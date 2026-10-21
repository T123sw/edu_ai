"""Measure observed SDK step-to-response waits, excluding subsequent tool time."""
import json
import time
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
state = json.loads((OUT / 'latest.json').read_text())
nodes = {a['id']: a['node'] for a in state['artifacts']}
rows, pending = [], []
now = time.time()
for path in OUT.glob('artifact_*/sessions/*.jsonl'):
    starts, first, finished = {}, {}, set()
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        data = event.get('data') or {}
        key = (data.get('turn'), data.get('step'))
        if event['type'] == 'step/start':
            starts[key] = event['time'] / 1000
        elif event['type'] == 'assistant/chunk':
            first.setdefault(key, event['time'] / 1000)
        elif event['type'] == 'assistant/message' and key in starts:
            finished.add(key)
            row = {'node': nodes[path.parent.parent.name], 'session': path.name,
                   'turn': key[0], 'step': key[1], 'started_at': starts[key],
                   'response_at': event['time'] / 1000,
                   'first_chunk_wait_seconds': round(first.get(key, event['time'] / 1000) - starts[key], 3),
                   'response_wait_seconds': round(event['time'] / 1000 - starts[key], 3),
                   'usage': data.get('usage'), 'tools': [
                       b.get('name') for b in (data.get('message') or {}).get('content', [])
                       if b.get('type') == 'tool-call']}
            rows.append(row)
    for key, start in starts.items():
        if key not in finished:
            pending.append({'node': nodes[path.parent.parent.name], 'session': path.name,
                            'turn': key[0], 'step': key[1],
                            'seconds_since_step_start': round(now - start, 3)})
result = {'observed_at': now, 'completed': rows, 'pending': pending,
          'note': 'SDK step start to first/full assistant response; may include provider protocol correction. Heartbeat comments are not model output. Pending waits use last copied trace.'}
(OUT / 'model-response-timing.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({'completed_steps': len(rows),
                  'longest_completed': sorted(
                      [{k: r[k] for k in ('node', 'response_wait_seconds', 'tools')} for r in rows],
                      key=lambda r: r['response_wait_seconds'], reverse=True)[:3],
                  'longest_pending': sorted(pending, key=lambda r: r['seconds_since_step_start'], reverse=True)[:3]},
                 ensure_ascii=False))
