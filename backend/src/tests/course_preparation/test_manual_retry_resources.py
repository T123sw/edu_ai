from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.database.models import PreparationArtifact, CoursePreparationAttemptRecord, PreparationExecution
from app.course_preparation.lifecycle_repository import StaleLease
from app.course_preparation.production_stages import ProductionStages
from app.course_preparation.runtime_contracts import BudgetCost
from app.course_preparation.tool_registry import digest
from tests.course_preparation.test_generation_adapter import generation, spec


@pytest.mark.parametrize('incomplete_status', ['failed', 'running', 'pending'])
def test_retry_keeps_completed_draft_and_schedules_only_incomplete_resource(generation, incomplete_status):
    repo, parent, adapter = generation
    now = [datetime.now(timezone.utc)]
    repo.clock = lambda: now[0]
    specifications = [spec(), {**spec(), 'resource_type': 'classroom'}]
    receipts, artifacts = {}, []
    for value in specifications:
        key = digest(value)
        action = repo.begin_action(parent, 'generation:' + key, 'generate_resource', value, BudgetCost(calls=1))
        receipt = adapter.submit(parent, value, action['action_id'])
        repo.finish_action(parent, action['action_id'], receipt)
        receipts[key] = receipt
        artifacts.append(receipt['artifact_id'])
    child = adapter.artifacts.claim('alice', artifacts[1]) if incomplete_status != 'pending' else None
    action = (adapter.artifacts.begin_action(child, 'inflight', 'model_completion', {}, BudgetCost(calls=1, tokens=100))
              if child and incomplete_status == 'running' else None)
    if incomplete_status == 'failed':
        adapter.artifacts.fail(child, 'BUDGET_EXHAUSTED')
    body = {'content': 'completed report'}
    with Session(repo.engine) as session, session.begin():
        draft = session.get(PreparationArtifact, artifacts[0])
        draft.status, draft.content, draft.content_digest = 'draft', body, digest(body)
        session.get(CoursePreparationAttemptRecord, (parent.preparation_id, 1)).stage = 'produce'
    checkpoint = {'resource_specs': specifications, 'generation_receipts': receipts,
        'research_summary': {'findings': ['original source']}, 'node_evidence': {'n': ['original quote']}}
    repo.checkpoint(parent, checkpoint)
    repo.fail(parent, 'DEADLINE_EXCEEDED')
    before = repo.get_public('alice', parent.preparation_id)['budget']
    now[0] += timedelta(hours=2)
    retried = repo.retry('alice', parent.preparation_id)
    current = repo.claim('next-worker', preparation_id=parent.preparation_id)
    assert current.stage == 'produce'
    assert current.checkpoint['research_summary'] == checkpoint['research_summary']
    assert current.checkpoint['node_evidence'] == checkpoint['node_evidence']
    assert current.checkpoint['resource_specs'][0] == specifications[0]
    assert current.checkpoint['resource_specs'][1]['revision'] == 2
    assert current.checkpoint['generation_receipts'] == {digest(specifications[0]): receipts[digest(specifications[0])]}
    for key in ('consumed', 'reserved', 'limits'):
        assert retried['budget'][key] == before[key]
    with Session(repo.engine) as session:
        assert session.get(PreparationExecution, (parent.preparation_id, 1)).checkpoint == checkpoint
    with pytest.raises(StaleLease, match='SUPERSEDED'):
        adapter.artifacts.claim('alice', artifacts[1])
    if child:
        with pytest.raises(StaleLease):
            adapter.artifacts.save(child, {'content': 'late response'})
    if action:
        adapter.artifacts.finish_action(child, action['action_id'], {}, BudgetCost(calls=1, tokens=40))
        assert repo.get_public('alice', parent.preparation_id)['budget']['consumed']['tokens'] == 40
    stages = ProductionStages(repo, adapter, SimpleNamespace(validate=lambda *_: None))
    # Readback validation of generated bodies is covered elsewhere; isolate scheduling.
    original_reader = adapter.read_result
    adapter.read_result = lambda owner, receipt: adapter.artifacts.get(owner, receipt['artifact_id'])
    result = stages.produce(current)
    new_key = digest(current.checkpoint['resource_specs'][1])
    new_receipt = result.checkpoint['generation_receipts'][new_key]
    job = adapter.task_store.get_durable(new_receipt['job_id'])
    assert new_receipt['artifact_id'] != artifacts[1]
    assert job.deadline_at == datetime.fromisoformat(retried['budget']['deadline']).timestamp()
    assert adapter.artifacts.get('alice', artifacts[0], content=True)['content'] == body
    assert stages.produce(current).checkpoint['generation_receipts'][new_key] == new_receipt
    adapter.read_result = original_reader


def test_retry_rejects_tampered_completed_artifact_atomically(generation):
    repo, parent, adapter = generation
    value = spec()
    action = repo.begin_action(parent, 'generation:' + digest(value), 'generate_resource', value, BudgetCost(calls=1))
    receipt = adapter.submit(parent, value, action['action_id'])
    repo.checkpoint(parent, {'resource_specs': [value], 'generation_receipts': {digest(value): receipt}})
    with Session(repo.engine) as session, session.begin():
        artifact = session.get(PreparationArtifact, receipt['artifact_id'])
        artifact.status, artifact.content, artifact.content_digest = 'draft', {'content': 'tampered'}, 'wrong'
    repo.fail(parent, 'PROVIDER_TIMEOUT')
    before = deepcopy(repo.get_public('alice', parent.preparation_id))
    with pytest.raises(ValueError, match='ARTIFACT_CONTENT_MISMATCH'):
        repo.retry('alice', parent.preparation_id)
    assert repo.get_public('alice', parent.preparation_id) == before


