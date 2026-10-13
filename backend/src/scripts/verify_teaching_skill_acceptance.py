"""Opt-in real-model acceptance in disposable storage; saves answers for human review."""
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
    from tests.self_learning.test_classroom_context import material, playback

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
    output = Path(__file__).resolve().parents[3] / 'docs/acceptance/2026-10-13-teaching-skill/expanded-live.json'
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
            {'id': 'c', 'label': '历史记录'}, {'id': 'ppt', 'label': '条件与赋值'},
            {'id': 'long', 'label': '阅读长文'}, {'id': 'check', 'label': '变量理解检查'}]}})
        paragraph = '执行 x = 1 后，执行 y = x，再执行 x = 2。此时 x 为 2，y 仍为 1。变量名绑定对象，给 x 重新赋值不会自动改变 y 的绑定。'
        put('a', 'report', 'a-core', {'title': '变量学习指南', 'content': '# 变量与赋值\n\n' + paragraph})
        put('check', 'report', 'check-guide', {'title': '变量检查资料', 'content': '# 变量\n\n' + paragraph})
        put('b', 'quiz', 'arithmetic', {'title': '算术练习', 'questions': [
            {'id': 'q1', 'type': 'single_choice', 'stem': 'Python 表达式 2 + 3 的结果是什么？',
             'options': ['4', '5', '6'], 'answer': 'B', 'explanation': '整数相加，结果为 5。'},
            {'id': 'q2', 'type': 'single_choice', 'stem': 'Python 表达式 2 * 3 的结果是什么？',
             'options': ['5', '6', '8'], 'answer': 'B', 'explanation': '整数相乘，结果为 6。'}]})
        put('ppt', 'classroom', 'slides', material())
        long_text = ('变量名绑定对象。' * 1249) + '验收口令是蓝鲸。'
        assert len(long_text) == 10000
        put('long', 'report', 'long-guide', {'title': '长引用资料', 'content': long_text})
        svc.checks.generator = None
        svc.checks.model_json = real_json

        entered = request('POST', course + 'a/enter')
        first = ask('selected_explanation', '请解释这段内容，简短一点，不用检查理解。', selected_text=paragraph)
        ask('followup_new_example', '用苹果和橘子的例子再解释一次，保持简短。')
        # Same topic, different resource must retain its session.
        ask('same_topic_other_resource', '刚才我们用了哪两种水果作例子？只回答水果名。', mid='a-extra')
        ask('quiz_ambiguous', '这道题怎么做？', 'b', 'quiz', 'arithmetic')
        ask('quiz_hint', '第一题我不会，只给一个提示，不要告诉我结果或选项。', 'b', 'quiz', 'arithmetic',
            selected_text='Python 表达式 2 + 3 的结果是什么？')
        ask('quiz_full_solution', '现在给我第一题的完整解析和答案。', 'b', 'quiz', 'arithmetic')
        ask('ppt_view_and_narration', '我现在看的哪一页？刚才讲到哪一句？你能看清图片里的细节吗？请简短回答。',
            'ppt', 'classroom', 'slides', locator={'kind': 'classroom', 'scene_id': 'two'}, classroom=playback())
        ask('long_selected_text', '引用末尾的验收口令是什么？只回答口令。', 'long', 'report', 'long-guide', selected_text=long_text)
        ask('voluntary_check', '请出一道理解检查题让我做，我希望可以跳过。不要先告诉我答案。',
            'check', 'report', 'check-guide')
        cards = request('GET', course + 'check/checks')['items']
        assert cards, 'Agent did not create requested understanding check'
        card = cards[-1]
        assert 'correct_option_ids' not in card['public_question'] and 'reference_answer' not in card['public_question']
        attempt = request('POST', prefix + '/checks/' + card['check_id'] + '/attempts',
            {'request_id': str(uuid4()), 'question_version': card['question_version'], 'skipped': True})
        assert attempt['status'] == 'skipped' and not attempt['evidence_refs']
        report['api_checks'].append({'case': 'skip_generated_check', 'status': 'passed', 'card': card, 'attempt': attempt})
        after = request('POST', course + 'a/enter')
        assert after['session_id'] == entered['session_id']
        assert len(after['items']) > len(entered['items'])
        other = request('POST', course + 'b/enter')
        assert other['session_id'] != after['session_id']
        assert '苹果' not in json.dumps(other['items'], ensure_ascii=False)
        request('GET', prefix + '/agent-turns/' + first['turn_id'], expected=404, headers={'Authorization': 'Bearer bob'})
        report['api_checks'].append({'case': 'session_restore_topic_and_owner_isolation', 'status': 'passed'})
        facts = svc.progress_service.repository.read('alice', 'learning-fixture')
        assert all(not r.get('completed') for r in facts['resources'])
        report['api_checks'].append({'case': 'questions_and_skip_do_not_mark_reading_complete', 'status': 'passed'})
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
