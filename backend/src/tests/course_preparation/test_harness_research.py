import json
from types import SimpleNamespace

import httpx
import pytest

from app.course_preparation.harness_adapter import HarnessPreparationAdapter
from app.course_preparation.harness_research import LearningPathTools
from app.course_preparation.research_agent import ResearchAgent
from app.course_preparation.research_contracts import ResearchState, ResearchBrief
from tests.course_preparation.test_research_flow import Sources, request, brief, path


def setup_tools(*, guard=lambda: None, source_policy='open'):
    saved = []
    agent = ResearchAgent(model=None, sources=Sources(), incremental_findings=True, source_policy=source_policy)
    state = ResearchState(phase='research', brief=ResearchBrief.model_validate(brief()))
    tools = LearningPathTools(agent, request(), state, reserve=saved.append, guard=guard, timeout=30)
    return tools, saved


def coverage():
    return [{'requirement_id':'req1','kind':'knowledge','status':'covered','finding_ids':['f1'],'reason':'已读正文支撑递归终止条件'}]


def research(tools):
    found = tools.call('search_sources', {'query': '递归终止'})
    read = tools.call('fetch_source', {'candidate_id': found['candidates'][0]['candidate_id']})
    assert read['evidence'][0]['passages'][0]['text'].startswith('递归需要终止条件')
    result = tools.call('record_evidence_finding', {'finding_id': 'f1', 'claim': '递归需要终止条件',
                                                   'citation_refs': ['q1_1']})
    assert result['finding']['citations'][0]['source_id'] == tools.state.evidence[0].source_id
    return tools.call('finalize_research_summary', {'overview': '递归终止', 'finding_ids': ['f1'], 'coverage':coverage()})


def test_real_results_validation_repair_and_checkpoint_resume():
    tools, saved = setup_tools()
    assert research(tools)['ok']
    invalid = path(tools.state.evidence[0].source_id)
    invalid['nodes'][0]['minutes'] = 31
    assert not tools.call('save_course_plan', invalid)['ok']
    assert saved[-1].last_error and saved[-1].path is None
    resumed = LearningPathTools(tools.agent, request(), saved[-1], reserve=saved.append, guard=lambda: None, timeout=30)
    assert resumed.call('save_course_plan', path(tools.state.evidence[0].source_id))['path_saved']
    assert resumed.result.phase == 'review'
    assert len(tools.agent.sources.searches) == len(tools.agent.sources.reads) == 1
    assert not resumed.call('search_sources', {'query': 'extra'})['ok']


def test_planning_can_return_to_research_and_invalidates_old_summary():
    tools, saved = setup_tools()
    research(tools)
    assert tools.state.summary is not None
    tools.call('record_evidence_finding', {'finding_id': 'f1', 'claim': '终止条件使递归停止', 'citation_refs': ['q1_1']})
    assert tools.state.summary is None and tools.state.phase == 'research'
    assert not tools.call('save_course_plan', path(tools.state.evidence[0].source_id))['ok']
    assert tools.state.path is None


def test_plan_correction_rejects_node_patch_and_explains_full_envelope():
    tools, saved = setup_tools()
    research(tools)
    complete = path(tools.state.evidence[0].source_id)
    invalid = tools.call('save_course_plan', complete['nodes'][0])
    assert not invalid['ok'] and tools.state.path is None
    assert '完整课程对象' in invalid['error']['message']
    assert '不能拆成多次调用' in invalid['error']['message']
    assert tools.call('save_course_plan', complete)['path_saved']


def test_uploaded_only_unmounted_review_and_bad_references_cannot_execute():
    tools, saved = setup_tools(source_policy='uploaded_only')
    assert 'search_sources' not in tools.tools
    assert not tools.call('search_sources', {'query': 'forbidden'})['ok']
    assert not tools.agent.sources.searches
    assert not tools.call('submit_path_review', {'decision': 'pass'})['ok']
    assert tools.state.review is None
    tools, saved = setup_tools()
    assert not tools.call('record_evidence_finding', {'finding_id':'f1','claim':'fake','citation_refs':['q99_1']})['ok']
    assert not tools.state.draft_findings


