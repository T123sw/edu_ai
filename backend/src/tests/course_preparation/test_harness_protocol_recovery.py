import json
import httpx
import pytest
from deepseek_harness import DeepSeekHarness
from tests.course_preparation.test_harness_intake import adapter, CONTEXT, TOOL


@pytest.mark.parametrize('always_multiple', [False, True])
def test_content_submission_batch_is_corrected_before_any_tool_dispatch(always_multiple):
    from app.course_preparation.harness_generation import ContentTools
    requests, ledger, dispatched = [], [], []

    class RecordingTools(ContentTools):
        def call(self, name, arguments):
            dispatched.append((name, arguments))
            return super().call(name, arguments)

    toolset = RecordingTools(lambda: None, structured=True)

    def complete(request):
        payload = json.loads(request.content)
        requests.append(payload)
        name = next(t['function']['name'] for t in payload['tools'] if t['function']['name'].endswith('submit_resource_json'))
        if len(requests) > 1:
            assert '只提交当前资源' in payload['messages'][-1]['content']
            assert not dispatched
        values = [{'content': 'report'}, {'content': {'questions': []}}] if always_multiple or len(requests) == 1 else [{'content': 'corrected report'}]
        return httpx.Response(200, json={'id': 'batch-recovery', 'object': 'chat.completion', 'created': 1,
            'model': 'test', 'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {
                'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': f'call-{i}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps({'value': value})}}
                    for i, value in enumerate(values)]}}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 10, 'total_tokens': 60}})

    class Meter:
        def start(self, **kwargs): ledger.append({}); return ledger[-1]
        def finish(self, action, **kwargs): action.update(kwargs)

    model = adapter(DeepSeekHarness, client_factory=lambda **kw: httpx.Client(transport=httpx.MockTransport(complete), **kw), meter=Meter())
    model.gateway._build_headers = lambda key: {}
    model.gateway._thinking_params = lambda name: {}
    tools = [{'type': 'function', 'function': spec} for spec in toolset.tools.values()]
    run = lambda: model._run({**CONTEXT, 'phase': 'resource_write'}, tools, timeout=30, toolset=toolset)
    if always_multiple:
        with pytest.raises(ValueError, match='after two corrections'):
            run()
        assert len(requests) == len(ledger) == 3
        assert not dispatched and toolset.result is None
    else:
        assert json.loads(run()) == {'content': 'corrected report'}
        assert len(requests) == len(ledger) == 2
        assert dispatched == [('submit_resource_json', {'value': {'content': 'corrected report'}})]
    assert all(row['usage']['total_tokens'] == 60 for row in ledger)


@pytest.mark.parametrize('first_failure', ['invalid_json', 'large_invalid_json', 'length'])
def test_native_session_requests_corrected_json_without_dispatching_invalid_arguments(first_failure):
    requests, ledger = [], []
    def complete(request):
        payload = json.loads(request.content)
        requests.append(payload)
        name = next(t['function']['name'] for t in payload['tools'] if t['function']['name'] != 'skill')
        if len(requests) == 1:
            arguments = '{"summary":"' + ('坏' * 40000 if first_failure == 'large_invalid_json' else 'bad') + '"'
        else:
            assert ('截断' if first_failure == 'length' else 'JSON') in json.dumps(payload['messages'], ensure_ascii=False)
            assert len(payload['messages'][-1]['content']) < 2500
            arguments = '{"summary":"corrected"}'
        message = {'role': 'assistant', 'content': None, 'tool_calls': [
            {'id': 'call-json', 'type': 'function', 'function': {'name': name, 'arguments': arguments}}]}
        return httpx.Response(200, json={'id': 'json-recovery', 'object': 'chat.completion', 'created': 1,
            'model': 'test', 'choices': [{'index': 0, 'message': message, 'finish_reason': 'length' if len(requests) == 1 and first_failure == 'length' else 'tool_calls'}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 10, 'total_tokens': 60}})
    class Meter:
        def start(self, **kwargs):
            ledger.append({})
            return ledger[-1]
        def finish(self, action, **kwargs): action.update(kwargs)
    model = adapter(DeepSeekHarness, client_factory=lambda **kw: httpx.Client(transport=httpx.MockTransport(complete), **kw), meter=Meter())
    model.gateway._build_headers = lambda key: {}
    model.gateway._thinking_params = lambda name: {}
    assert model.decide({**CONTEXT, 'phase': 'resource_write'}, [TOOL], timeout=30) == ('record_input_document', {'summary': 'corrected'})
    assert len(requests) == len(ledger) == 2
    assert all(row['usage']['total_tokens'] == 60 for row in ledger)


def test_native_response_deadline_has_typed_provider_failure_and_settles_usage(monkeypatch):
    import time
    import importlib
    from types import SimpleNamespace
    provider = importlib.import_module('app.course_preparation.harness_provider')
    current = [0]
    monkeypatch.setattr(provider, 'time', SimpleNamespace(monotonic=lambda: current[0], time=time.time))
    ledger = []
    def complete(request):
        current[0] = 31
        return httpx.Response(200, json={'choices': []})
    class Meter:
        def start(self, **kwargs): ledger.append({}); return ledger[-1]
        def finish(self, action, **kwargs): action.update(kwargs)
    model = adapter(DeepSeekHarness, client_factory=lambda **kw: httpx.Client(transport=httpx.MockTransport(complete), **kw), meter=Meter())
    model.gateway._build_headers=lambda key: {}
    model.gateway._thinking_params=lambda name: {}
    from app.course_preparation.research_agent import ResearchError
    with pytest.raises(ResearchError, match='PROVIDER_TIMEOUT'):
        model.decide({**CONTEXT, 'phase': 'resource_write'}, [TOOL], timeout=30)
    assert len(ledger) == 1 and ledger[0]['failed'] is True


@pytest.mark.parametrize('always_unknown', [False, True])
def test_unknown_tool_is_corrected_before_dispatch_instead_of_poisoning_session(always_unknown):
    requests=[]
    def complete(request):
        payload=json.loads(request.content);requests.append(payload)
        allowed=next(t['function']['name'] for t in payload['tools'] if t['function']['name']!='skill')
        if len(requests)>1:
            assert '未挂载工具' in payload['messages'][-1]['content']
            assert allowed in payload['messages'][-1]['content']
        name='mcp__hyperframes__invented_edit' if always_unknown or len(requests)==1 else allowed
        return httpx.Response(200,json={'id':'unknown-tool-recovery','object':'chat.completion','created':1,
            'model':'test','choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':None,
                'tool_calls':[{'id':'call-unknown','type':'function','function':{'name':name,'arguments':'{"summary":"corrected"}'}}]}}],
            'usage':{'prompt_tokens':50,'completion_tokens':10,'total_tokens':60}})
    model=adapter(DeepSeekHarness,client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(complete),**kw))
    model.gateway._build_headers=lambda key:{}
    model.gateway._thinking_params=lambda name:{}
    if always_unknown:
        from app.course_preparation.harness_provider import CompletionFormatError
        with pytest.raises(CompletionFormatError,match='after two corrections'):
            model.decide({**CONTEXT,'phase':'resource_write'},[TOOL],timeout=30)
        assert len(requests)==3
    else:
        assert model.decide({**CONTEXT,'phase':'resource_write'},[TOOL],timeout=30)==('record_input_document',{'summary':'corrected'})
        assert len(requests)==2
