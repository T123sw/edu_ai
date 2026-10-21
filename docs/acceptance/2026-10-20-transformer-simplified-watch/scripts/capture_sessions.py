"""Copy only this preparation's live SDK traces; never changes runtime files."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
reported = None


def sample():
    global reported
    state = json.loads((OUT / 'latest.json').read_text())
    workspaces = {a['workspace']: a for a in state['artifacts'] if a.get('workspace')}
    candidates = list(Path('/tmp').glob('edu-hf-sdk-*/home/sessions/*/*/session.jsonl'))
    for workspace in workspaces:
        candidates.extend((Path(workspace) / '.host/sessions').glob('*.jsonl'))
    for path in candidates:
        try:
            with path.open('rb') as source:
                header = json.loads(source.readline())
                artifact = workspaces.get(header.get('cwd'))
                if artifact is None:
                    continue
                dest = OUT / artifact['id'] / 'sessions' / (header['id'] + '.jsonl')
                dest.parent.mkdir(exist_ok=True)
                # A finalized copy replaces its live counterpart only if longer.
                previous = dest.stat().st_size if dest.exists() else 0
                if path.stat().st_size <= previous:
                    continue
                source.seek(previous)
                chunk = source.read()
                with dest.open('ab') as target:
                    target.write(chunk)
        except (OSError, ValueError, KeyError):
            continue
    errors, tools, calls = [], [], {}
    for artifact in workspaces.values():
        for path in (OUT / artifact['id'] / 'sessions').glob('*.jsonl'):
            for line in path.read_text().splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                kind, data = event.get('type', ''), event.get('data') or {}
                if any(word in kind.lower() for word in ('error', 'retry', 'timeout')):
                    errors.append({'node': artifact['node'], 'session': path.name, 'event': event})
                if kind == 'tool/call':
                    calls[(path.name, data.get('callId'))] = event
                if kind != 'tool/result':
                    continue
                for block in (data.get('message') or {}).get('content', []):
                    if block.get('type') != 'tool-result':
                        continue
                    call = calls.get((path.name, block.get('toolCallId')))
                    if call is None:
                        continue
                    for part in block.get('content', []):
                        if part.get('type') != 'text':
                            continue
                        try:
                            result = json.loads(part['text'].removeprefix('Error: '))
                        except (ValueError, KeyError):
                            continue
                        if not isinstance(result, dict):
                            continue
                        tool = call['data']['name'].removeprefix('mcp__hyperframes__')
                        if result.get('ok') is False or result.get('exit_code') not in (None, 0) or tool in (
                                'prepare_narration', 'prepare_scene_assets', 'render_project', 'poll_command'):
                            tools.append({'node': artifact['node'], 'session': path.name,
                                'tool': tool, 'called_at': call['time'] / 1000,
                                'returned_at': event['time'] / 1000,
                                'arguments': call['data'].get('arguments'),
                                'result': {k: result.get(k) for k in (
                                    'ok', 'error', 'command_id', 'exit_code', 'output_file')}})
    result = {'as_of': datetime.now(timezone.utc).isoformat(), 'session_errors': errors,
              'tool_results': tools, 'note': 'Live and finalized traces deduplicated by native session ID.'}
    target = OUT / 'live-session-audit.json'
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    temp.replace(target)
    counts = {'session_errors': len(errors), 'failed_tools': sum(r['result']['ok'] is False for r in tools),
              'nonzero_commands': len({(r['session'], r['result']['command_id']) for r in tools
                                      if r['result']['exit_code'] not in (None, 0)})}
    if counts != reported:
        print(json.dumps({'at': result['as_of'], **counts}), flush=True)
        reported = counts
    return state['status'] in ('succeeded', 'failed', 'canceled')


while True:
    try:
        if sample():
            break
    except (OSError, ValueError) as exc:
        print(json.dumps({'observer_error': str(exc)[:200]}), flush=True)
    time.sleep(30)
