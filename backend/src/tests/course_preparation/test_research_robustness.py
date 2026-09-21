import json
from uuid import uuid4

import httpx
import pytest

from app.course_preparation.harness_research import LearningPathTools
from app.course_preparation.research_agent import ResearchError, RecoverableSourceError
from app.course_preparation.research_contracts import Candidate
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.source_errors import provider_error
from tests.course_preparation.test_harness_research import setup_tools, coverage, research
from tests.course_preparation.test_research_flow import path


def blocker():
    return {'reason':'缺少可运行实现的正文依据',
            'coverage':[{'requirement_id':'req1','status':'missing','reason':'附件只有概念，缺少示例'}],
            'suggested_actions':['补充可运行的示例材料']}


@pytest.mark.parametrize('count', [9, 30])
def test_many_core_uploads_leave_web_budget_and_allow_complete_path(count):
    base, saved = setup_tools()
    base.agent.max_calls = 60
    req = PreparationRequest(request_id=uuid4(), operation='create_course', goal='综合上传材料理解递归',
        uploads=[{'document_id':f'doc{i}', 'version':1, 'usage':'primary'} for i in range(count)])
    state = base.state.model_copy(update={'candidates':tuple(Candidate(candidate_id=f'src{i}',
        url=f'upload://doc{i}/1',title=f'教材{i}',snippet='附件') for i in range(count))})
    tools = LearningPathTools(base.agent, req, state, reserve=saved.append, guard=lambda:None, timeout=30)
    for i in range(count):
        assert tools.call('fetch_source', {'candidate_id':f'src{i}'})['ok']
    assert tools.agent.read_budget(tools.state)['web_reads'] == 8
    found = tools.call('search_sources', {'query':'补充递归教程'})
    web = next(c for c in found['candidates'] if c['url'].startswith('https://'))
    assert tools.call('fetch_source', {'candidate_id':web['candidate_id']})['ok']
    assert tools.call('record_evidence_finding', {'finding_id':'f1','claim':'递归终止','citation_refs':['q1_1']})['ok']
    assert tools.call('finalize_research_summary', {'overview':'递归','finding_ids':['f1'],'coverage':coverage()})['ok']
    assert tools.call('save_course_plan', path(tools.state.evidence[0].source_id))['path_saved']
    assert tools.state.upload_reads == count and tools.state.reads == count+1


def test_temporary_outage_can_recover_and_failure_counts_survive_resume():
    tools, saved = setup_tools()
    tools.call('search_sources', {'query':'递归终止'})
    candidate = tools.state.candidates[0].candidate_id
    original = tools.agent.sources.read
    def fail(*a, **kw):
        raise RecoverableSourceError('EXTRACT_TEMPORARY','temporary')
    tools.agent.sources.read = fail
    assert tools.call('fetch_source', {'candidate_id':candidate})['error']['retry_allowed']
    resumed = LearningPathTools(tools.agent,tools.request,saved[-1],reserve=saved.append,guard=lambda:None,timeout=30)
    assert not resumed.call('fetch_source', {'candidate_id':candidate,'offset_chars':0})['error']['retry_allowed']
    reads = resumed.state.reads
    assert not resumed.call('fetch_source', {'candidate_id':candidate})['ok']
    assert resumed.state.reads == reads and resumed.fatal is None
    assert resumed.call('search_sources', {'query':'换一个教程'})['ok']
    assert resumed.call('report_research_blocker', blocker())['research_stopped']
    assert resumed.result.path is None
    tools, saved = setup_tools()
    tools.call('search_sources', {'query':'递归终止'})
    candidate = tools.state.candidates[0].candidate_id
    original = tools.agent.sources.read
    tools.agent.sources.read = fail
    tools.call('fetch_source', {'candidate_id':candidate})
    tools.agent.sources.read = original
    assert tools.call('fetch_source', {'candidate_id':candidate})['ok']
    assert not tools.state.source_failures


@pytest.mark.parametrize('status,recoverable', [(429,True),(503,True),(408,True),(401,False),(403,False)])
def test_http_failure_classification(status,recoverable):
    req=httpx.Request('GET','https://example.org')
    exc=httpx.HTTPStatusError('failed',request=req,response=httpx.Response(status,request=req))
    assert isinstance(provider_error(exc,'EXTRACT'),RecoverableSourceError) == recoverable


