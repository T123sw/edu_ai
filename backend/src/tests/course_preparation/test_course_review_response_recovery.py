from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.course_preparation.quality import QualityStages, check_digest
from app.course_preparation.research_agent import ResearchError
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.tool_registry import digest


@pytest.fixture
def review_harness(monkeypatch):
    import app.course_preparation.quality as module
    monkeypatch.setattr(module.ResearchState, 'model_validate', lambda _: SimpleNamespace(path={}))
    monkeypatch.setattr(module.ResearchAgent, '_validate_path', lambda *_: None)
    monkeypatch.setattr(module, 'candidate_manifest', lambda *_: SimpleNamespace(model_dump=lambda **_: {'checked': True}))
    specs = [{'node_id': key, 'objectives': [key]} for key in ('n1', 'n2')]
    ids = ['artifact_f8987f13585ca7b8ac878c13fc9bc78d', 'artifact_other_node']
    artifacts = [{'artifact_id': key, 'spec': spec, 'spec_digest': digest(spec), 'status': 'draft',
                  'content_digest': digest(key), 'resource_type': 'report', 'content': {'content': 'unchanged body'}}
                 for key, spec in zip(ids, specs)]
    cp = {'research_state': {}, 'resource_specs': specs, 'generation_receipts': {digest(spec): {'id': i} for i, spec in enumerate(specs)},
          'brief': {}, 'plan': {'nodes': [{'node_key': key} for key in ('n1', 'n2')]}, 'node_evidence': {'n1': [], 'n2': []}}
    state = SimpleNamespace(calls=[], response={'decision': 'pass', 'checked_node_ids': ['n1']}, tool='review_course_delivery', artifacts=artifacts, error=None)
    class Model:
        def decide(self, context, tools, **kwargs):
            state.calls.append((deepcopy(context), deepcopy(tools)))
            if state.error: raise state.error
            return state.tool, state.response
    request = PreparationRequest(request_id=uuid4(), operation='create_course', goal='学习')
    stage = QualityStages(SimpleNamespace(get=lambda **_: SimpleNamespace(request=request)),
                          SimpleNamespace(read_result=lambda owner, receipt: artifacts[receipt['id']]),
                          SimpleNamespace(validate=lambda *_: None), lambda *_: SimpleNamespace(model=Model()))
    context = SimpleNamespace(checkpoint=cp, owner_user_id='alice', preparation_id='prep')
    return stage, context, state


@pytest.mark.parametrize('invalid_id', ['artifact_f8987f13585ca7b8ac7c13fc9bc78d', 'artifact_other_node', 'resource_2'])
def test_invalid_or_foreign_reference_is_corrected_without_rewriting_or_guessing(review_harness, invalid_id):
    stage, context, state = review_harness
    original = deepcopy(state.artifacts)
    state.response = {'decision': 'fail', 'checked_node_ids': ['n1'], 'issues': [{'artifact_ids': [invalid_id], 'reason': '答案需修正'}]}
    result = stage.review(context)
    assert result.next_stage is None and 'quality' not in result.checkpoint
    assert result.checkpoint['review_schema_error']['code'] == 'COURSE_REVIEW_UNKNOWN_RESOURCE'
    context.checkpoint = result.checkpoint
    state.response = {**state.response, 'issues': [{'artifact_ids': ['resource_1'], 'reason': '答案需修正'}]}
    result = stage.review(context)
    assert result.next_stage == 'repair'
    assert result.checkpoint['quality']['issues'][0]['artifact_ids'] == [original[0]['artifact_id']]
    assert state.calls[-1][0]['last_schema_error']['allowed_artifact_ids'] == ['resource_1']
    assert state.artifacts == original


@pytest.mark.parametrize('failure,code', [('missing_node', 'COURSE_REVIEW_INCOMPLETE'), ('wrong_tool', 'COURSE_REVIEW_INVALID'), ('bad_reference', 'COURSE_REVIEW_UNKNOWN_RESOURCE')])
def test_invalid_review_is_bounded_across_persisted_steps(review_harness, failure, code):
    stage, context, state = review_harness
    if failure == 'missing_node': state.response['checked_node_ids'] = ['n2']
    if failure == 'wrong_tool': state.tool = 'some_other_tool'
    if failure == 'bad_reference': state.response.update(decision='fail', issues=[{'artifact_ids': ['unknown'], 'reason': 'wrong'}])
    for _ in range(2):
        result = stage.review(context)
        assert result.next_stage is None and 'candidate_manifest' not in result.checkpoint
        context.checkpoint = deepcopy(result.checkpoint)
    with pytest.raises(ResearchError) as caught:
        stage.review(context)
    assert caught.value.code == code
    assert len(state.calls) == 3


def test_short_ids_and_schema_are_scoped_to_current_node(review_harness):
    stage, context, state = review_harness
    stage.review(context)
    packet, tools = state.calls[0]
    assert [r['artifact_id'] for r in packet['artifacts']] == ['resource_1']
    schema = tools[0]['function']['parameters']
    assert schema['$defs']['DeliveryIssue']['properties']['artifact_ids']['items']['enum'] == ['resource_1']
    assert schema['properties']['checked_node_ids']['items']['enum'] == ['n1']


def test_correction_keeps_passed_nodes_and_resets_only_for_changed_inputs(review_harness):
    stage, context, state = review_harness
    context.checkpoint = stage.review(context).checkpoint
    state.response = {'decision': 'fail', 'checked_node_ids': ['n2'], 'issues': [{'artifact_ids': ['missing'], 'reason': 'bad'}]}
    for _ in range(2): context.checkpoint = stage.review(context).checkpoint
    assert 'n1' in context.checkpoint['node_quality_reviews']
    state.artifacts[1]['content']['content'] = 'new body'
    state.artifacts[1]['content_digest'] = digest('new body')
    # Changed content invalidates old review receipts and grants a fresh bounded correction cycle.
    state.response['checked_node_ids'] = ['n1']
    context.checkpoint = stage.review(context).checkpoint
    assert context.checkpoint['review_schema_repairs'] == {'n1': 1}
    assert context.checkpoint['review_schema_repair_digest'] == check_digest(context.checkpoint)


@pytest.mark.parametrize('code', ['PROVIDER_TIMEOUT', 'PROVIDER_UNAVAILABLE', 'HARNESS_UNAVAILABLE', 'HARNESS_SHUTDOWN_FAILED'])
def test_transient_review_failure_releases_worker_and_retries_only_twice(review_harness, code):
    stage, context, state = review_harness
    state.error = ResearchError(code, 'temporary')
    for wait in (5, 10):
        result = stage.review(context)
        assert result.wait_seconds == wait and result.next_stage is None
        assert 'quality' not in result.checkpoint
        context.checkpoint = deepcopy(result.checkpoint)
    with pytest.raises(ResearchError) as caught: stage.review(context)
    assert caught.value.code == code
    state.error = None
    assert 'n1' in stage.review(context).checkpoint['node_quality_reviews']


@pytest.mark.parametrize('error', [ResearchError('BUDGET_EXHAUSTED', 'budget'), PermissionError('revoked'), ValueError('programming bug')])
def test_budget_permission_and_programming_errors_are_not_retried(review_harness, error):
    stage, context, state = review_harness
    state.error = error
    with pytest.raises(type(error)): stage.review(context)
    assert 'review_provider_retry' not in context.checkpoint
