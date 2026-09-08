"""Project durable task facts onto conversation messages, including older Harness turns."""
import hashlib
import json


def is_report_read_result(result):
    if (result.get('workflow') or {}).get('stage') == 'result_check':
        return True  # Results produced before queries were separated from generation.
    tools = {item.get('tool') for item in (result.get('trace') or {}).get('tool_events', []) if item.get('ok')}
    return 'query_report_job' in tools and not tools.intersection({'submit_report', 'cancel_report_job', 'draft_report_outline'})


def project_task_status(payload, owner, *, task_store=None, harness_root=None):
    from core.config import Config
    from app.chat.tasks.task_store import get_task_store
    task_store = task_store or get_task_store()
    # Storage returns shared nested objects; projections must not mutate history.
    payload = {**payload, 'history': [dict(m) for m in payload.get('history', [])]}
    links = dict((payload.get('state') or {}).get('task_messages') or {})
    root = harness_root if harness_root is not None else Config.STORAGE_ROOT / 'deepseek_harness'
    identity = [owner, payload.get('course_id'), payload['conversation_id']]
    key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
    path = root / key / 'state.json'
    if path.exists():
        try:
            saved = json.loads(path.read_text())
            for response in saved.get('responses', {}).values():
                request, result = response.get('request') or {}, response.get('result') or {}
                if request.get('owner') != owner or request.get('conversation_id') != payload['conversation_id']:
                    continue
                task_id = result.get('task_id')
                if not task_id:
                    continue
                # Match persisted content and its preceding user turn, never a keyword.
                history = payload['history']
                matches = []
                for index, message in enumerate(history):
                    if (index and message.get('role') == 'assistant'
                            and message.get('content') == (result.get('message') or {}).get('content')
                            and history[index - 1].get('role') == 'user'
                            and history[index - 1].get('content') == request.get('question')):
                        matches.append(message)
                if len(matches) == 1:
                    message_id = matches[0].get('message_id')
                    if is_report_read_result(result):
                        links.pop(message_id, None)
                        matches[0].pop('task_id', None)
                        matches[0].pop('task_status', None)
                    else:
                        links.setdefault(message_id, task_id)
        except (OSError, ValueError):
            pass
    for message in payload['history']:
        task_id = links.get(message.get('message_id'))
        if not task_id:
            continue
        task = task_store.get(task_id, owner_user_id=owner)
        if not task:
            continue
        status = task.get('status')
        message.update(task_id=task_id, task_status=status)
        if status in {'succeeded', 'completed'}:
            message['content'] = '任务已完成，生成的资料可在右侧“最近生成”中查看。'
        elif status in {'failed', 'canceled'}:
            message['content'] = '任务已取消。' if status == 'canceled' else '任务生成失败，请在后台任务中查看详情。'
        elif status in {'pending', 'queued', 'running'}:
            message['content'] = '任务正在进行，完成后会在这里显示。'
    return payload
