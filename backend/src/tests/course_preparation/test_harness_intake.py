import json
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, urlopen

import pytest

from app.course_preparation.harness_intake import HarnessIntakeAdapter, IntakeTools
from app.course_preparation.model_adapter import ResearchModelAdapter


TOOL = {'type': 'function', 'function': {'name': 'record_input_document', 'description': 'save',
        'parameters': {'type': 'object', 'properties': {'summary': {'type': 'string'}}, 'required': ['summary']}}}
CONTEXT = {'phase': 'input_document', 'goal': '学习工具调用', 'document': {'content': '工具调用'}}


def rpc(url, token, method, params=None):
    req = Request(url, data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}).encode(),
                  headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with urlopen(req) as response:
        return json.load(response)['result']


class FakeHarness:
    mode = 'ok'
    closed = False

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.patch = json.loads(Path(kwargs['patches'][0]).read_text())

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        type(self).closed = True

    def run(self, prompt, **kwargs):
        config = next(p['config'] for p in self.patch[-1]['insert'] if p['id'] == 'preparation-mcp')
        url, token = config['env']['EDU_MCP_URL'], self.kwargs['env']['EDU_MCP_TOKEN']
        assert [t['name'] for t in rpc(url, token, 'tools/list')['tools']] == ['record_input_document']
        assert all(p['disabled'] for p in self.patch[:3])
        if self.mode == 'crash':
            raise RuntimeError('sdk unavailable')
        if self.mode != 'text':
            rpc(url, token, 'tools/call', {'name': 'record_input_document', 'arguments': {'summary': '工具调用'}})
        if self.mode == 'duplicate':
            rpc(url, token, 'tools/call', {'name': 'record_input_document', 'arguments': {'summary': 'different'}})
        return SimpleNamespace(finish_reason='length' if self.mode == 'truncated' else 'stop')


def adapter(factory=FakeHarness, **kwargs):
    gateway = SimpleNamespace(candidates=[{'model_name': 'test', 'api_base': 'http://unused', 'api_key': 'secret'}])
    return HarnessIntakeAdapter(gateway, sdk_factory=factory, **kwargs)


def test_harness_submits_through_scoped_mcp_and_records_runtime():
    FakeHarness.mode = 'ok'
    model = adapter()
    assert model.decide(CONTEXT, [TOOL], timeout=5) == ('record_input_document', {'summary': '工具调用'})
    assert model.last_packet_metadata['runtime'] == 'deepseek-harness'
    assert FakeHarness.closed


@pytest.mark.parametrize('mode', ['text', 'truncated', 'crash'])
def test_harness_failure_cannot_become_success_or_fallback(mode, monkeypatch):
    FakeHarness.mode = mode
    monkeypatch.setattr(ResearchModelAdapter, 'decide', lambda *a, **k: pytest.fail('must not fall back'))
    with pytest.raises((ValueError, RuntimeError)):
        adapter().decide(CONTEXT, [TOOL], timeout=5)
    assert FakeHarness.closed


def test_unknown_preparation_phase_cannot_fall_back(monkeypatch):
    monkeypatch.setattr(ResearchModelAdapter, 'decide', lambda *a, **k: pytest.fail('must not fall back'))
    with pytest.raises(RuntimeError, match='HARNESS_PHASE_UNKNOWN'):
        adapter().decide({'phase': 'unknown_intelligence'}, [], timeout=1)


def test_tools_reject_unmounted_calls_and_defer_second_decision():
    tools = IntakeTools([TOOL])
    assert not tools.call('search_sources', {})['ok']
    assert tools.result is None
    assert tools.call('record_input_document', {'summary': 'one'})['ok']
    assert tools.call('record_input_document', {'summary': 'one'})['ok']
    assert tools.call('record_input_document', {'summary': 'two'})['error'] == 'DEFERRED_TO_NEXT_STEP'
    assert tools.result == ('record_input_document', {'summary': 'one'})


