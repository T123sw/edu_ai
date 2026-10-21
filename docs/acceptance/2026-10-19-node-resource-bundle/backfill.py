"""One-off authorized companion-resource backfill; use the normal preparation API."""
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / 'backfill.json'
COURSE = 'learn-4abecf6908d242b5bbed483aff8a17de'
AUTH = Path('/tmp/hf-demo-course-auth/auth.json')


def api(path, body=None):
    token = json.loads(AUTH.read_text())['token']
    request = urllib.request.Request('http://127.0.0.1/backend/api/' + path,
        data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 502, 503, 504) or attempt == 5:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 5:
                raise
        time.sleep(min(5 * (attempt + 1), 20))


def save(value):
    temporary = LEDGER.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(LEDGER)


def main():
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {'course': COURSE, 'nodes': [], 'status': 'running'}
    room = api('self-learning/courses/' + COURSE)
    if not ledger['nodes']:
        ledger['nodes'] = [{'node_id': node['id'], 'title': node['title'], 'status': 'pending'} for node in room['chapters']]
        ledger['originalVideos'] = [r for node in room['chapters'] for r in node['resources'] if r['kind'] == 'video']
        save(ledger)
    for node in ledger['nodes']:
        if node['status'] in ('succeeded', 'already_complete'):
            continue
        if not node.get('request'):
            room = api('self-learning/courses/' + COURSE)
            chapter = next(n for n in room['chapters'] if n['id'] == node['node_id'])
            existing = {r['kind'] for r in chapter['resources'] if r['ready']}
            missing = [kind for kind in ('report', 'quiz') if kind not in existing]
            if not missing:
                node['status'] = 'already_complete'; save(ledger); continue
            node['request'] = {'request_id': str(uuid4()), 'operation': 'supplement_node',
                'goal': f"为当前冒泡排序课程的「{node['title']}」知识点补齐独立报告和配套习题。沿用本节点既有学习目标、语言和基础，报告讲清知识并给出例子，习题用于检验这些目标且包含答案和解析。保留原学习路径、节点目标和全部已有资料，只补齐缺失的报告和习题，不重新生成视频。",
                'target': {'course_id': COURSE, 'node_id': node['node_id'], 'base_manifest_version': room['manifestRef']['version']},
                'overrides': {'include_classroom': False, 'required_resource_types': missing}}
            save(ledger)
        if not node.get('preparation_id'):
            task = api('course-preparations', node['request'])
            node.update(preparation_id=task['preparation_id'], status=task['status'])
            save(ledger)
            print(json.dumps({'node': node['node_id'], 'preparation_id': node['preparation_id'], 'status': node['status']}), flush=True)
        while True:
            task = api('course-preparations/' + node['preparation_id'])
            node.update(status=task['status'], stage=task['stage'], result_ref=task.get('result_ref'), error_code=task.get('error_code'))
            save(ledger)
            if task['status'] == 'succeeded':
                print(json.dumps({'node': node['node_id'], 'status': 'succeeded'}), flush=True)
                break
            if task['status'] in ('failed', 'canceled'):
                ledger['status'] = 'stopped'; save(ledger)
                raise RuntimeError(f"Backfill stopped: {node['node_id']} {task['status']} {task.get('error_code')}")
            time.sleep(15)
    room = api('self-learning/courses/' + COURSE)
    videos = [r for n in room['chapters'] for r in n['resources'] if r['kind'] == 'video']
    ledger['videoIdentitiesPreserved'] = [(r['id'], r.get('remote')) for r in videos] == [(r['id'], r.get('remote')) for r in ledger['originalVideos']]
    ledger['status'] = 'succeeded'
    ledger['manifestRef'] = room['manifestRef']
    save(ledger)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if LEDGER.exists():
            ledger = json.loads(LEDGER.read_text())
            ledger.update(status='stopped', error=f'{type(exc).__name__}: {exc}')
            save(ledger)
        raise
