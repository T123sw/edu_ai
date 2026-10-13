"""Opt-in teaching checks with real provider calls and isolated learning storage.

Run with LEARNING_LIVE_ACCEPTANCE=1 and LEARNING_TEST_DATABASE_URL pointing at
the isolated test PostgreSQL instance. Never writes production conversations.
"""
import json
import os
from pathlib import Path
import time
from uuid import uuid4


def main():
    if os.getenv('LEARNING_LIVE_ACCEPTANCE') != '1':
        raise SystemExit('Set LEARNING_LIVE_ACCEPTANCE=1 for real model calls.')
    test_url = os.environ['LEARNING_TEST_DATABASE_URL']
    from app.services.runtime_config_resolver import runtime_config_resolver
    config = runtime_config_resolver.resolve('llm')
    # The fixture pins its own DB and file storage before constructing services.
    os.environ['LEARNING_TEST_DATABASE_URL'] = test_url
    for flag in ('LEARNING_SESSION_V1_ENABLED', 'LEARNING_PROGRESS_V1_ENABLED',
                 'LEARNING_AGENT_V1_ENABLED', 'LEARNING_ENRICHMENT_V1_ENABLED',
                 'LEARNING_PREPARATION_V1_ENABLED', 'LEARNING_SCOPED_ROLLOUT',
                 'COURSE_PREPARATION_ENABLED'):
        os.environ[flag] = 'false'
    for flag in ('LEARNING_BROWSER_AGENT', 'LEARNING_BROWSER_ENRICHMENT'):
        os.environ[flag] = '1'
    os.environ['LEARNING_BROWSER_PREPARATION'] = '0'
    from tests.self_learning import browser_app as fixture
    from sqlalchemy import text
    from app.self_learning.agent_runtime import LearningAgentRuntime
    from app.self_learning.model_adapter import LearningModelAdapter
    from app.self_learning.turn_contracts import AnswerRequest
    from tests.self_learning.test_classroom_context import material, playback

    svc = fixture.svc
    model = LearningModelAdapter.from_config(config)
    runtime = LearningAgentRuntime(svc, svc.turn_repository, lambda _: model)
    report = {'model': config['model'], 'mode': 'real model; synthetic materials and isolated learning database', 'cases': []}
    output = Path(__file__).resolve().parents[3] / 'docs/acceptance/2026-10-13-teaching-skill/live.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        svc.manager.save_course_info('learning-fixture', {
            'id': 'learning-fixture', 'title': '古诗文鉴赏', 'created_by': 'alice'})
        svc.manager.save_knowledge_graph('learning-fixture', {'root': {'id': 'root', 'children': [
            {'id': 'a', 'label': '诗歌意象与意境'}, {'id': 'b', 'label': '意象的表达作用'},
            {'id': 'c', 'label': '课堂阅读'}]}})
        generic = '# 核心概念\n\n## 定义的本质属性\n\n该概念是由主体、客体、机制构成的多维复合系统。标准定义是在特定约束条件下，系统内部各要素相互作用所产生的确定性规律。'
        good = '# 意象与意境\n\n意象是寄托诗人情感的具体物象；意境是诗中物象与情感共同形成的整体氛围。明月可以成为思乡的意象。不能仅凭出现月亮就断定思乡，还需联系全诗。'
        for node, mid, content in [('a', 'a-core', generic), ('b', 'b-core', good)]:
            svc.manager.save_generated_material('learning-fixture', 'report', mid,
                {'title': '学习指南', 'content': content, 'learning_course_resource': True},
                owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id=node)

        def ask(label, question, node='a', kind='report', mid='a-core', **snapshot):
            source = svc.material('learning-fixture', kind, mid, 'alice')
            req = AnswerRequest(request_id=uuid4(), question=question, reading_context={
                'resource_ref': {'course_id': 'learning-fixture', 'material_type': kind,
                                 'material_id': mid, 'version': source['version']}, **snapshot})
            turn = svc.turns.accept('alice', 'learning-fixture', node, req)
            start = time.monotonic()
            runtime.run_once()
            finished = svc.turns.get('alice', turn['turn_id'])
            case = {'case': label, 'question': question, 'status': finished['status'],
                    'seconds': round(time.monotonic() - start, 2), 'result': finished.get('result'),
                    'error_code': finished.get('error_code')}
            report['cases'].append(case)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(json.dumps({'case': label, 'status': finished['status']}, ensure_ascii=False), flush=True)
            assert finished['status'] == 'succeeded', case
            assert finished['result']['teaching_skill']['name'] == 'teach-current-topic'
            return finished['result']

        ask('generic_paragraph', '请解释这段内容。', selected_text=generic.split('\n\n')[-1])
        for label, question in [('course_followup', '我们现在在围绕着什么在提问'),
                                ('topic_followup', '围绕着哪个知识点')]:
            answer = ask(label, question)
            assert '古诗文鉴赏' in answer['answer_markdown'] and '诗歌意象与意境' in answer['answer_markdown']
        answer = ask('direct_explanation', '请简短解释意象与意境的区别，举一个例子，不用检查理解。', 'b', mid='b-core')
        assert not answer['suggested_action_ids']
        answer = ask('different_example', '换一个不使用月亮的例子。', 'b', mid='b-core')
        assert not answer['suggested_action_ids']
        slides = material()
        svc.manager.save_generated_material('learning-fixture', 'classroom', 'slides', slides,
            owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='c')
        answer = ask('viewed_vs_spoken', '我当前看的页和刚才讲解的位置分别是什么？你能看到图片细节吗？',
                     'c', 'classroom', 'slides', locator={'kind': 'classroom', 'scene_id': 'two'}, classroom=playback())
        assert answer['teaching_skill']['mode'] == 'classroom'
        report['status'] = 'passed'
        report['review_required'] = 'Inspect answers for pedagogy; structural assertions alone do not grade teaching quality.'
    finally:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        fixture.engine.dispose()
        with fixture.admin.begin() as db:
            db.execute(text(f'DROP SCHEMA {fixture.schema} CASCADE'))
        fixture.admin.dispose()


if __name__ == '__main__':
    main()
