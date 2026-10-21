import json

import pytest
from sqlalchemy.orm import Session

from app.database.models import PreparationArtifact
from app.course_preparation.failure_explanation import explain
from app.course_preparation.contracts import PreparationNotFound
from app.course_preparation.runtime_contracts import BudgetCost
from app.course_preparation.tool_registry import digest
from tests.course_preparation.test_generation_adapter import generation, spec


@pytest.mark.parametrize('code,expected', [
    ('CONTEXT_BUDGET_EXCEEDED', '单次处理上限'),
    ('DEADLINE_EXCEEDED', '时间上限'),
    ('BUDGET_EXHAUSTED:cost_micro_usd', '生成额度'),
    ('RESOURCE_CONTENT_REJECTED', '前后不一致'),
    ('MODEL_UNAVAILABLE', '响应超时'),
    ('private provider stack trace with api-key', '没有足够信息'),
])
def test_allowlisted_human_explanations_never_echo_internal_errors(code, expected):
    title, reason, action = explain(code, 'review')
    assert expected in reason
    assert title and action and code not in title + reason + action


def test_public_failure_includes_all_current_resources_but_not_raw_details(generation):
    repo, parent, adapter = generation
    specs = [{**spec(), 'title': f'内容 {i}'} for i in range(5)]
    codes = [None, 'CONTEXT_BUDGET_EXCEEDED', 'BUDGET_EXHAUSTED', 'RESOURCE_CONTENT_REJECTED', 'MODEL_UNAVAILABLE']
    for value, code in zip(specs, codes):
        action = repo.begin_action(parent, digest(value), 'generate_resource', value, BudgetCost(calls=1))
        receipt = adapter.submit(parent, value, action['action_id'])
        repo.finish_action(parent, action['action_id'], receipt)
        with Session(repo.engine) as session, session.begin():
            artifact = session.get(PreparationArtifact, receipt['artifact_id'])
            artifact.status = 'failed' if code else 'draft'
            artifact.error_code = code
            artifact.content = {'_failure_detail': {'code': code, 'phase': 'resource_write',
                'budget_metric': 'cost_micro_usd', 'message': 'PRIVATE PROVIDER TRACE sk-secret'}} if code else {'content': 'saved'}
    # Last artifact belongs to an obsolete spec, and must not reappear.
    repo.checkpoint(parent, {'resource_specs': specs[:-1]})
    assert repo.get_public('alice', parent.preparation_id)['failure'] is None
    repo.fail(parent, 'CONTEXT_BUDGET_EXCEEDED')
    public = repo.get_public('alice', parent.preparation_id)
    failure = public['failure']
    assert failure['planned_resources'] == 4 and failure['saved_resources'] == 1
    assert len(failure['resource_issues']) == 3
    assert '生成额度不足' in failure['reason'] and '部分学习内容仍需修正' in failure['reason']
    assert any('预留费用' in issue['reason'] for issue in failure['resource_issues'])
    text = json.dumps(failure, ensure_ascii=False)
    assert 'PRIVATE' not in text and 'sk-secret' not in text and 'MODEL_UNAVAILABLE' not in text
    assert '内容 4' not in text and 'CONTEXT_BUDGET_EXCEEDED' not in text
    with pytest.raises(PreparationNotFound):
        repo.get_public('bob', parent.preparation_id)


def test_unknown_failure_has_safe_fallback_without_resources(generation):
    repo, parent, _ = generation
    repo.fail(parent, 'INTERNAL_PRIVATE_ERROR')
    failure = repo.get_public('alice', parent.preparation_id)['failure']
    assert '没有足够信息' in failure['reason']
    assert failure['resource_issues'] == [] and failure['saved_resources'] == 0


@pytest.mark.parametrize('exception,expected', [
    (ValueError('PRIVATE TRACE'), '本次操作未能完成'),
    (ValueError('ONLY_TERMINAL_FAILURE_CAN_RETRY'), '当前不能重试'),
])
def test_control_errors_are_readable(exception, expected):
    from app.api.course_preparations import execute
    from fastapi import HTTPException
    def action():
        raise exception
    with pytest.raises(HTTPException) as caught:
        execute(action)
    assert expected in caught.value.detail
    assert str(exception) not in caught.value.detail
