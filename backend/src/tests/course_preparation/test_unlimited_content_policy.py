"""User content is not a quota; delivery does not depend on classroom page labels."""
from copy import deepcopy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.research_contracts import ResearchBrief, Requirement, LearningPath
from app.course_preparation.quality import candidate_manifest
from app.course_preparation.resource_alignment import validate_artifact, node_requirement_issues
from app.course_preparation.tool_registry import digest
from tests.course_preparation.test_resource_alignment import quiz, checkpoint
from tests.course_preparation.test_harness_generation import content_skills, gateway, completion


def test_large_request_brief_and_path_survive_all_contracts():
    goal = '解释一个详细的学习需求。' * 1000
    request = PreparationRequest(request_id=uuid4(), operation='create_course', goal=goal)
    requirements = [Requirement(requirement_id=f'r{i}', text=goal, source_quote=goal) for i in range(30)]
    brief = ResearchBrief(topic=goal, audience='初学者', language='zh', total_minutes=100,
        node_count=30, learning_goal=goal, prior_knowledge=goal, requirements=requirements)
    nodes = [{'node_key':f'n{i}', 'title':goal, 'objectives':[goal] * 15,
        'prerequisite_keys':[f'n{j}' for j in range(i)], 'minutes':5, 'requirement_ids':[r.requirement_id for r in requirements],
        'finding_ids':[f'f{j}' for j in range(30)], 'source_ids':[f's{j}' for j in range(20)],
        'learning_activities':[goal] * 15, 'self_check':goal} for i in range(30)]
    path = LearningPath(title=goal, summary=goal, nodes=nodes, limitations=[])
    assert request.goal == brief.learning_goal == goal and len(path.nodes) == 30
    assert len(path.nodes[-1].objectives) == 15 and len(path.nodes[-1].source_ids) == 20


@pytest.mark.parametrize('official', [True, False])
def test_real_transport_does_not_apply_byte_context_or_phase_output_quota(content_skills, official):
    from deepseek_harness import DeepSeekHarness
    calls = []
    root, ledger = gateway(completion('完整结果', mutate=calls.append), context_tokens=100, sdk_factory=DeepSeekHarness)
    root.deadline = None
    if official:
        root.configured.candidates[0]['api_base'] = 'https://api.deepseek.com/v1'
    # This exceeded the old 128k byte approximation while fitting transport.
    large_input = '详细知识与材料。' * 10000
    assert root.for_phase('resource_review', context={}).chat(
        [{'role':'user', 'content':large_input}], max_tokens=100) == '完整结果'
    assert len(calls) == len(ledger.actions) == 1
    assert large_input in json.dumps(calls[0], ensure_ascii=False)
    assert calls[0].get('max_tokens') == (384000 if official else None)
    assert ledger.actions[0]['actual'].tokens == 70


def test_research_view_preserves_long_requirements_without_local_window_gate():
    from tests.course_preparation.test_research_context_view import state
    from app.course_preparation.research_context_view import build_model_research_context
    original = state()
    brief = original.brief.model_copy(update={'learning_goal':'必须保留的需求。' * 15000})
    original = original.model_copy(update={'brief':brief})
    view = build_model_research_context(original, SimpleNamespace(retry_only=True, context_tokens=100))
    assert view['brief']['learning_goal'] == brief.learning_goal
    assert view['context_view']['max_bytes'] is None
    assert view['context_view']['estimated_bytes'] > 96000


def optional_classroom():
    a = quiz()
    a['resource_type'] = a['spec']['resource_type'] = 'classroom'
    a['spec']['teaching_context']['requirement_ids'] = ['req1']
    a['spec_digest'] = digest(a['spec'])
    a['content']['content'] = {'stage':{'id':'stage'}, 'scenes':[{'id':'page', 'content':{'html':'<p>加法</p>'}}]}
    meta = a['content']['generation_state']['preparation']
    meta.update(spec_digest=a['spec_digest'], teaching_context_digest=digest(a['spec']['teaching_context']),
        objective_bindings=[], applied_requirements=[], generator='openmaic-native',
        alignment_policy='optional_native_classroom_v1', alignment_status='not_generated',
        render_checks={'passed':True,'issues':[]})
    a['content_digest'] = digest(a['content'])
    return a


