import hashlib
import json
import pytest
from app.course_preparation.research_contracts import ResearchState, SourceEvidence, ResearchBrief, Requirement, ReadEvidenceArgs
from app.course_preparation.research_context_view import build_research_context_view, read_research_evidence
from app.course_preparation.research_agent import ResearchAgent, ResearchError


def state():
    evidence=[]
    for i in range(12):
        content=('原始资料，必须核对工具调用。'*400)+f'文末目标{i}：真实 API 安装和鉴权。'
        evidence.append(SourceEvidence(source_id=f's{i}',candidate_id=f'c{i}',url=f'upload://d{i}/1',title=f'd{i}',
            content=content,content_sha256=hashlib.sha256(content.encode()).hexdigest(),retrieved_at='2026-09-19'))
    return ResearchState(phase='research',evidence=tuple(evidence),brief=ResearchBrief(topic='API',audience='beginner',
        language='zh',total_minutes=60,material_gaps=('缺少先修鉴权证据',),requirements=(Requirement(requirement_id='req',text='真实 API',source_quote='真实 API'),)))


def test_bounded_view_preserves_requirements_gaps_locators_and_recall():
    original=state(); before=original.model_dump_json()
    view=build_research_context_view(original,required_ids=['s11','req'],max_bytes=10000)
    size=len(json.dumps(view,ensure_ascii=False,separators=(',',':')).encode())
    assert size==view['context_view']['estimated_bytes']<=10000
    assert view['context_view']['actual_usage'] is None
    assert view['brief']['requirements'][0]['text']=='真实 API'
    assert view['brief']['material_gaps']==['缺少先修鉴权证据']
    assert len(view['evidence'])==12 and any(e['content_omitted'] for e in view['evidence'])
    assert original.model_dump_json()==before
    recalled=read_research_evidence(original,source_id='s11',offset_chars=len(original.evidence[-1].content)-30)
    assert '文末目标11' in recalled['content']
    quote=read_research_evidence(original,citation_ref='q12_1')
    assert quote['quote'] in original.evidence[-1].content


def test_too_small_budget_fails_without_dropping_requirement():
    with pytest.raises(ResearchError,match='RESEARCH_CONTEXT_BUDGET'):
        build_research_context_view(state(),required_ids=['req'],max_bytes=100)
    with pytest.raises(ValueError,match='UNKNOWN_REQUIRED_ID'):
        build_research_context_view(state(),required_ids=['invented'],max_bytes=10000)


def test_recall_tool_rechecks_authority_and_never_networks():
    class Sources:
        denied=False
        def authorize_read(self,url):
            if self.denied: raise PermissionError('revoked')
        def read(self,*a,**kw): pytest.fail('recall must use original bytes')
    sources=Sources(); agent=ResearchAgent(model=None,sources=sources)
    args=ReadEvidenceArgs(citation_ref='q12_1')
    assert agent.read_evidence(state(),args)['source_id']=='s11'
    sources.denied=True
    with pytest.raises(PermissionError): agent.read_evidence(state(),args)


def test_required_quote_is_preserved_before_optional_body():
    original=state()
    view=build_research_context_view(original,required_ids=['q12_20'],max_bytes=10000)
    assert any(p['citation_ref']=='q12_20' for p in view['evidence'][-1]['passages'])


