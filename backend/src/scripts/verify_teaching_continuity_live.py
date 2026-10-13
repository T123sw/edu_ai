"""Real-model acceptance for learning continuity with seeded inaccurate history."""
import json
import os
from pathlib import Path
import time
from uuid import uuid4


def main():
    if os.getenv('LEARNING_LIVE_ACCEPTANCE') != '1':
        raise SystemExit('Set LEARNING_LIVE_ACCEPTANCE=1 to make real model calls.')
    test_url = os.environ['LEARNING_TEST_DATABASE_URL']
    from app.services.runtime_config_resolver import runtime_config_resolver
    config = runtime_config_resolver.resolve('llm')
    os.environ['LEARNING_TEST_DATABASE_URL'] = test_url
    for flag in ('LEARNING_SESSION_V1_ENABLED', 'LEARNING_PROGRESS_V1_ENABLED',
                 'LEARNING_AGENT_V1_ENABLED', 'LEARNING_ENRICHMENT_V1_ENABLED',
                 'LEARNING_PREPARATION_V1_ENABLED', 'LEARNING_SCOPED_ROLLOUT',
                 'COURSE_PREPARATION_ENABLED'):
        os.environ[flag] = 'false'
    os.environ.update(LEARNING_BROWSER_AGENT='1', LEARNING_BROWSER_ENRICHMENT='1',
                      LEARNING_BROWSER_PREPARATION='0', LEARNING_BROWSER_REAL='0')
    from tests.self_learning import browser_app as fixture
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from app.self_learning.agent_runtime import LearningAgentRuntime
    from app.self_learning.model_adapter import LearningModelAdapter
    from app.chat.bounded_completion import answer_json

    svc = fixture.svc
    model = LearningModelAdapter.from_config(config)
    runtime = LearningAgentRuntime(svc, svc.turn_repository, lambda _: model)
    app = FastAPI()  # No fixture lifespan: run only the real model worker explicitly.
    app.include_router(fixture.router)
    app.dependency_overrides.update(fixture.app.dependency_overrides)
    client = TestClient(app, headers={'Authorization': 'Bearer alice'})
    prefix = '/api/self-learning'
    course = prefix + '/courses/learning-fixture/topics/'
    report = {'model': config['model'], 'storage': 'disposable PostgreSQL schema and temporary files',
              'cases': [], 'api_checks': [], 'semantic_review': 'pending'}
    output = Path(__file__).resolve().parents[3] / 'docs/acceptance/2026-10-13-teaching-continuity/live.json'
    output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    def request(method, path, body=None, expected=200, **kwargs):
        response = client.request(method, path, json=body, **kwargs)
        assert response.status_code == expected, (path, response.status_code, response.text)
        return response.json()

    def put(node, kind, mid, data):
        svc.manager.save_generated_material('learning-fixture', kind, mid,
            {**data, 'learning_course_resource': True}, owner_user_id='alice',
            visibility='course', scope_type='knowledge_point', scope_id=node)

    def ask(label, question, node='a', kind='report', mid='a-core', **snapshot):
        source = svc.material('learning-fixture', kind, mid, 'alice')
        reading = {'resource_ref': {'course_id': 'learning-fixture', 'material_type': kind,
                   'material_id': mid, 'version': source['version']}, **snapshot}
        accepted = request('POST', course + node + '/agent-turns',
                           {'request_id': str(uuid4()), 'question': question, 'reading_context': reading}, 202)
        started = time.monotonic()
        runtime.run_once()
        finished = request('GET', prefix + '/agent-turns/' + accepted['turn_id'])
        report['cases'].append({'case': label, 'question': question, 'reading_context': reading,
            'seconds': round(time.monotonic() - started, 2), 'response': finished})
        save()
        print(json.dumps({'case': label, 'status': finished['status']}, ensure_ascii=False), flush=True)
        return finished

    async def real_json(owner, system, data, seconds=25):
        result = await model.complete([{'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}], [],
            deadline=time.monotonic() + seconds)
        return answer_json(result['content'])

    try:
        svc.manager.save_course_info('learning-fixture', {'id': 'learning-fixture', 'title': 'Python 入门', 'created_by': 'alice'})
        svc.manager.save_knowledge_graph('learning-fixture', {'root': {'id': 'root', 'children': [
            {'id': 'a', 'label': '变量与赋值'}, {'id': 'b', 'label': '算术表达式'},
            {'id': 'c', 'label': '历史记录'}, {'id': 'long', 'label': '阅读长文'}]}})
        put('a', 'report', 'a-core', {'title': '变量讲义', 'content': '# 变量与赋值\n\nx = 1 绑定整数对象。y = x 让 y 绑定同一对象，x = 2 只改变 x 的绑定，y 仍为 1。'})
        entered = request('POST', course + 'a/enter')
        repo = svc.session_repository
        with repo._write(entered['session_id']) as db:
            session = repo._owned(db, 'alice', entered['session_id'])
            for i in range(3):
                repo._append(db, session, f'old-u-{i}', 'user', '围绕哪个课程和知识点？', 'user_content', {'request_id': f'old-{i}'})
                repo._append(db, session, f'old-a-{i}', 'assistant', '课程名称未知；正式知识点是核心概念的定义边界。', 'assistant_content', {'request_id': f'old-{i}'})
        ask('old_history_course_identity', '我们现在学习哪个课程和哪个知识点？简短回答。')
        answer = ask('explicit_difficulty', '我现在还是不理解变量重新赋值为什么不影响 y。请在本知识点教学记录里记下这项困惑，并给一个提示。')
        notes = request('GET', course + 'a/observations')['items']
        assert notes and any(n['kind'] in ('difficulty', 'open_question') for n in notes)
        note = next(n for n in notes if n['kind'] in ('difficulty', 'open_question'))
        assert note['sources'] and note['resource_ref']['material_id'] == 'a-core'
        request('POST', prefix + '/observations/' + note['turn_id'], {'status': 'resolved'})
        ask('after_correction', '以我更新后的教学记录为准，刚才那项困惑现在是什么状态？这能证明我掌握整个知识点了吗？')
        ask('helpful_explanation', '用贴标签来解释变量绑定对我很有帮助，请在本知识点记下这个有效讲法，不要设为所有课程的长期偏好。')
        notes = request('GET', course + 'a/observations')['items']
        assert any(n['kind'] == 'helpful_explanation' for n in notes)
        assert svc.memory.read('alice', 'learning-fixture')['items'] == []
        for case in report['cases']:
            assert case['response']['status'] == 'succeeded', case
        report['api_checks'] = [{'case': 'notes_keep_sources_and_corrections', 'notes': notes}, {'case': 'no_implicit_long_term_preference', 'status': 'passed'}]
        report['execution_status'] = 'finished'
    except Exception as exc:
        report['execution_status'] = 'failed'
        report['exception'] = str(exc)
        raise
    finally:
        save()
        client.close()
        fixture.engine.dispose()
        with fixture.admin.begin() as db:
            db.execute(text(f'DROP SCHEMA {fixture.schema} CASCADE'))
        fixture.admin.dispose()


if __name__ == '__main__':
    main()
