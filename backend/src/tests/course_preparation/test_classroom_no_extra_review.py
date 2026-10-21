from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.chat.harness.reviewed_resource import review_classroom, verified_resource
from app.course_preparation.quality import QualityStages
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.tool_registry import digest
from tests.course_preparation.test_openmaic_native_integration import native_scene
from tests.course_preparation.test_generation_adapter import generation


class NoModel:
    def chat(self, *args, **kwargs):
        raise AssertionError('extra classroom model call')

    def for_phase(self, *args, **kwargs):
        raise AssertionError('extra classroom model session')


def test_structure_receipt_is_explicit_and_invalidates_on_content_or_metadata_change():
    content = native_scene('interactive', {'html': '<button>观察</button>'})
    original = deepcopy(content)
    result, receipt = review_classroom(content, {}, gateway=NoModel())
    assert result == original and receipt['decision'] == 'skipped'
    assert receipt['method'] == 'structural_validation'
    assert 'checks' not in receipt and 'scene_checks' not in receipt
    artifact = {**result, 'generation_state': {'resource_review': receipt}}
    assert verified_resource(artifact, 'classroom')
    changed = deepcopy(artifact)
    changed['scenes'][0]['content']['html'] = '<button>改变</button>'
    assert not verified_resource(changed, 'classroom')
    changed = deepcopy(artifact)
    changed['generation_state']['preparation'] = {'changed': True}
    assert not verified_resource(changed, 'classroom')
    changed = deepcopy(artifact)
    changed['generation_state']['resource_review']['policy'] = 'unknown'
    assert not verified_resource(changed, 'classroom')


def test_disabling_classroom_review_does_not_allow_malformed_classrooms_or_unreviewed_quizzes():
    with pytest.raises((ValueError, TypeError)):
        review_classroom({'stage': {}, 'scenes': []}, {}, gateway=NoModel())
    assert not verified_resource({'content': {'questions': []}, 'generation_state': {
        'resource_review': {'decision': 'skipped', 'method': 'structural_validation'}}}, 'quiz')


@pytest.mark.parametrize('with_report', [False, True])
@pytest.mark.parametrize('excluded_kind', ['classroom', 'quiz'])
def test_course_gates_exclude_classrooms_and_quizzes_from_model_repairs(monkeypatch, with_report, excluded_kind):
    import app.course_preparation.quality as module
    monkeypatch.setattr(module.ResearchState, 'model_validate', lambda _: SimpleNamespace(path={}))
    monkeypatch.setattr(module.ResearchAgent, '_validate_path', lambda *_: None)
    monkeypatch.setattr(module, 'candidate_manifest', lambda *_: SimpleNamespace(model_dump=lambda **_: {}))
    kinds = [excluded_kind, *(['report'] if with_report else [])]
    artifacts = []
    for kind in kinds:
        spec = {'node_id': 'n', 'resource_type': kind, 'objectives': ['理解']}
        artifacts.append({'artifact_id': kind, 'resource_type': kind, 'status': 'draft',
            'spec': spec, 'spec_digest': digest(spec), 'content_digest': digest(kind),
            'content': {'content': 'EXCLUDED_BODY_NEVER_REVIEW' * 100000 if kind == excluded_kind else '报告正文'}})
    specs = [a['spec'] for a in artifacts]
    checkpoint = {'research_state': {}, 'resource_specs': specs,
        'generation_receipts': {digest(spec): {'index': i} for i, spec in enumerate(specs)},
        'brief': {}, 'plan': {'nodes': [{'node_key': 'n'}]}, 'node_evidence': {'n': []}}
    calls = []
    class Model:
        def decide(self, context, tools, **kwargs):
            calls.append(context)
            assert with_report
            assert all(a['kind'] != excluded_kind for a in context['artifacts'])
            assert 'EXCLUDED_BODY_NEVER_REVIEW' not in str(context)
            assert context['allowed_artifact_ids'] == ['resource_1']
            assert context['classroom_review_policy']
            assert any(row['resource_type'] == excluded_kind and row['available']
                       and row['content_review'] == 'skipped' for row in context['resource_inventory'])
            return 'review_course_delivery', {'decision': 'pass', 'checked_node_ids': ['n']}
    def factory(*_):
        assert with_report, 'classroom-only course must not construct a review model'
        return SimpleNamespace(model=Model())
    request = PreparationRequest(request_id=uuid4(), operation='create_course', goal='学习')
    stages = QualityStages(SimpleNamespace(get=lambda **_: SimpleNamespace(request=request)),
        SimpleNamespace(read_result=lambda _, r: artifacts[r['index']]),
        SimpleNamespace(validate=lambda *_: None), factory)
    ctx = SimpleNamespace(checkpoint=checkpoint, owner_user_id='alice', preparation_id='prep')
    first = stages.review(ctx)
    ctx.checkpoint = first.checkpoint
    final = stages.review(ctx)
    assert final.next_stage == 'commit'
    assert final.checkpoint['quality']['classroom_content_review'] == 'skipped'
    assert final.checkpoint['quality']['quiz_content_review'] == 'skipped'
    assert len(calls) == (2 if with_report else 0)


def test_policy_recovery_reuses_private_candidate_and_original_budget_across_parent_retry(generation):
    from tests.course_preparation.test_generation_adapter import spec
    from app.course_preparation.runtime_contracts import BudgetCost
    repo, parent, adapter = generation
    specification = {**spec(), 'resource_type': 'classroom'}
    action = repo.begin_action(parent, 'classroom', 'generate_resource', specification, BudgetCost(calls=1))
    receipt = adapter.submit(parent, specification, action['action_id'])
    child = adapter.artifacts.claim('alice', receipt['artifact_id'])
    content = native_scene('interactive', {'html': '<button>观察</button>'})
    port = adapter.artifacts.checkpoint_port(child)
    port.save_review_candidate(content=content, content_digest=digest(content), spec_digest=child['spec_digest'],
        review_state={'generator': 'openmaic-native', 'teaching_context_digest': digest(None)})
    adapter.artifacts.fail(child, {'code': 'CONTEXT_BUDGET_EXCEEDED', 'phase': 'resource_review',
        'category': 'budget', 'retry_scope': 'none', 'message': 'old review exceeded context'})
    repo.cancel('alice', parent.preparation_id)
    before = repo.get_public('alice', parent.preparation_id)['budget']
    repo.retry('alice', parent.preparation_id)
    next_parent = repo.claim('next-worker', preparation_id=parent.preparation_id)
    resumed = adapter.resume_classroom_delivery(next_parent, child['artifact_id'])
    assert adapter.resume_classroom_delivery(next_parent, child['artifact_id']) == resumed
    next_child = adapter.artifacts.claim('alice', child['artifact_id'])
    saved = adapter.artifacts.checkpoint_port(next_child).load_review_candidate()
    assert saved['content'] == content
    assert saved['parent_attempt_no'] == next_parent.attempt_no
    assert adapter.task_store.get_durable(resumed['job_id']).command == {'artifact_id': child['artifact_id'], 'resource_type': 'classroom'}
    after = repo.get_public('alice', parent.preparation_id)['budget']
    assert {k: after[k] for k in ('limits', 'consumed', 'reserved')} == {k: before[k] for k in ('limits', 'consumed', 'reserved')}
    assert after['deadline'] >= before['deadline']
    from app.course_preparation.lifecycle_repository import StaleLease
    with pytest.raises(StaleLease):
        adapter.artifacts.checkpoint_port(child).load_review_candidate()