def test_native_classroom_without_page_mapping_reaches_manifest_without_fake_checks():
    a = optional_classroom()
    validate_artifact(a)
    cp = checkpoint(a)
    cp['plan']['nodes'][0]['requirement_ids'] = ['req1']
    manifest = candidate_manifest(SimpleNamespace(preparation_id='prep-x', owner_user_id='alice'), cp,
        PreparationRequest(request_id=uuid4(), operation='create_course', goal='加法'))
    resource = manifest.nodes[0].resources[0]
    assert resource.objective_ids == ('n:o1',) and resource.objective_coverage == 'planned'
    assert not manifest.nodes[0].checks
    assert a['content']['generation_state']['preparation']['objective_bindings'] == []


def test_optional_classroom_does_not_transfer_missing_labels_or_waive_other_integrity():
    a = optional_classroom()
    b = quiz()
    b['spec']['teaching_context']['requirement_ids'] = ['req1']
    meta = b['content']['generation_state']['preparation']
    meta['applied_requirements'] = []
    b['spec_digest'] = meta['spec_digest'] = digest(b['spec'])
    meta['teaching_context_digest'] = digest(b['spec']['teaching_context'])
    b['content_digest'] = digest(b['content'])
    nodes = [{'node_key':'n','requirement_ids':['req1']}]
    assert node_requirement_issues([a,b], nodes) == []
    assert node_requirement_issues([b], nodes)  # Ordinary report/quiz-only coverage remains enforced.
    bad = deepcopy(b)
    bad['content']['generation_state']['preparation']['objective_bindings'][0]['locator']['question_id'] = 'missing'
    bad['content_digest'] = digest(bad['content'])
    with pytest.raises(ValueError, match='CONTENT_LOCATOR_NOT_FOUND'):
        node_requirement_issues([a,bad], nodes)
    a['content']['content']['scenes'][0]['content']['html'] = '<p>changed</p>'
    with pytest.raises(ValueError, match='ARTIFACT_DIGEST_MISMATCH'):
        validate_artifact(a)


def test_http_accepts_long_goal_and_persists_it_with_retry_only_policy(runtime_engine):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import course_preparations as api
    from app.course_preparation.service import PreparationService
    from tests.course_preparation.test_runtime_foundation import repo
    repository = repo(runtime_engine)
    repository.retry_only = True
    app = FastAPI()
    app.include_router(api.router)
    app.state.preparation_service = PreparationService(repository)
    app.dependency_overrides[api.owner] = lambda: 'alice'
    goal = '完整保留这一条详细学习需求。' * 1200
    payload = {'request_id':str(uuid4()), 'operation':'create_course', 'goal':goal}
    response = TestClient(app).post('/api/course-preparations', json=payload)
    assert response.status_code == 202
    value = response.json()
    assert value['budget']['deadline'] is None
    assert all(value['budget']['limits'][key] is None for key in ('calls','tokens','cost_micro_usd','seconds'))
    stored = repository.get(owner_user_id='alice', preparation_id=value['preparation_id'])
    assert stored.request.goal == goal


def test_active_legacy_task_adopts_new_policy_before_expired_budget_guard(runtime_engine):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy.orm import Session
    from app.database.models import PreparationBudget
    from app.course_preparation.runtime_contracts import BudgetCost
    from tests.course_preparation.test_runtime_foundation import repo, request
    now = [datetime.now(timezone.utc)]
    repository = repo(runtime_engine, now)
    value = repository.submit('alice', request())
    with Session(runtime_engine) as session, session.begin():
        budget = session.get(PreparationBudget, value['preparation_id'])
        spent = {key:budget.limits[key] for key in ('calls','tokens','cost_micro_usd')}
        budget.consumed = spent
    now[0] += timedelta(days=2)
    repository.retry_only = True
    context = repository.claim('worker', preparation_id=value['preparation_id'])
    assert context is not None and context.deadline is None
    repository.begin_action(context, 'next', 'model_completion', {}, BudgetCost(calls=1, tokens=1))
    assert repository.get_public('alice', value['preparation_id'])['budget']['consumed'] == spent