def test_revoked_guard_stops_all_later_side_effects():
    allowed = [True]
    def guard():
        if not allowed[0]:
            raise PermissionError('revoked')
    tools, saved = setup_tools(guard=guard)
    tools.call('search_sources', {'query': '递归终止'})
    allowed[0] = False
    assert not tools.call('fetch_source', {'candidate_id': tools.state.candidates[0].candidate_id})['ok']
    allowed[0] = True
    assert not tools.call('search_sources', {'query': 'extra'})['ok']
    assert isinstance(tools.fatal, PermissionError) and not tools.agent.sources.reads


@pytest.mark.parametrize('batch_findings', [False, True])
def test_native_sdk_continues_with_real_results_until_path_saved(batch_findings):
    from deepseek_harness import DeepSeekHarness
    saved, requests = [], []
    sources = Sources()
    state = ResearchState(phase='research', brief=ResearchBrief.model_validate(brief()))
    def complete(req):
        body = json.loads(req.content); requests.append(body)
        current = saved[-1] if saved else state
        results = json.dumps([m for m in body['messages'] if m['role']=='tool'],ensure_ascii=False)
        if current.path:
            assert body['tool_choice'] == 'none'
            assert 'path_saved' in results
            message={'role':'assistant','content':'路径已提交。'}
        else:
            if not current.candidates:
                name,args='search_sources',{'query':'递归终止'}
            elif not current.evidence:
                assert current.candidates[0].candidate_id in results
                name,args='fetch_source',{'candidate_id':current.candidates[0].candidate_id}
            elif not current.draft_findings:
                assert '递归需要终止条件' in results and 'q1_1' in results
                name,args='record_evidence_finding',{'finding_id':'f1','claim':'递归需要终止条件','citation_refs':['q1_1']}
            elif not current.summary:
                name,args='finalize_research_summary',{'overview':'递归终止','finding_ids':['f1'],'coverage':coverage()}
            else:
                name,args='save_course_plan',path(current.evidence[0].source_id)
            mounted=next(t['function']['name'] for t in body['tools'] if t['function']['name'].endswith('__'+name))
            message={'role':'assistant','content':None,'tool_calls':[{'id':'call_'+str(len(requests)),
                'type':'function','function':{'name':mounted,'arguments':json.dumps(args)}}]}
        if batch_findings and not current.draft_findings and current.evidence:
            second = json.loads(json.dumps(message['tool_calls'][0]))
            second['id'] += '_second'
            second['function']['arguments'] = json.dumps({**args, 'finding_id':'f2'})
            message['tool_calls'].append(second)
        return httpx.Response(200,json={'id':'continuous','object':'chat.completion','created':1,'model':'test',
            'choices':[{'index':0,'message':message,'finish_reason':'stop' if current.path else 'tool_calls'}],
            'usage':{'prompt_tokens':50,'completion_tokens':10,'total_tokens':60}})
    gateway=SimpleNamespace(candidates=[{'model_name':'test','api_base':'http://unused','api_key':'test'}],
                            _build_headers=lambda key:{},_thinking_params=lambda model:{})
    model=HarnessPreparationAdapter(gateway,sdk_factory=DeepSeekHarness,
        client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(complete),**kw))
    agent=ResearchAgent(model=model,sources=sources,incremental_findings=True)
    def persist(current):
        saved.append(current)
        if current.path:
            # Terminal closure must not require another model/context budget.
            model.context_tokens = 1
    result=model.run_learning_path(agent,request(),state,reserve=persist,guard=lambda:None,timeout=30)
    assert result.phase=='review' and result.path and len(requests)==5
    assert len(result.draft_findings) == (2 if batch_findings else 1)
    assert len(sources.searches)==len(sources.reads)==1
    assert model.required_skill['name']=='build-learning-path'


def test_action_budget_stops_before_external_call():
    tools, saved = setup_tools()
    tools.agent.max_calls = 1
    tools.call('search_sources', {'query':'递归终止'})
    result = tools.call('fetch_source', {'candidate_id':tools.state.candidates[0].candidate_id})
    assert not result['ok'] and result['error']=='BUDGET_EXHAUSTED'
    assert not tools.agent.sources.reads and saved[-1].calls==1