@pytest.mark.parametrize('phase,tool_name', [('input_document','record_input_document'), ('intent','save_preparation_brief'),
    ('research','search_sources'), ('research','fetch_source'), ('research','record_evidence_finding'),
    ('research','finalize_research_summary'), ('plan','save_course_plan'),
    ('review','submit_path_review'), ('research_nodes','assess_node_evidence'),
    ('route_adjustment','save_route_adjustment')])
def test_real_sdk_round_trip_is_metered_and_only_exposes_intake_tool(phase, tool_name):
    """Run the installed SDK + MCP subprocesses against a deterministic provider."""
    import httpx
    from deepseek_harness import DeepSeekHarness
    calls, ledger = [], []

    def complete(request):
        body = json.loads(request.content)
        calls.append(body)
        names = [tool['function']['name'] for tool in body.get('tools', [])]
        business_names = [name for name in names if name != 'skill']
        assert len(business_names) == 1 and business_names[0].endswith(tool_name), names
        assert 'skill' in names
        from app.course_preparation.workflow_skills import load_workflow_skill, skill_is_loaded
        skill = load_workflow_skill(phase)
        assert skill_is_loaded(body['messages'], skill)
        assert sum(str(m.get('content', '')).count('<skill_content name=') for m in body['messages']) == 1
        assert not any(skill['body'] in str(m.get('content', '')) for m in body['messages'] if m['role'] == 'system')
        tool_results = [m for m in body['messages'] if m['role'] == 'tool']
        if tool_results: assert body['tool_choice'] == 'none'
        message = {'role': 'assistant', 'content': '已提交'} if tool_results else {
            'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call_intake', 'type': 'function',
            'function': {'name': business_names[0], 'arguments': json.dumps({'summary': '工具调用'})}}]}
        return httpx.Response(200, json={'id': 'chat-test', 'object': 'chat.completion', 'created': 1,
            'model': 'deepseek-v4-flash', 'choices': [{'index': 0, 'message': message,
            'finish_reason': 'stop' if tool_results else 'tool_calls'}], 'usage': {'prompt_tokens': 50, 'completion_tokens': 10, 'total_tokens': 60}})

    class Meter:
        def start(self, **kwargs):
            ledger.append({'reserved': kwargs})
            return ledger[-1]
        def finish(self, action, **kwargs):
            action.update(kwargs)

    model = adapter(DeepSeekHarness, client_factory=lambda **kw: httpx.Client(transport=httpx.MockTransport(complete), **kw), meter=Meter())
    model.gateway.candidates[0]['model_name'] = 'deepseek-v4-flash'
    model.gateway._build_headers = lambda key: {}
    model.gateway._thinking_params = lambda name: {}
    tool = {**TOOL, 'function': {**TOOL['function'], 'name': tool_name}}
    assert model.decide({**CONTEXT, 'phase': phase}, [tool], timeout=30) == (tool_name, {'summary': '工具调用'})
    assert len(calls) == len(ledger) == 2
    assert all(row['usage']['total_tokens'] == 60 for row in ledger)
    assert all(row['response_data']['runtime'] == 'deepseek-harness' for row in ledger)
    assert all(row['response_data']['skill']['loaded'] for row in ledger)