@pytest.mark.parametrize('sibling_submitted', [True, False])
def test_node_retry_only_submits_target_and_does_not_enter_global_repair(generation, sibling_submitted):
    from app.course_preparation.research_agent import ResearchError
    repo, parent, adapter = generation
    specifications = [spec(), {**spec(), 'node_id': 'next', 'objective_ids': ['next:o1']}]
    receipts = {}
    for value in specifications[:2 if sibling_submitted else 1]:
        key = digest(value)
        action = repo.begin_action(parent, 'generation:' + key, 'generate_resource', value, BudgetCost(calls=1))
        receipt = adapter.submit(parent, value, action['action_id'])
        repo.finish_action(parent, action['action_id'], receipt)
        receipts[key] = receipt
        child = adapter.artifacts.claim('alice', receipt['artifact_id'])
        adapter.artifacts.fail(child, 'PROVIDER_TIMEOUT')
    repo.checkpoint(parent, {'resource_specs': specifications, 'generation_receipts': receipts})
    repo.fail(parent, 'RESOURCE_GENERATION_FAILED')
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import course_preparations as api
    from app.course_preparation.service import PreparationService
    app = FastAPI()
    app.include_router(api.router)
    app.state.preparation_service = PreparationService(repo)
    app.dependency_overrides[api.owner] = lambda: 'alice'
    response = TestClient(app).post(f'/api/course-preparations/{parent.preparation_id}/retry', json={'node_id': 'tools'})
    assert response.status_code == 202, response.text
    current = repo.claim('retry-one', preparation_id=parent.preparation_id)
    assert current.checkpoint['resource_specs'][1] == specifications[1]
    stages = ProductionStages(repo, adapter, SimpleNamespace(validate=lambda *_: None))
    adapter.read_result = lambda owner, receipt: adapter.artifacts.get(owner, receipt['artifact_id'])
    first = stages.produce(current)
    new_spec = first.checkpoint['resource_specs'][0]
    assert new_spec['revision'] == 2
    target = first.checkpoint['generation_receipts'][digest(new_spec)]
    assert len(first.checkpoint['generation_receipts']) == (2 if sibling_submitted else 1)
    child = adapter.artifacts.claim('alice', target['artifact_id'])
    adapter.artifacts.save(child, {'content': 'completed target'})
    current = current.model_copy(update={'checkpoint': first.checkpoint})
    with pytest.raises(ResearchError, match='本次知识点重试已结束'):
        stages.produce(current)
    assert adapter.artifacts.get('alice', target['artifact_id'])['status'] == 'draft'


def test_node_retry_rejects_unknown_node_before_creating_attempt(generation):
    repo, parent, _ = generation
    repo.checkpoint(parent, {'resource_specs': [spec()]})
    repo.fail(parent, 'PROVIDER_TIMEOUT')
    with pytest.raises(ValueError, match='RETRY_NODE_UNAVAILABLE'):
        repo.retry('alice', parent.preparation_id, node_id='unknown')
    assert repo.get_public('alice', parent.preparation_id)['attempt_no'] == 1


def test_retry_preserves_failed_candidate_and_specific_feedback(generation):
    from tests.course_preparation.test_review_resume import candidate, failure
    repo, parent, store, child, body = candidate(generation)
    value = deepcopy(child['spec'])
    port = store.checkpoint_port(child)
    port.save_review_candidate(content=body, content_digest=digest(body), spec_digest=child['spec_digest'],
        review_state={'needs_repair': True, 'feedback': ['第六题正确答案应为 A、B、C']})
    store.fail(child, failure(child, 'content'))
    repo.checkpoint(parent, {'resource_specs': [value], 'generation_receipts': {}})
    repo.fail(parent, 'RESOURCE_CONTENT_REJECTED')
    repo.retry('alice', parent.preparation_id)
    next_context = repo.claim('retry-worker', preparation_id=parent.preparation_id)
    revised = next_context.checkpoint['resource_specs'][0]
    assert revised['original_content'] == body
    assert '第六题正确答案应为 A、B、C' in revised['revision_feedback']
    assert revised['revision'] == value.get('revision', 1) + 1


def test_explicit_path_retry_keeps_evidence_but_renews_bounded_repair_attempt():
    from app.course_preparation.manual_retry import prepare_retry_checkpoint
    checkpoint = {'research_state': {'repairs': 2, 'review': {'issues': ['原先修审阅冲突']}, 'evidence': ['saved']},
                  'node_research_repairs': 2}
    updated, stage, _ = prepare_retry_checkpoint(None, None, SimpleNamespace(stage='plan'), checkpoint)
    assert updated['research_state']['repairs'] == 0
    assert updated['research_state']['review'] == checkpoint['research_state']['review']
    assert updated['research_state']['evidence'] == ['saved']
    assert checkpoint['research_state']['repairs'] == 2 and stage == 'plan'