def test_missing_coverage_unknown_findings_and_partial_coverage_block_path():
    tools, saved = setup_tools()
    research(tools)
    for rows in ([], [{**coverage()[0],'finding_ids':['fake']}], [coverage()[0],coverage()[0]]):
        # Separate sessions avoid intentionally triggering the no-progress cap.
        t=LearningPathTools(tools.agent,tools.request,tools.state,reserve=saved.append,guard=lambda:None,timeout=30)
        assert not t.call('finalize_research_summary', {'overview':'递归','finding_ids':['f1'],'coverage':rows})['ok']
    partial=[{**coverage()[0],'status':'partial','reason':'缺少边界示例'}]
    assert tools.call('finalize_research_summary', {'overview':'依据仍不足','finding_ids':['f1'],'coverage':partial})['ok']
    assert not tools.call('save_course_plan',path(tools.state.evidence[0].source_id))['ok']
    result=tools.call('report_research_blocker',{**blocker(),'coverage':partial})
    assert result['research_stopped'] and tools.result.path is None


def test_native_sdk_stops_with_saved_blocker():
    from deepseek_harness import DeepSeekHarness
    from types import SimpleNamespace
    from app.course_preparation.harness_adapter import HarnessPreparationAdapter
    tools,saved=setup_tools()
    requests=[]
    def complete(req):
        body=json.loads(req.content);requests.append(body)
        stopped=bool(saved and saved[-1].blocker)
        if stopped:
            assert body['tool_choice']=='none'
            message={'role':'assistant','content':'需要补充示例材料。'}
        else:
            name=next(t['function']['name'] for t in body['tools'] if t['function']['name'].endswith('__report_research_blocker'))
            message={'role':'assistant','content':None,'tool_calls':[{'id':'blocker','type':'function',
                'function':{'name':name,'arguments':json.dumps(blocker())}}]}
        return httpx.Response(200,json={'id':'test','object':'chat.completion','created':1,'model':'test',
            'choices':[{'index':0,'message':message,'finish_reason':'stop' if stopped else 'tool_calls'}],
            'usage':{'prompt_tokens':50,'completion_tokens':10,'total_tokens':60}})
    gateway=SimpleNamespace(candidates=[{'model_name':'test','api_base':'http://unused','api_key':'test'}],
                            _build_headers=lambda key:{},_thinking_params=lambda model:{})
    model=HarnessPreparationAdapter(gateway,sdk_factory=DeepSeekHarness,
        client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(complete),**kw))
    result=model.run_learning_path(tools.agent,tools.request,tools.state,reserve=saved.append,guard=lambda:None,timeout=30)
    assert result.blocker and result.path is None and len(requests)==1


def test_blocker_is_persisted_and_exposed_without_entering_generation(runtime_engine):
    from app.course_preparation.lifecycle_repository import LifecycleRepository
    from app.course_preparation.research_stages import ResearchStages
    from app.course_preparation.runner import PreparationRunner
    from app.course_preparation.service import PreparationService
    from app.course_preparation.research_agent import ResearchAgent
    from tests.course_preparation.test_research_flow import Model, Sources, request
    class Auth:
        def authorize(self,*a): pass
    class BlockedModel(Model):
        def run_learning_path(self, agent, request, state, **kwargs):
            tools=LearningPathTools(agent,request,state,**kwargs)
            assert tools.call('report_research_blocker',blocker())['research_stopped']
            return tools.result
    repo=LifecycleRepository(runtime_engine,authorizer=Auth())
    task=repo.submit('alice',request())
    stages=ResearchStages(repo,lambda *a:ResearchAgent(model=BlockedModel(),sources=Sources()),None)
    runner=PreparationRunner(repo,stages.handlers())
    assert runner.run_step(task['preparation_id'],worker_id='test')['stage']=='research_scope'
    result=runner.run_step(task['preparation_id'],worker_id='test')
    assert result=={'failed':True,'code':'RESEARCH_INSUFFICIENT'}
    svc=PreparationService(repo)
    data=svc.intermediates('alice',task['preparation_id'])
    assert data['research_blocker']['reason']==blocker()['reason'] and 'plan' not in data
    assert svc.get('alice',task['preparation_id'])['status']=='failed'


def test_node_cannot_substitute_unrelated_finding_for_coverage():
    tools,saved=setup_tools()
    research(tools)
    assert tools.call('record_evidence_finding',{'finding_id':'f2','claim':'另一个观察','citation_refs':['q1_1']})['ok']
    assert tools.call('finalize_research_summary',{'overview':'递归','finding_ids':['f1','f2'],'coverage':coverage()})['ok']
    proposal=path(tools.state.evidence[0].source_id)
    proposal['nodes'][0]['finding_ids']=['f2']
    result=tools.call('save_course_plan',proposal)
    assert not result['ok'] and 'coverage' in result['error']['message']
    assert tools.state.path is None
