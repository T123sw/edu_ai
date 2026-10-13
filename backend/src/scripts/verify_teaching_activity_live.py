"""Opt-in real-model checks, exclusively in the disposable browser fixture schema."""
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4


def main():
    if os.getenv('LEARNING_LIVE_ACCEPTANCE') != '1':
        raise SystemExit('Set LEARNING_LIVE_ACCEPTANCE=1 for real model calls.')
    test_url = os.environ['LEARNING_TEST_DATABASE_URL']
    from app.services.runtime_config_resolver import runtime_config_resolver
    config = runtime_config_resolver.resolve('llm')
    os.environ['LEARNING_TEST_DATABASE_URL'] = test_url
    for name in ('LEARNING_SESSION_V1_ENABLED', 'LEARNING_PROGRESS_V1_ENABLED', 'LEARNING_AGENT_V1_ENABLED',
                 'LEARNING_ENRICHMENT_V1_ENABLED', 'LEARNING_PREPARATION_V1_ENABLED', 'LEARNING_SCOPED_ROLLOUT', 'COURSE_PREPARATION_ENABLED'):
        os.environ[name] = 'false'
    os.environ.update(LEARNING_BROWSER_AGENT='1', LEARNING_BROWSER_ENRICHMENT='1', LEARNING_BROWSER_REAL='0', LEARNING_BROWSER_PREPARATION='0')
    from tests.self_learning import browser_app as fixture
    from app.self_learning.agent_runtime import LearningAgentRuntime
    from app.self_learning.model_adapter import LearningModelAdapter
    from app.self_learning.turn_contracts import AnswerRequest
    from app.self_learning.check_service import CheckSubmission
    from sqlalchemy import text
    svc = fixture.svc
    runtime = LearningAgentRuntime(svc, svc.turn_repository, lambda _: LearningModelAdapter.from_config(config))
    output = Path(__file__).resolve().parents[3] / 'docs/acceptance/2026-10-13-teaching-activities/live.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'model': config['model'], 'storage': 'isolated disposable PostgreSQL schema', 'cases': []}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    try:
        svc.manager.save_generated_material('learning-fixture', 'quiz', 'coaching-quiz', {
            'title': '变量和条件练习', 'learning_course_resource': True, 'questions': [
                {'stem': 'Python 中，哪一项把整数 3 赋给变量 x？', 'options': ['x = 3', 'x == 3'], 'answer': 'A', 'explanation': '= 赋值；== 比较。'},
                {'stem': '当 x = 3 时，表达式 x > 5 的值是什么？', 'options': ['True', 'False'], 'answer': 'B', 'explanation': '3 不大于 5，因此是 False。'}]},
            owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
        checks = svc.checks.material_checks('alice', 'learning-fixture', 'coaching-quiz', 1)['items']
        ref = checks[0]['source_ref']
        draft = svc.turns.accept('alice', 'learning-fixture', 'a', AnswerRequest(request_id=uuid4(),
            question='我暂时选第二项，只给我一个提示，不要公布答案。', reading_context={
                'resource_ref': ref, 'locator': {'kind': 'quiz', 'question_index': 0},
                'practice': {'check_id': checks[0]['check_id'], 'draft': {'option_ids': ['option_2']}}}))
        assert runtime.run_once()
        result = svc.turns.get('alice', draft['turn_id'])
        report['cases'].append({'case': 'unsubmitted_draft_hint', 'turn': result})
        save()
        assert result['status'] == 'succeeded', result['error_code']
        for index, option in [(0, 'option_2'), (1, 'option_2')]:
            check = checks[index]
            svc.checks.teaching.configure('alice', check['check_id'], True, 0)
            submitted = asyncio.run(svc.checks.submit('alice', check['check_id'], CheckSubmission(
                request_id=uuid4(), question_version=1, option_ids=[option])))
            assert runtime.run_once()
            state = svc.checks.teaching.view('alice', check['check_id'])
            result = svc.turns.get('alice', state['feedback']['turn_id'])
            report['cases'].append({'case': 'wrong_assignment_feedback' if index == 0 else 'switch_to_correct_comparison',
                                    'submitted': submitted, 'activity': state, 'turn': result})
            save()
            assert result['status'] == 'succeeded', result['error_code']
        report['status'] = 'completed_for_semantic_review'
        save()
        print(str(output))
    finally:
        fixture.engine.dispose()
        with fixture.admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS {fixture.schema} CASCADE'))
        fixture.admin.dispose()


if __name__ == '__main__':
    main()
