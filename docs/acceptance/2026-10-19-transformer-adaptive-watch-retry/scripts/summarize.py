"""Summarize saved observer evidence only; never writes production state."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def epoch(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def rounded(value):
    return round(value, 3) if value is not None else None


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))


s = read(ROOT / 'latest.json')
start = epoch(s['attempt_started_at'])
events = read(ROOT / 'preparation-events.json', [])
current = [e for e in events if e['attempt'] == s['attempt_no']]
terminal = next((e for e in current if e['type'] in ('succeeded', 'failed', 'canceled')), None)
end = epoch(terminal['at'] if terminal else s['at'])
stage_events = [e for e in current if e['type'] == 'stage_changed']
stages = []
for i, e in enumerate(stage_events):
    until = epoch(stage_events[i+1]['at']) if i+1 < len(stage_events) else end
    stages.append({'stage': e['payload']['stage'], 'started_at': e['at'],
                   'seconds': rounded(until - epoch(e['at'])),
                   'complete': i+1 < len(stage_events) or terminal is not None})
produce = next((epoch(e['at']) for e in stage_events if e['payload']['stage'] == 'produce'), None)
availability = []
first_open = {}
for m in read(ROOT / 'manifests.json', []):
    resources = [r for n in m['payload']['nodes'] for r in n.get('resources', [])]
    availability.append({'version': m['version'], 'at': m['created_at'],
                         'seconds_since_resume': rounded(epoch(m['created_at'])-start),
                         'resources': len(resources)})
    for r in resources:
        first_open.setdefault(r['resource_id'], m['created_at'])
resources = []
for a in s['artifacts']:
    dest = ROOT / a['id']
    opened = first_open.get(a['id'].replace('artifact_', 'resource_'))
    r = {k: a.get(k) for k in ('id', 'node', 'type', 'status', 'created_at', 'started_at',
                              'finished_at', 'execution_seconds', 'task_error', 'error')}
    r.update(start_after_resume_seconds=rounded(a['started_at']-start) if a.get('started_at') else None,
             scheduler_delay_after_produce_seconds=rounded(epoch(a['created_at'])-produce) if produce else None,
             durable_queue_seconds=rounded(a['started_at']-epoch(a['created_at'])) if a.get('started_at') else None,
             first_opened_at=opened,
             open_after_resume_seconds=rounded(epoch(opened)-start) if opened else None)
    content = read(dest / 'content.json', {})
    body = content.get('content', {})
    if a['type'] == 'quiz':
        r['questions'] = len(body.get('questions', [])) if isinstance(body, dict) else None
    if a['type'] == 'classroom':
        ev = read(dest / 'host-events.json', [])
        workers = a.get('scene_workers', [])
        r.update(brief_seconds=a.get('brief_seconds'), scene_worker_groups=len(workers),
                 tool_failures=a.get('tool_failures', []), runtime=read(dest / 'runtime.json'))
        dispatch = min((w['submitted_at'] for w in workers), default=None)
        all_done = bool(workers) and all(w.get('finished_at') for w in workers)
        scene_end = max(w['finished_at'] for w in workers) if all_done else None
        r['native_preparation_including_brief_seconds'] = rounded(dispatch-a['started_at']) if dispatch else None
        r['scene_span_including_queue_seconds'] = rounded(scene_end-dispatch) if scene_end else None
        r['scene_workers'] = workers
        r['scene_phase_outcome'] = ('failed_or_canceled' if any(w['status'] in ('failed', 'canceled') for w in workers)
                                    else 'succeeded' if all_done else 'running' if workers else 'not_started')
        renders = [e for e in ev if e['tool'] == 'render_project' and e.get('command_id')]
        r['renders'] = []
        for render in renders:
            done = next((e for e in ev if e['tool'] == 'poll_command' and
                         e.get('command_id') == render['command_id'] and e.get('exit_code') is not None), None)
            r['renders'].append({'command_id': render['command_id'], 'started_at': render['at'],
                                 'finished_at': done['at'] if done else None,
                                 'exit_code': done.get('exit_code') if done else None,
                                 'seconds_including_admission_and_poll': rounded(done['at']-render['at']) if done else None})
        if renders and scene_end:
            r['assembly_and_check_seconds'] = rounded(renders[0]['at']-scene_end)
        if r['renders'] and r['renders'][-1]['finished_at'] and a.get('finished_at'):
            r['post_render_seconds'] = rounded(a['finished_at']-r['renders'][-1]['finished_at'])
        timeline = body.get('timeline', {}) if isinstance(body, dict) else {}
        segments = timeline.get('segments', [])
        r.update(video_seconds=timeline.get('duration'), scenes=len(segments),
                 narrated_scenes=sum(bool(x.get('narration')) for x in segments),
                 verification=body.get('verification') if isinstance(body, dict) else None,
                 projects=[{k: p.get(k) for k in ('path', 'audio_seconds', 'audio_lines', 'frame_files', 'renders')}
                           for p in a.get('projects', [])])
    resources.append(r)
summary = {'preparation_id': s['preparation_id'], 'attempt': s['attempt_no'], 'status': s['status'],
           'as_of': s['at'], 'started_at': s['attempt_started_at'],
           'finished_at': terminal['at'] if terminal else None, 'seconds_since_resume': rounded(end-start),
           'original_started_at': s['original_started_at'], 'original_error': 'STEP_FAILED',
           'original_attempt_seconds': 101.480621,
           'timing_note': 'Attempt 2 reuses research and planning. It excludes failure-to-restart downtime; not a fresh-course controlled benchmark. Stage spans overlap across resources.',
           'observation_note': 'Normal retry resumed the original task once; subsequent observation is read-only. Previews are copied existing native snapshots.',
           'delivery': s['delivery'], 'error': s['error'], 'counts': s['resource_counts'],
           'stages': stages, 'availability': availability, 'resources': resources,
           'concurrency_observations': read(ROOT / 'concurrency-observations.json'),
           'content_spotcheck': 'content-spotcheck.json', 'visual_spotcheck': 'visual-spotcheck.json',
           'media_probe': read(ROOT / 'media-probe.json'),
           'fix': '../2026-10-19-preparation-pool-starvation/summary.json'}
save('summary.json', summary)
for name, rows in [('stage-timing.csv', stages), ('resource-timing.csv', resources)]:
    keys = list(dict.fromkeys(k for row in rows for k, v in row.items() if not isinstance(v, (dict, list))))
    with (ROOT / name).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
print(json.dumps({'status': s['status'], 'minutes': round((end-start)/60, 2),
                  'counts': s['resource_counts'], 'availability': availability[-1:]}, ensure_ascii=False))
