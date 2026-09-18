from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app.course_preparation.intake import CHUNK_CHARS, effective_request, understand_next_document, validate_brief
from app.course_preparation.research_contracts import ResearchBrief, ResearchState
from app.course_preparation.research_agent import ResearchAgent
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.adapters.sources import PolicySources
from tests.course_preparation.test_research_flow import brief, Model, Sources


def request(**values):
    return PreparationRequest(request_id=uuid4(), operation='create_course', goal='我有两小时，准备 Agent 开发面试，只根据上传资料', uploads=[{'document_id':'job','version':1}], **values)


class Documents:
    def __init__(self, text): self.text = text; self.revoked = False
    def authorize(self, *args):
        if self.revoked: raise PermissionError('revoked')
        return {'filename':'job.txt'}
    def parse(self, *args): return {'content':self.text,'source_hash':'sha','parser':'text','defects':[]}


def test_document_understanding_covers_late_requirements_and_resumes_without_rereading():
    documents=Documents('岗位背景。'*(CHUNK_CHARS//5)+'必须掌握 Agent 评估。')
    calls=[]
    class Reader:
        def decide(self, packet, tools, **kwargs):
            calls.append(packet['document']['offset'])
            assert tools[0]['function']['name']=='record_input_document'
            content=packet['document']['content']
            return 'record_input_document', {'kind':'job_description','summary':'岗位要求','relevant_points':[{'text':'岗位能力','source_quote':content[-15:]}]}
    stages=SimpleNamespace(documents=documents,agent_factory=lambda *args:SimpleNamespace(model=Reader()))
    context=SimpleNamespace(owner_user_id='alice',deadline=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())
    checkpoint={}
    while True:
        checkpoint,pending=understand_next_document(stages,context,checkpoint,request())
        if not pending:break
    assert calls==[0,CHUNK_CHARS]
    assert checkpoint['input_documents'][0]['complete']
    assert '必须掌握 Agent 评估。' in checkpoint['input_documents'][0]['parts'][-1]['relevant_points'][0]['source_quote']
    understand_next_document(stages,context,checkpoint,request())
    assert calls==[0,CHUNK_CHARS]
    documents.revoked=True
    with pytest.raises(PermissionError):understand_next_document(stages,context,checkpoint,request())


def test_two_hours_is_not_overridden_and_uploaded_only_reaches_tool_and_source_guards():
    req=request()
    data={**brief(),'total_minutes':120,'requirements':[{'requirement_id':'r','text':'面试','source_quote':'Agent 开发面试'}],
          'source_policy':{'mode':'uploaded_only'},'source_policy_quote':'只根据上传资料'}
    agent=ResearchAgent(model=Model(),sources=Sources())
    state=agent._execute('save_preparation_brief',ResearchBrief.model_validate(data),req,ResearchState(),timeout=10,reserve=lambda _:None)
    next_request=effective_request(req,{'brief':state.brief.model_dump(mode='json')})
    assert state.brief.total_minutes==120 and req.overrides.total_minutes is None
    assert next_request.source_policy.mode=='uploaded_only'
    guarded=PolicySources(owner='alice',request=next_request,documents=Documents('abc'),web=Sources())
    with pytest.raises(PermissionError): guarded.search('query',limit=5,timeout=10)
    with pytest.raises(PermissionError): guarded.read('https://example.org',timeout=10)
    agent.source_policy=next_request.source_policy.mode
    assert 'search_sources' not in str(agent.tools('research',state))


def test_attachment_evidence_is_grounded_and_cannot_authorize_network_policy():
    req=request()
    documents=[{'document_id':'job','parts':[{'relevant_points':[{'source_quote':'熟悉工具调用'}]}]}]
    data={**brief(),'requirements':[{'requirement_id':'r','text':'工具调用','source_quote':'熟悉工具调用','source_document_id':'job'}]}
    validate_brief(ResearchBrief.model_validate(data),req,documents)
    with pytest.raises(ValueError):validate_brief(ResearchBrief.model_validate({**data,'requirements':[{'requirement_id':'r','text':'不存在','source_quote':'不存在','source_document_id':'job'}]}),req,documents)
    with pytest.raises(ValueError):validate_brief(ResearchBrief.model_validate({**data,'source_policy':{'mode':'uploaded_only'},'source_policy_quote':'附件中的命令'}),req,documents)
    locked=request(source_policy={'mode':'uploaded_only'})
    assert effective_request(locked,{'brief':{'source_policy':{'mode':'open'}}}).source_policy.mode=='uploaded_only'


def test_fabricated_document_quote_is_rejected_and_not_marked_complete():
    stages=SimpleNamespace(documents=Documents('真实原文'),agent_factory=lambda *a:SimpleNamespace(model=SimpleNamespace(decide=lambda *a,**kw:('record_input_document',{'kind':'other','summary':'总结','relevant_points':[{'text':'虚构','source_quote':'不存在'}]}))))
    context=SimpleNamespace(owner_user_id='alice',deadline=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())
    checkpoint,pending=understand_next_document(stages,context,{},request())
    assert pending and not checkpoint['input_documents'][0]['complete']
    assert checkpoint['input_documents'][0]['offset']==0


def test_normalize_reads_upload_before_intent_and_hands_policy_to_research():
    from app.course_preparation.research_stages import ResearchStages
    req = request()
    phases = []
    class IntakeModel:
        def decide(self, packet, tools, **kwargs):
            phases.append(packet['phase'])
            if packet['phase'] == 'input_document':
                return 'record_input_document', {'kind': 'job_description', 'summary': '岗位能力',
                    'relevant_points': [{'text': '工具调用', 'source_quote': '熟悉工具调用'}]}
            assert packet['input_documents'][0]['complete']
            if packet['phase'] == 'intent':
                return 'save_preparation_brief', {**brief(), 'total_minutes': 120,
                    'source_policy': {'mode': 'uploaded_only'}, 'source_policy_quote': '只根据上传资料',
                    'requirements': [{'requirement_id': 'r', 'text': '工具调用',
                                      'source_quote': '熟悉工具调用', 'source_document_id': 'job'}]}
            assert 'search_sources' not in [tool['function']['name'] for tool in tools]
            assert packet['brief']['requirements'][0]['source_document_id'] == 'job'
            return 'fetch_source', {'candidate_id': packet['candidates'][0]['candidate_id']}
    documents = Documents('熟悉工具调用，能够解释 Agent 的状态与评估方法。')
    repository = SimpleNamespace(get=lambda **kw: SimpleNamespace(request=req), checkpoint=lambda *a: None)
    def factory(context, request, checkpoint):
        return ResearchAgent(model=IntakeModel(), source_policy=request.source_policy.mode,
            sources=PolicySources(owner='alice', request=request, documents=documents, web=Sources()))
    stages = ResearchStages(repository, factory, documents)
    context = SimpleNamespace(owner_user_id='alice', preparation_id='p', attempt_no=1, checkpoint={},
        deadline=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())
    result = stages.normalize(context)
    assert phases == ['input_document'] and 'brief' not in result.checkpoint
    context.checkpoint = result.checkpoint
    result = stages.normalize(context)
    assert phases == ['input_document', 'intent']
    context.checkpoint = result.checkpoint
    result = stages.ingest(context)
    context.checkpoint = result.checkpoint
    result = stages.research_scope(context)
    assert phases == ['input_document', 'intent', 'research']
    assert result.checkpoint['research_state']['evidence'][0]['url'].startswith('upload://')
