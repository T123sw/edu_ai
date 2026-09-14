"""Project task checkpoints from committed outcomes, never from conversation text.

The foreground cursor is separate from background jobs and document references.
Only a newly presented plan/draft or an actual submission moves that cursor.
"""
from copy import deepcopy


def project_interaction(previous, result):
    state = deepcopy(previous or {'version': 0, 'foreground': None, 'tasks': {}})
    updates = []
    for event in (result.get('trace') or {}).get('tool_events', []):
        data = event.get('data') or {}
        if event.get('ok') and event.get('tool') in {'submit_report', 'submit_resource'} and data.get('outline_id'):
            submitted = state['tasks'].get('plan:' + data['outline_id'])
            if submitted and submitted['revision'] == data.get('revision') and submitted['status'] != 'submitted':
                submitted.update(status='submitted', job_id=data['task_id'])
                state['version'] += 1
        if event.get('ok') and event.get('tool') in {'query_report_job', 'query_resource_job'} and data.get('task_id'):
            updates.append((data['task_id'], data.get('status')))
    if result.get('task_id') and (result.get('workflow') or {}).get('status') in {'completed', 'failed', 'canceled'}:
        updates.append((result['task_id'], result['workflow']['status']))
    for job_id, status in updates:
        job = state['tasks'].get('job:' + job_id)
        if job and status and job['status'] != status:
            job['status'] = status
            state['version'] += 1
    revision = result.get('artifact_revision') or {}
    plan = result.get('harness_outline') or {}
    workflow = result.get('workflow') or {}
    task = None
    if revision.get('draft'):
        draft = revision['draft']
        task = {'id': 'draft:' + draft['draft_id'], 'kind': 'artifact_revision',
                'revision': draft['revision'], 'status': 'awaiting_confirm'}
    elif plan.get('outline_id'):
        task = {'id': 'plan:' + plan['outline_id'], 'kind': workflow.get('type'),
                'revision': plan['revision'], 'status': 'awaiting_confirm'}
    elif result.get('task_id') and workflow.get('status') == 'running':
        task = {'id': 'job:' + result['task_id'], 'kind': workflow.get('type'),
                'revision': 1, 'status': 'running'}
    elif revision.get('status') in {'completed', 'discarded'}:
        active = state['tasks'].get(state['foreground']) or {}
        if active.get('kind') == 'artifact_revision':
            task = {**active, 'status': revision['status']}
    if task is None:
        # Read-only answers and late background notifications cannot select a task.
        return state
    old = state['tasks'].get(state['foreground'])
    if old and old['id'] != task['id'] and old['status'] == 'awaiting_confirm':
        old['status'] = 'suspended'
    if state['foreground'] == task['id'] and state['tasks'].get(task['id']) == task:
        return state
    state['tasks'][task['id']] = task
    state['foreground'] = task['id']
    state['version'] += 1
    return state


from contextlib import contextmanager
import hashlib
from pathlib import Path
from filelock import FileLock
from core.config import Config


@contextmanager
def conversation_turn(payload):
    conversation_id = getattr(payload, 'conversation_id', None)
    owner = getattr(payload, 'owner', None)
    if not conversation_id:
        yield
        return
    root = Path(Config.STORAGE_ROOT) / 'interaction_locks'
    root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f'{owner}:{conversation_id}'.encode()).hexdigest()
    with FileLock(str(root / (key + '.lock')), timeout=15):
        yield
