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


@pytest.mark.parametrize('enabled', [True, False])
def test_saved_brief_uses_classroom_switch_over_model_inference(enabled):
    req = PreparationRequest(request_id=uuid4(), operation='create_course',
        goal='理解递归终止条件，需要 AI 课堂', overrides={'include_classroom': enabled})
    data = {**brief(), 'required_resource_types': [] if enabled else ['classroom']}
    agent = ResearchAgent(model=Model(), sources=Sources())
    state = agent._execute('save_preparation_brief', ResearchBrief.model_validate(data),
        req, ResearchState(), timeout=10, reserve=lambda _: None)
    assert state.brief.required_resource_types == (('report', 'quiz', 'classroom') if enabled else ('report', 'quiz'))


def test_classroom_default_preserves_old_request_identity_and_off_changes_it():
    import hashlib
    import json
    from app.course_preparation.schemas import request_digest
    req = request()
    legacy_payload = req.model_dump(mode='json')
    del legacy_payload['overrides']['include_classroom']
    legacy_digest = hashlib.sha256(json.dumps(legacy_payload, ensure_ascii=False,
        sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
    assert request_digest(req) == legacy_digest
    disabled = req.model_copy(update={'overrides': req.overrides.model_copy(update={'include_classroom': False})})
    assert request_digest(disabled) != legacy_digest


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


def test_intake_references_preserve_mineru_escaping_and_reject_wrong_chunk():
    original = r'模型返回 call\_id，工具失败返回 INVALID\_ARGUMENT。不得执行任意代码。'
    documents = Documents(original)
    packets = []
    class Reader:
        def decide(self, packet, tools, **kwargs):
            packets.append(packet)
            return 'record_input_document', {'kind':'learning_material','summary':'工具调用',
                'relevant_points':[{'text':'保留调用关联 ID',
                    'source_ref':packet['document']['passages'][0]['source_ref']}],
                'material_gaps':['缺少供应商 SDK 安装和鉴权示例']}
    stages = SimpleNamespace(documents=documents,agent_factory=lambda *a:SimpleNamespace(model=Reader()))
    context = SimpleNamespace(owner_user_id='alice',deadline=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())
    checkpoint, _ = understand_next_document(stages,context,{},request())
    point = checkpoint['input_documents'][0]['parts'][0]['relevant_points'][0]
    assert point['source_quote'] == original
    from app.course_preparation.intake_references import resolve_requirements, document_passages
    candidate = ResearchBrief.model_validate({**brief(),'material_gaps':['缺少供应商 SDK 安装和鉴权示例'],
        'requirements':[{'requirement_id':'r','text':'工具调用','source_ref':point['source_ref']}]})
    resolved = resolve_requirements(candidate,checkpoint['input_documents'])
    validate_brief(resolved,request(),checkpoint['input_documents'])
    assert resolved.requirements[0].source_quote == original
    assert resolved.requirements[0].source_document_id == 'job'
    assert resolved.material_gaps == candidate.material_gaps
    changed = [{**checkpoint['input_documents'][0], 'version':2}]
    with pytest.raises(ValueError, match='r: 未知 source_ref'):
        resolve_requirements(candidate,changed)
    assert document_passages({'document_id':'job','version':1,'source_hash':'sha'},12000,original)[0]['source_ref'] != point['source_ref']


def test_invalid_reference_and_empty_quote_have_actionable_errors():
    from app.course_preparation.intake_references import resolve_requirements, with_references
    docs = [{'document_id':'job','version':1,'source_hash':'sha','parts':[{'offset':0,
        'relevant_points':[{'text':'工具调用','source_quote':'熟悉工具调用'}]}]}]
    ref = with_references(docs)[0]['parts'][0]['relevant_points'][0]['source_ref']
    data = {**brief(),'requirements':[{'requirement_id':'req-bad','text':'工具调用','source_ref':ref,'source_document_id':'another'}]}
    with pytest.raises(ValueError,match='req-bad: source_ref 不属于'):
        resolve_requirements(ResearchBrief.model_validate(data),docs)
    data['requirements'] = [{'requirement_id':'req-empty','text':'无依据'}]
    for quote in ('', ' '):
        data['requirements'][0]['source_quote'] = quote
        with pytest.raises(ValueError,match='要求原话'):
            validate_brief(ResearchBrief.model_validate(data),request(),docs)


def test_source_ids_are_resolved_before_saving_brief_and_handed_to_research():
    from app.course_preparation.intake_references import with_references
    docs = with_references([{'document_id':'job','version':1,'source_hash':'sha','parts':[{'offset':0,
        'relevant_points':[{'text':'工具调用','source_quote':r'使用 call\_id 关联结果。'}]}]}])
    ref = docs[0]['parts'][0]['relevant_points'][0]['source_ref']
    payload = {**brief(),'requirements':[{'requirement_id':'r','text':'工具调用','source_ref':ref}],
        'material_gaps':['缺少 API 鉴权示例']}
    agent = ResearchAgent(model=Model(),sources=Sources(),extra_context={'input_documents':docs})
    state = agent._execute('save_preparation_brief',ResearchBrief.model_validate(payload),request(),ResearchState(),timeout=10,reserve=lambda _:None)
    assert state.phase == 'research'
    assert state.brief.requirements[0].source_quote == r'使用 call\_id 关联结果。'
    assert state.brief.material_gaps == ('缺少 API 鉴权示例',)
