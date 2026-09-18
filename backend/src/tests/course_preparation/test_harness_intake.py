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
        config = self.patch[-1]['insert'][0]['config']
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


@pytest.mark.parametrize('mode', ['text', 'duplicate', 'truncated', 'crash'])
def test_harness_failure_cannot_become_success_or_fallback(mode, monkeypatch):
    FakeHarness.mode = mode
    monkeypatch.setattr(ResearchModelAdapter, 'decide', lambda *a, **k: pytest.fail('must not fall back'))
    with pytest.raises((ValueError, RuntimeError)):
        adapter().decide(CONTEXT, [TOOL], timeout=5)
    assert FakeHarness.closed


def test_later_phases_keep_existing_adapter(monkeypatch):
    monkeypatch.setattr(ResearchModelAdapter, 'decide', lambda *a, **k: ('existing', {}))
    assert adapter().decide({'phase': 'research'}, [], timeout=1) == ('existing', {})


def test_tools_reject_unmounted_calls_and_conflicting_second_decision():
    tools = IntakeTools([TOOL])
    assert not tools.call('search_sources', {})['ok']
    assert tools.result is None
    assert tools.call('record_input_document', {'summary': 'one'})['ok']
    assert tools.call('record_input_document', {'summary': 'one'})['ok']
    assert not tools.call('record_input_document', {'summary': 'two'})['ok']


def test_real_sdk_round_trip_is_metered_and_only_exposes_intake_tool():
    """Run the installed SDK + MCP subprocesses against a deterministic provider."""
    import httpx
    from deepseek_harness import DeepSeekHarness
    calls, ledger = [], []

    def complete(request):
        body = json.loads(request.content)
        calls.append(body)
        names = [tool['function']['name'] for tool in body.get('tools', [])]
        assert len(names) == 1 and names[0].endswith('record_input_document'), names
        tool_results = [m for m in body['messages'] if m['role'] == 'tool']
        message = {'role': 'assistant', 'content': '已提交'} if tool_results else {
            'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call_intake', 'type': 'function',
            'function': {'name': names[0], 'arguments': json.dumps({'summary': '工具调用'})}}]}
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
    assert model.decide(CONTEXT, [TOOL], timeout=30) == ('record_input_document', {'summary': '工具调用'})
    assert len(calls) == len(ledger) == 2
    assert all(row['usage']['total_tokens'] == 60 for row in ledger)
    assert all(row['response_data']['runtime'] == 'deepseek-harness' for row in ledger)


@pytest.mark.parametrize('case', ['meter_denied', 'context_limit', 'call_limit', 'truncated'])
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
    assert len(calls) == (4 if case == 'call_limit' else 1 if case == 'truncated' else 0)
    assert len(finishes) == len(calls)