@pytest.mark.parametrize('case', ['meter_denied', 'context_limit', 'call_limit', 'truncated', 'skill_missing'])
def test_provider_guards_block_calls_and_incomplete_results(case):
    import httpx
    from urllib.error import HTTPError
    from app.course_preparation.harness_provider import harness_provider
    calls, finishes = [], []

    def complete(request):
        calls.append(request)
        return httpx.Response(200, json={'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'ok'},
            'finish_reason': 'length' if case == 'truncated' else 'stop'}], 'usage': {'total_tokens': 10}})

    class Meter:
        def start(self, **kwargs):
            if case == 'meter_denied':
                raise RuntimeError('BUDGET_EXHAUSTED')
            return kwargs
        def finish(self, action, **kwargs):
            finishes.append(kwargs)

    model = adapter(client_factory=lambda **kw: httpx.Client(transport=httpx.MockTransport(complete), **kw), meter=Meter())
    model.gateway._build_headers = lambda key: {}
    model.gateway._thinking_params = lambda name: {}
    if case == 'skill_missing':
        from app.course_preparation.intake_skill import load_intake_skill
        model.required_skill = load_intake_skill()
    if case == 'context_limit':
        model.context_tokens = 10
    with harness_provider(model, timeout=5) as (url, token, state):
        def post():
            req = Request(url + '/chat/completions', data=json.dumps({'messages': [], 'stream': False}).encode(),
                headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            with urlopen(req) as response:
                return json.load(response)
        if case == 'call_limit':
            for _ in range(4):
                post()
        with pytest.raises(HTTPError):
            post()
        assert state['error'] is not None
    assert len(calls) == (4 if case == 'call_limit' else 3 if case == 'truncated' else 0)
    assert len(finishes) == len(calls)


def test_real_sdk_batch_accepts_one_action_and_explicitly_defers_rest():
    import httpx
    from deepseek_harness import DeepSeekHarness
    requests = []
    def complete(request):
        body = json.loads(request.content); requests.append(body)
        results = [m for m in body['messages'] if m['role'] == 'tool']
        if results:
            assert body['tool_choice'] == 'none'
            text = json.dumps(results, ensure_ascii=False)
            assert 'DEFERRED_TO_NEXT_STEP' in text
            message = {'role':'assistant','content':'已提交一个动作，等待下一步。'}
        else:
            name = next(t['function']['name'] for t in body['tools'] if t['function']['name'] != 'skill')
            message = {'role':'assistant','content':None,'tool_calls':[
                {'id':f'call_{i}','type':'function','function':{'name':name,'arguments':json.dumps({'summary':str(i)})}}
                for i in range(2)]}
        return httpx.Response(200,json={'id':'batch','object':'chat.completion','created':1,'model':'test',
            'choices':[{'index':0,'message':message,'finish_reason':'stop' if results else 'tool_calls'}],
            'usage':{'prompt_tokens':50,'completion_tokens':10,'total_tokens':60}})
    model = adapter(DeepSeekHarness,client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(complete),**kw))
    model.gateway._build_headers=lambda key:{}
    model.gateway._thinking_params=lambda name:{}
    result = model.decide({**CONTEXT,'phase':'research'},[TOOL],timeout=30)
    assert result[0] == 'record_input_document'
    assert result[1]['summary'] in ('0','1')
    assert len(requests) == 2


@pytest.mark.parametrize('case', ['unmounted', 'duplicate_id', 'invalid_json'])
def test_provider_rejects_invalid_batch_before_sdk_dispatch(case):
    import httpx
    from urllib.error import HTTPError
    from app.course_preparation.harness_provider import harness_provider
    toolset = IntakeTools([TOOL])
    calls = [
        {'id': f'call_{i}', 'type': 'function', 'function': {
            'name': TOOL['function']['name'], 'arguments': '{"summary":"ok"}'}}
        for i in range(2)
    ]
    if case == 'unmounted':
        calls[1]['function']['name'] = 'execute_shell'
    elif case == 'duplicate_id':
        calls[1]['id'] = calls[0]['id']
    else:
        calls[1]['function']['arguments'] = '{broken'
    def complete(request):
        return httpx.Response(200, json={'choices': [{'index': 0,
            'message': {'role': 'assistant', 'tool_calls': calls}, 'finish_reason': 'tool_calls'}]})
    model = adapter(client_factory=lambda **kw: httpx.Client(transport=httpx.MockTransport(complete), **kw))
    model.gateway._build_headers = lambda key: {}
    model.gateway._thinking_params = lambda name: {}
    with harness_provider(model, timeout=5, toolset=toolset) as (url, token, state):
        req = Request(url + '/chat/completions', data=json.dumps({'messages': [], 'tools': [TOOL]}).encode(),
                      headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        with pytest.raises(HTTPError):
            urlopen(req)
        assert isinstance(state['error'], ValueError)
        assert toolset.result is None
