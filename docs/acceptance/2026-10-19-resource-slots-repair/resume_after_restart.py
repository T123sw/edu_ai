"""One bounded recovery of the two user-authorized failures after backend reload."""
import json
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / 'recovery.json'
BACKFILL = ROOT.parent / '2026-10-19-node-resource-bundle/backfill.json'
LATEST = 'prep_a9c1d026075f47b3aaa7fbc0862a7692'
SUPPLEMENT = 'prep_23c0a1f3160d4c45843f9264c6efc8e8'
OLD_PID = '2527834'
AUTH = Path('/tmp/hf-demo-course-auth/auth.json')


def api(path, body=None):
    token = json.loads(AUTH.read_text())['token']
    request = urllib.request.Request('http://127.0.0.1/backend/api/' + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 502, 503, 504) or attempt == 5: raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 5: raise
        time.sleep(5)


def save(value, path=LEDGER):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def identity(room):
    return sorted((r['id'], r.get('remote', {}).get('version'))
        for c in room['chapters'] for r in c['resources'] if r['ready'])


def main():
    state = json.loads(LEDGER.read_text()) if LEDGER.exists() else {'status': 'waiting_backend_restart', 'tasks': {}}
    save(state)
    while True:
        pid = subprocess.check_output(['systemctl', 'show', 'edu-ai-backend', '-p', 'MainPID', '--value'], text=True).strip()
        active = subprocess.check_output(['systemctl', 'show', 'edu-ai-backend', '-p', 'ActiveState', '--value'], text=True).strip()
        if pid not in ('0', OLD_PID) and active == 'active': break
        time.sleep(10)
    state.update(status='recovering', backend_pid=pid); save(state)
    # User workers are separately owned and can be reloaded normally.
    subprocess.run(['systemctl', '--user', 'restart', 'edu-ai-durable-workers'], check=True)
    for task_id in (LATEST, SUPPLEMENT):
        task = api('course-preparations/' + task_id)
        if task_id == LATEST and 'originalResources' not in state:
            state['originalResources'] = identity(api('self-learning/courses/learn-a9c1d026075f47b3aaa7fbc0862a7692'))
            save(state)
        if task['status'] == 'failed' and task['attempt_no'] == 1 and task_id not in state['tasks']:
            task = api('course-preparations/' + task_id + '/retry', {})
        state['tasks'][task_id] = {k: task.get(k) for k in ('status', 'stage', 'attempt_no', 'error_code')}
        save(state)
        if task['status'] in ('failed', 'canceled'):
            raise RuntimeError(f'Recovery stopped at {task_id}: {task["status"]}')
    ledger = json.loads(BACKFILL.read_text())
    ledger['status'] = 'running'; ledger.pop('error', None)
    for node in ledger['nodes']:
        if node.get('preparation_id') == SUPPLEMENT:
            node['status'] = state['tasks'][SUPPLEMENT]['status']; node['error_code'] = None
    save(ledger, BACKFILL)
    subprocess.run(['systemctl', '--user', 'restart', 'edu-node-resource-backfill-20261019'], check=True)
    while True:
        latest = api('course-preparations/' + LATEST)
        state['tasks'][LATEST] = {k: latest.get(k) for k in ('status', 'stage', 'attempt_no', 'error_code', 'result_ref')}
        supplement = api('course-preparations/' + SUPPLEMENT)
        state['tasks'][SUPPLEMENT] = {k: supplement.get(k) for k in ('status', 'stage', 'attempt_no', 'error_code')}
        backfill = json.loads(BACKFILL.read_text()); state['backfill_status'] = backfill['status']
        state['backfill_nodes'] = [{k: n.get(k) for k in ('node_id', 'status', 'preparation_id')} for n in backfill['nodes']]
        save(state)
        if latest['status'] in ('failed', 'canceled') or backfill['status'] == 'stopped':
            raise RuntimeError('A recovery task stopped; details retained in the task and backfill ledgers')
        if latest['status'] == 'succeeded' and backfill['status'] == 'succeeded':
            room = api('self-learning/courses/learn-a9c1d026075f47b3aaa7fbc0862a7692')
            state['originalResourcesPreserved'] = set(map(tuple, state['originalResources'])) <= set(identity(room))
            if not state['originalResourcesPreserved']: raise RuntimeError('Original resource identities changed')
            state['status'] = 'succeeded'; save(state); return
        time.sleep(15)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        state = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
        state.update(status='stopped', error=f'{type(exc).__name__}: {exc}')
        save(state)
        raise
