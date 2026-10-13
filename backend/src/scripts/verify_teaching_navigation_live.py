"""Real-model acceptance for question switching and exact-version report retrieval."""
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
    output = Path(__file__).resolve().parents[3] / 'docs/acceptance/2026-10-13-teaching-navigation/live.json'
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
        put('b', 'quiz', 'arithmetic', {'title': '算术练习', 'questions': [
            {'id': 'q1', 'type': 'single_choice', 'stem': 'Python 表达式 2 + 3 的结果是什么？',
             'options': ['4', '5', '6'], 'answer': 'B', 'explanation': '整数相加，结果为 5。'},
            {'id': 'q2', 'type': 'single_choice', 'stem': 'Python 表达式 2 * 3 的结果是什么？',
             'options': ['5', '6', '8'], 'answer': 'B', 'explanation': '整数相乘，结果为 6。'}]})
        svc.checks.generator = None
        svc.checks.model_json = real_json

        ask('located_second_question', '请解释这道题，给出结果。', 'b', 'quiz', 'arithmetic', locator={'kind': 'quiz', 'question_index': 1})
        ask('located_hint_first_question', '这次只给提示，不要告诉我结果。', 'b', 'quiz', 'arithmetic', locator={'kind': 'quiz', 'question_index': 0})
        put('long', 'report', 'long-guide', {'title': '递归长文', 'content': '# 基础\n\n' + ('背景介绍。\n\n' * 2000) + '递归终止条件是 n 等于零。满足这个条件时返回 1，不再调用自身。'})
        ask('late_passage_retrieval', '这份资料中递归终止条件是什么？满足后返回什么？简短回答。', 'long', 'report', 'long-guide')
        for case in report['cases']:
            assert case['response']['status'] == 'succeeded', case
        hint = report['cases'][1]['response']['result']['answer_markdown']
        assert '2 + 3' in hint and '5' not in hint, 'Switched question must receive an addition hint without the answer'
        citations = report['cases'][0]['response']['result']['citations']
        assert any(c['locator'] == {'kind': 'quiz', 'question_index': 1} for c in citations)
        citations = report['cases'][2]['response']['result']['citations']
        assert any(c['locator'].get('block_id', '').startswith('report-v1:') for c in citations)
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
