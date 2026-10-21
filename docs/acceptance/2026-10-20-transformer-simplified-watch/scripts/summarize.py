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
delivery = dict(s.get('delivery') or {})
if terminal and terminal['type'] == 'succeeded':
    # partial_delivery is a historical checkpoint; final commit emits a newer manifest.
    delivery.update(terminal['payload'])
    final_manifest = read(ROOT / 'manifests.json', [])[-1]
    delivery['available_resources'] = sum(
        len(n.get('resources', [])) for n in final_manifest['payload']['nodes'])
    delivery['delivery_state'] = final_manifest['payload'].get('delivery_state')
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
                         'seconds_since_start': rounded(epoch(m['created_at'])-start),
                         'resources': len(resources)})
    for r in resources:
        first_open.setdefault(r['resource_id'], m['created_at'])
resources = []
for a in s['artifacts']:
    dest = ROOT / a['id']
    opened = first_open.get(a['id'].replace('artifact_', 'resource_'))
    r = {k: a.get(k) for k in ('id', 'node', 'type', 'status', 'created_at', 'started_at',
                              'finished_at', 'execution_seconds', 'task_error', 'error')}
    r.update(start_after_task_start_seconds=rounded(a['started_at']-start) if a.get('started_at') else None,
             submitted_after_first_produce_seconds=rounded(epoch(a['created_at'])-produce) if produce else None,
             durable_queue_seconds=rounded(a['started_at']-epoch(a['created_at'])) if a.get('started_at') else None,
             first_opened_at=opened,
             open_after_task_start_seconds=rounded(epoch(opened)-start) if opened else None)
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
            render_row = {'command_id': render['command_id'], 'started_at': render['at'],
                                 'finished_at': done['at'] if done else None,
                                 'exit_code': done.get('exit_code') if done else None,
                                 'seconds_including_admission_and_poll': rounded(done['at']-render['at']) if done else None}
            log_path = dest / 'commands' / (render['command_id'] + '.log')
            trace = []
            if log_path.exists():
                for line in log_path.read_text().splitlines():
                    if line.startswith('{"stage": "render"'):
                        admission = json.loads(line)
                        if admission.get('status') == 'running':
                            render_row['admission_wait_seconds'] = rounded(admission.get('wait_seconds'))
                    if '[Render:trace] ' in line:
                        try:
                            trace.append(json.loads(line.split('[Render:trace] ', 1)[1]))
                        except ValueError:
                            pass
            render_row['native_phase_seconds'] = {
                t['phase']: rounded(t['durationMs']/1000)
                for t in trace if t.get('status') == 'end' and t.get('durationMs') is not None
            }
            r['renders'].append(render_row)
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
light = [r for r in resources if r['type'] in ('quiz', 'report')]
light_finished = (max(r['finished_at'] for r in light)
                  if light and all(r['finished_at'] for r in light) else None)
first_review = next((epoch(e['at']) for e in stage_events if e['payload']['stage'] == 'review'), None)
initial_light = [r for r in light if first_review is None or epoch(r['created_at']) < first_review]
logical_latest = {}
repair_delays = []
for r in resources:
    key = (r['node'], r['type'])
    prior = logical_latest.get(key)
    if prior and prior.get('finished_at'):
        repair_delays.append({'node': r['node'], 'type': r['type'], 'prior_artifact': prior['id'],
                              'replacement_artifact': r['id'],
                              'seconds_from_prior_finish_to_replacement_submission':
                                  rounded(epoch(r['created_at'])-prior['finished_at'])})
    logical_latest[key] = r
summary = {'preparation_id': s['preparation_id'], 'attempt': s['attempt_no'], 'status': s['status'],
           'as_of': s['at'], 'started_at': s['attempt_started_at'],
           'finished_at': terminal['at'] if terminal else None, 'seconds_since_start': rounded(end-start),
           'original_started_at': s['original_started_at'], 'original_error': None,
           'prior_attempts': [],
           'timing_note': 'Fresh attempt 1. Resource phases overlap and should not be added across videos. This is an observational run, not a controlled speed benchmark.',
           'phase_boundaries': 'Native preparation includes brief conversion, script/storyboard, narration, packet creation and their retries. Scene span includes admission queues and overlaps across workers. Render duration includes admission and polling latency. Narration synthesis is asynchronous; host tool elapsed is submission latency and is not reported as synthesis duration.',
           'observation_note': 'Entire observation is read-only; no retry, cancellation, restart or production changes. Previews are copied existing native snapshots.',
           'delivery': delivery,
           'delivery_source': 'Final succeeded event and latest manifest when terminal; partial-delivery checkpoint while running.',
           'error': s['error'], 'counts': s['resource_counts'],
           'counts_note': 'Artifact counts retain failed historical versions; logical_latest_counts uses the latest submission for each node/type. Delivery availability is authoritative for published resources.',
           'logical_latest_counts': {status: sum(r['status'] == status for r in logical_latest.values())
                                     for status in sorted({r['status'] for r in logical_latest.values()})},
           'automatic_replacement_delays': repair_delays,
           'milestones': {
               'first_nonempty_manifest': next((m for m in availability if m['resources'] > 0), None),
               'initial_report_quiz_execution_finished_after_start_seconds': rounded(
                   max(r['finished_at'] for r in initial_light)-start)
                   if initial_light and all(r['finished_at'] for r in initial_light) else None,
               'report_quiz_execution_finished_after_start_seconds': rounded(light_finished-start) if light_finished else None,
               'report_quiz_opened_after_start_seconds': max(
                   (r['open_after_task_start_seconds'] for r in light if r['first_opened_at']), default=None),
               'report_quiz_counts': {status: sum(r['status'] == status for r in light)
                                     for status in sorted({r['status'] for r in light})}},
           'stages': stages, 'availability': availability, 'resources': resources,
           'concurrency_observations': read(ROOT / 'concurrency-observations.json'),
           'content_spotcheck': 'content-spotcheck.json', 'visual_spotcheck': 'visual-spotcheck.json',
           'media_probe': read(ROOT / 'media-probe.json'),
           'playback_checks': 'playback-checks.json',
           'observed_issues': read(ROOT / 'observed-issues.json'),
           'fix': '../2026-10-20-generation-simplification/summary.json'}
save('summary.json', summary)
video_rows = []
for r in resources:
    if r['type'] != 'classroom':
        continue
    video_rows.append({k: r.get(k) for k in (
        'node', 'status', 'start_after_task_start_seconds', 'execution_seconds',
        'brief_seconds', 'native_preparation_including_brief_seconds',
        'scene_span_including_queue_seconds', 'assembly_and_check_seconds',
        'post_render_seconds', 'video_seconds', 'scenes', 'narrated_scenes')})
    video_rows[-1]['render_seconds_including_admission_and_poll'] = (
        r['renders'][-1]['seconds_including_admission_and_poll'] if r['renders'] else None)
    video_rows[-1]['render_admission_seconds'] = (
        r['renders'][-1].get('admission_wait_seconds') if r['renders'] else None)
for name, rows in [('stage-timing.csv', stages), ('resource-timing.csv', resources),
                   ('video-timing.csv', video_rows)]:
    keys = list(dict.fromkeys(k for row in rows for k, v in row.items() if not isinstance(v, (dict, list))))
    with (ROOT / name).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
print(json.dumps({'status': s['status'], 'minutes': round((end-start)/60, 2),
                  'counts': s['resource_counts'], 'availability': availability[-1:]}, ensure_ascii=False))
