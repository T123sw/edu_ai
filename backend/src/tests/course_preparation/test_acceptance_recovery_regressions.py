"""Observed September 21 failures, with provider responses scripted explicitly."""
import copy
import json
from types import SimpleNamespace

import pytest

from app.course_preparation.lifecycle_repository import StaleLease
from app.course_preparation.runtime_contracts import BudgetCost
from app.course_preparation.tool_registry import digest
from app.course_preparation.quality import QualityStages
from tests.course_preparation.test_runtime_foundation import repo, request
from app.chat.harness.reviewed_resource import review_classroom as real_classroom_review


@pytest.mark.parametrize('terminal', ['canceled', 'failed', 'retried'])
def test_started_model_usage_settles_after_terminal_without_reopening_task(runtime_engine, terminal):
    service = repo(runtime_engine)
    service.submit('alice', request())
    context = service.claim('worker')
    action = service.begin_action(context, 'provider:observed', 'model_completion', {'model': 'test'},
                                  BudgetCost(calls=1, tokens=100))
    if terminal == 'failed':
        service.fail(context, 'PROVIDER_UNAVAILABLE')
    else:
        service.cancel('alice', context.preparation_id)
    if terminal == 'retried':
        service.retry('alice', context.preparation_id)
    for field, value in [('owner_user_id', 'bob'), ('lease_token', 'wrong-worker')]:
        with pytest.raises((StaleLease, PermissionError)):
            service.finish_action(context.model_copy(update={field: value}), action['action_id'], {}, BudgetCost(calls=1, tokens=40))
    receipt = {'usage': 40}
    service.finish_action(context, action['action_id'], receipt, BudgetCost(calls=1, tokens=40))
    service.finish_action(context, action['action_id'], receipt, BudgetCost(calls=1, tokens=40))
    state = service.get_public('alice', context.preparation_id)
    assert state['status'] == {'canceled': 'canceled', 'failed': 'failed', 'retried': 'accepted'}[terminal]
    assert state['result_ref'] is None
    assert state['budget']['reserved']['tokens'] == 0
    assert state['budget']['consumed']['tokens'] == 40
    with pytest.raises(StaleLease):
        service.checkpoint(context, {'late_content': 'must not save'})


def test_two_format_recoveries_leave_a_bounded_content_repair_with_actual_feedback():
    spec = {'node_id': 'n', 'revision': 1}
    artifact = {'artifact_id': 'quiz', 'spec_digest': digest(spec),
                'content': {'_review_candidate': {'content': {'questions': ['unchanged']}}}}
    cp = {'resource_specs': [spec], 'artifacts': [artifact], 'generation_receipts': {digest(spec): {}},
          'quality': {'issues': [{'artifact_ids': ['quiz'], 'reason': 'REVIEW_INVALID'}]}}
    stages = QualityStages(None, SimpleNamespace(resume_review=lambda *a, **k: {'job_id': k['recovery_key']}),
                           SimpleNamespace(validate=lambda *_: None), None)
    context = SimpleNamespace(checkpoint=cp, preparation_id='prep')
    for category, scope, message in [('review_format', 'review', 'question_index=5 expected option_indices=[]'),
                                     ('review_format', 'review', 'question_index=6 expected option_indices=[]'),
                                     ('content', 'content', '第3题缺少对用户选项的解释')]:
        artifact['failure_detail'] = {'code': 'REVIEW_INVALID', 'phase': 'resource_review', 'category': category,
                                      'retry_scope': scope, 'message': message}
        context.checkpoint['artifacts'] = [copy.deepcopy(artifact)]
        context.checkpoint['quality'] = cp['quality']
        context.checkpoint = stages.repair(context).checkpoint
    revised = context.checkpoint['resource_specs'][0]
    assert revised['revision'] == 2
    assert any('缺少对用户选项' in s for s in revised['revision_feedback'])
    assert revised['original_content'] == {'questions': ['unchanged']}
    assert context.checkpoint['repair_counts'] == {'review': 2, 'content': 1}
    from app.course_preparation.research_agent import ResearchError
    for number in (2, 3):
        artifact['spec_digest'] = digest(context.checkpoint['resource_specs'][0])
        context.checkpoint['artifacts'] = [copy.deepcopy(artifact)]
        context.checkpoint['quality'] = cp['quality']
        if number == 3:
            with pytest.raises(ResearchError, match='QUALITY_GATE_FAILED'):
                stages.repair(context)
        else:
            context.checkpoint = stages.repair(context).checkpoint


def test_quiz_review_resume_keeps_body_and_delivers_precise_format_feedback():
    from app.chat.harness.reviewed_resource import ReviewedResourceGenerator
    from app.course_preparation.generation_failures import GenerationFailure
    from tests.course_preparation.test_generated_content_constraints import quiz_envelope, completion_review
    from tests.course_preparation.test_classroom_teaching_contract import Checkpoint
    checkpoint = Checkpoint()
    calls = {'writer': 0, 'review': 0}
    class Gateway:
        def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]['content'])
            if 'schema' not in data:
                calls['writer'] += 1
                return json.dumps(quiz_envelope()['content'])
            calls['review'] += 1
            result = completion_review(data, 'quiz')
            if calls['review'] == 1:
                result['question_checks'][0]['option_checks'] = []
            else:
                assert 'question_index=0' in data['specification']['review_format_feedback']
                assert 'expected=' in data['specification']['review_format_feedback']
            return json.dumps(result)
    payload = SimpleNamespace(resource_type='quiz', title='职责', spec_digest='s')
    gateway = Gateway()
    def run():
        return ReviewedResourceGenerator(gateway, checkpoint=checkpoint).generate(payload, job_id='j', config_snapshot_id='c')
    with pytest.raises(GenerationFailure): run()
    before = checkpoint.candidate['content_digest']
    assert 'question_index=0' in checkpoint.candidate['review_state']['review_format_error']
    run()
    assert calls == {'writer': 1, 'review': 2}
    assert checkpoint.candidate['content_digest'] == before


def test_step_scene_mapping_covers_the_process_instead_of_only_intro_speech():
    from app.course_preparation.classroom_storyboard import ClassroomStoryboard, render_storyboard, storyboard_metadata
    from tests.course_preparation.test_classroom_teaching_contract import board_data
    board = ClassroomStoryboard.model_validate(board_data())
    body = render_storyboard(board, '课堂', 'r')
    metadata = storyboard_metadata(board, body)
    location = metadata['objective_bindings'][0]['locator']
    assert location == {'scene_id': 'r:example'}


def test_binding_format_feedback_names_missing_locations_for_repeated_objective():
    from app.chat.harness.preparation_content import validate_preparation_review
    metadata = {'applied_requirements': [], 'objective_bindings': [
        {'objective_id': 'o1', 'locator': {'section_id': section}} for section in ('s1', 's2', 's3')]}
    checks = [SimpleNamespace(binding_type='objective_id', binding_id='o1', locator={'section_id': 's1'})]
    with pytest.raises(ValueError) as error:
        validate_preparation_review('', 'report', metadata, checks)
    details = json.loads(str(error.value).split(': ', 1)[1])
    assert len(details['missing']) == 2 and details['extra'] == []
    assert {json.loads(item)[2]['section_id'] for item in details['missing']} == {'s2', 's3'}
