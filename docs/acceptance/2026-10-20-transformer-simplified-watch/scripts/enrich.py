"""Add observable policy, speech and error details to the saved timing summary."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]


def read(name, default=None):
    path = OUT / name
    return json.loads(path.read_text()) if path.exists() else default


summary = read('summary.json')
live = read('live-session-audit.json', {})
results = live.get('tool_results', [])
speech = []
for start in results:
    if start['tool'] != 'prepare_narration':
        continue
    cid = start['result']['command_id']
    finish = start if start['result']['exit_code'] is not None else next(
        (r for r in results if r['node'] == start['node']
         and r['session'] == start['session'] and r['result']['command_id'] == cid
         and r['result']['exit_code'] is not None), None)
    speech.append({'node': start['node'], 'command_id': cid,
                   'started_at': start['called_at'],
                   'finished_observed_at': finish['returned_at'] if finish else None,
                   'seconds_including_polling': round(finish['returned_at'] - start['called_at'], 3) if finish else None,
                   'exit_code': finish['result']['exit_code'] if finish else None})
audits = read('action-audit.json', {})
summary['quiz_generation'] = [{
    'node': q['node'], 'status': q['status'], 'questions': q['questions'],
    'review_policy': q['receipt'].get('policy'), 'review_decision': q['receipt'].get('decision'),
    'model_calls': len(q['model_calls']), 'model_phases': [r['phase'] for r in q['model_calls']]}
    for q in audits.get('quizzes', [])]
summary['narration_commands'] = speech
summary['narration_timing_note'] = (
    'Speech command request to first observed completion; includes command setup and polling latency. '
    'Multiple commands may reuse cached speech or regenerate changed lines; audio length is not synthesis time.')
summary['runtime_builds'] = [
    {'artifact': path.parent.name, **json.loads(path.read_text())}
    for path in OUT.glob('artifact_*/runtime.json')]
summary['session_error_events'] = live.get('session_errors', [])
summary['protocol_recoveries'] = audits.get('protocol_recoveries', [])
summary['failed_model_actions'] = audits.get('failed_actions', [])
summary['native_tool_failures'] = [r for r in results if r['result']['ok'] is False]
seen = set()
commands = []
for row in results:
    cid = row['result']['command_id']
    if row['result']['exit_code'] in (None, 0) or cid in seen:
        continue
    seen.add(cid)
    commands.append(row)
summary['nonzero_native_commands'] = commands
summary['error_note'] = 'Native exploratory tool/command errors and recovered protocol corrections are distinct from failed resources.'
summary['content_spotcheck'] = {'performed': False, 'reason': 'This run tracks production behavior; no model review or semantic repair was initiated by the observer.'}
summary['visual_spotcheck'] = read('visual-spotcheck.json', {'performed': False})
summary['observation_start'] = read('observation-start.json')
model = read('model-response-timing.json', {})
completed = model.get('completed', [])
summary['native_model_response_observation'] = {
    'completed_steps': len(completed),
    'longest_response_wait_seconds': max((r['response_wait_seconds'] for r in completed), default=None),
    'responses_over_300_seconds': [
        r for r in completed if r['response_wait_seconds'] > 300],
    'note': model.get('note')}
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
(OUT / 'narration-timing.json').write_text(json.dumps(speech, ensure_ascii=False, indent=2))
print(json.dumps({'status': summary['status'], 'speech_commands': len(speech),
                  'failed_tools': len(summary['native_tool_failures']),
                  'nonzero_commands': len(commands), 'session_errors': len(summary['session_error_events'])}))
