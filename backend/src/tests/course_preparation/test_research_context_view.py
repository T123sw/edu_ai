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