def test_finalized_findings_are_not_duplicated_in_bounded_review_context():
    from app.course_preparation.research_contracts import ResearchSummary, Finding, Citation
    evidence = state().evidence[:1]
    findings = tuple(Finding(finding_id=f'f{i}', claim='真实结论' * 35,
        citations=(Citation(source_id='s0', quote=evidence[0].content[:350]),)) for i in range(8))
    original = state().model_copy(update={'phase': 'review', 'evidence': evidence,
        'draft_findings': findings, 'summary': ResearchSummary(overview='研究汇总', findings=findings)})
    before = original.model_dump_json()
    view = build_research_context_view(original, required_ids=['req', 'f0', 'q1_1'], max_bytes=18000)
    assert view['draft_findings'] == []
    assert view['summary'] == original.summary.model_dump(mode='json')
    assert view['context_view']['deduplicated_draft_finding_ids'] == [f'f{i}' for i in range(8)]
    assert view['context_view']['draft_findings_reference'] == 'summary.findings'
    assert any(p['citation_ref'] == 'q1_1' for p in view['evidence'][0]['passages'])
    assert view['brief'] == original.brief.model_dump(mode='json')
    assert view['context_view']['estimated_bytes'] <= 18000
    assert original.model_dump_json() == before


def test_only_exact_finalized_duplicates_are_removed_from_projection():
    from app.course_preparation.research_contracts import ResearchSummary, Finding, Citation
    original = state().model_copy(update={'evidence': state().evidence[:1]})
    final = Finding(finding_id='f0', claim='已汇总结论',
        citations=(Citation(source_id='s0', quote=original.evidence[0].content[:80]),))
    changed = final.model_copy(update={'claim': '同编号但内容已经修改的草稿'})
    pending = final.model_copy(update={'finding_id': 'f1'})
    for summary in (None, ResearchSummary(overview='研究汇总', findings=(final,))):
        current = original.model_copy(update={'summary': summary, 'draft_findings': (changed, pending)})
        view = build_research_context_view(current, required_ids=['f0', 'f1'], max_bytes=10000)
        assert view['draft_findings'] == [f.model_dump(mode='json') for f in (changed, pending)]
        assert 'deduplicated_draft_finding_ids' not in view['context_view']


def test_model_view_expands_for_protected_facts_without_losing_original_state():
    from types import SimpleNamespace
    from app.course_preparation.research_contracts import ResearchSummary, Finding, Citation
    from app.course_preparation.research_context_view import build_model_research_context
    original = state().model_copy(update={'evidence': state().evidence[:1]})
    findings = tuple(Finding(finding_id=f'f{i}', claim='结论' * 900,
        citations=(Citation(source_id='s0', quote=original.evidence[0].content[:350]),)) for i in range(8))
    original = original.model_copy(update={'summary': ResearchSummary(overview='汇总', findings=findings)})
    before = original.model_dump_json()
    with pytest.raises(ResearchError, match='RESEARCH_CONTEXT_BUDGET'):
        build_research_context_view(original, required_ids=(), max_bytes=48000)
    view = build_model_research_context(original, SimpleNamespace(context_tokens=128000))
    info = view['context_view']
    assert info['expanded_for_protected_content'] is True
    assert 48000 < info['max_bytes'] < 96000
    assert info['estimated_bytes'] <= info['max_bytes']
    assert info['estimated_bytes'] == len(json.dumps(view, ensure_ascii=False, separators=(',', ':')).encode())
    assert view['summary'] == original.summary.model_dump(mode='json')
    assert before == original.model_dump_json()
    with pytest.raises(ResearchError, match='RESEARCH_CONTEXT_BUDGET'):
        build_model_research_context(original, SimpleNamespace(context_tokens=64000))


def test_model_view_does_not_expand_for_optional_source_prose(monkeypatch):
    from types import SimpleNamespace
    from app.course_preparation.research_context_view import build_model_research_context
    monkeypatch.setenv('COURSE_RESEARCH_VIEW_SOFT_BYTES', '10000')
    monkeypatch.setenv('COURSE_RESEARCH_VIEW_MAX_BYTES', '30000')
    view = build_model_research_context(state(), SimpleNamespace(context_tokens=128000))
    assert view['context_view']['expanded_for_protected_content'] is False
    assert view['context_view']['max_bytes'] == 10000
    assert any(e['content_omitted'] for e in view['evidence'])


def test_same_url_different_snapshot_cannot_relocate_quote():
    from uuid import uuid4
    from app.course_preparation.research_contracts import ResearchSummary, Finding, Citation
    from app.course_preparation.schemas import PreparationRequest
    old=state().evidence[0].model_copy(update={'url':'https://example.edu','snapshot_id':'v1','content':'Original old source has enough detailed text.'})
    new=old.model_copy(update={'source_id':'new','snapshot_id':'v2','content':'Completely different new source with a changed API.'})
    current=ResearchState(searches=1,evidence=(old,new))
    summary=ResearchSummary(overview='API',findings=(Finding(finding_id='f',claim='API',citations=(Citation(source_id=old.source_id,quote='changed API.'),)),))
    with pytest.raises(ValueError,match='引用与已读原文不匹配'):
        ResearchAgent(model=None,sources=None)._execute('save_research_summary',summary,
            PreparationRequest(request_id=uuid4(),operation='create_course',goal='API'),current,timeout=1,reserve=None)


def test_context_guard_resumes_from_saved_state_without_refunding_calls(runtime_engine):
    from tests.course_preparation.test_runtime_foundation import repo,request
    from app.course_preparation.research_stages import ResearchStages
    repository=repo(runtime_engine);task=repository.submit('alice',request())
    context=repository.claim('worker',preparation_id=task['preparation_id'])
    class Model:
        def run_learning_path(self,agent,request,state,*,reserve,**kw):
            reserve(state.model_copy(update={'calls':state.calls+1}))
            raise ResearchError('CONTEXT_BUDGET_EXCEEDED','history full')
    original=state()
    checkpoint={'research_state':original.model_dump(mode='json'),'research_attempt':1}
    stages=ResearchStages(repository,lambda *a:ResearchAgent(model=Model(),sources=None),None)
    for attempt in (1,2):
        checkpoint,saved=stages._decision(context,checkpoint)
        assert saved.calls==attempt
        assert checkpoint['research_context_restarts']==attempt
        assert saved.evidence==original.evidence
    with pytest.raises(ResearchError,match='CONTEXT_BUDGET_EXCEEDED'):
        stages._decision(context,checkpoint)


def test_context_rollover_projects_persisted_summary_before_stage_transition():
    from copy import deepcopy
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from app.course_preparation.research_stages import ResearchStages
    from tests.course_preparation.test_research_flow import Model, Sources, request, run
    completed = run(ResearchAgent(model=Model(), sources=Sources()))
    initial = completed.model_copy(update={'phase': 'research', 'summary': None,
        'path': None, 'review': None, 'calls': 0})
    req = request()
    saved = []
    repository = SimpleNamespace(
        get=lambda **kwargs: SimpleNamespace(request=req),
        checkpoint=lambda context, value: saved.append(deepcopy(value)),
        heartbeat=lambda context: None,
    )
    class RolloverModel:
        def run_learning_path(self, agent, request, state, *, reserve, **kwargs):
            reserve(state.model_copy(update={'phase': 'plan', 'summary': completed.summary, 'calls': 1}))
            raise ResearchError('CONTEXT_BUDGET_EXCEEDED', 'history full after summary saved')
    context = SimpleNamespace(owner_user_id='alice', preparation_id='prep-rollover', attempt_no=1,
        deadline=(datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
        checkpoint={'research_state': initial.model_dump(mode='json'), 'research_attempt': 1})
    stages = ResearchStages(repository, lambda *args: ResearchAgent(model=RolloverModel(), sources=None), None)
    result = stages.research_scope(context)
    assert result.next_stage == 'plan'
    assert result.checkpoint['research_summary'] == completed.summary.model_dump(mode='json')
    assert result.checkpoint['brief'] == completed.brief.model_dump(mode='json')
    assert result.checkpoint['research_state']['calls'] == 1
    assert result.checkpoint['research_context_restarts'] == 1
    assert saved[-1]['research_state']['summary'] == result.checkpoint['research_summary']
