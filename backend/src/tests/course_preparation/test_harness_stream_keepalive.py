import importlib
import json
import time

import httpx
import pytest

from tests.course_preparation.test_harness_intake import adapter


@pytest.mark.parametrize('failure', [False, True])
def test_native_stream_stays_alive_while_upstream_is_buffered(monkeypatch, failure):
    provider = importlib.import_module('app.course_preparation.harness_provider')
    monkeypatch.setattr(provider, 'STREAM_HEARTBEAT_SECONDS', .02)
    requests, ledger = [], []

    def complete(request):
        requests.append(json.loads(request.content))
        time.sleep(.3)  # longer than downstream's read timeout
        if failure:
            return httpx.Response(503)
        return httpx.Response(200, json={'id': 'delayed', 'model': 'test',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': 'validated result'}}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 8}})

    class Meter:
        def start(self, **kwargs):
            ledger.append({})
            return ledger[-1]

        def finish(self, action, **kwargs):
            action.update(kwargs)

    model = adapter(client_factory=lambda **kwargs: httpx.Client(
        transport=httpx.MockTransport(complete), **kwargs), meter=Meter())
    model.native_workflow = True
    model.gateway._build_headers = lambda key: {}
    model.gateway._thinking_params = lambda name: {}
    with provider.harness_provider(model, timeout=3) as (url, token, state):
        with httpx.Client(timeout=httpx.Timeout(.1, connect=1), trust_env=False) as client:
            with client.stream('POST', url + '/chat/completions',
                    headers={'Authorization': 'Bearer ' + token},
                    json={'stream': True, 'messages': [], 'tools': []}) as response:
                lines = list(response.iter_lines())
        assert ': keepalive' in lines
        data = [line for line in lines if line.startswith('data: ')]
        assert len(data) == 2 and data[-1] == 'data: [DONE]'
        assert ('error' in json.loads(data[0][6:])) == failure
        assert bool(state['error']) == failure
        assert state['completed_calls'] == (0 if failure else 1)
    assert len(requests) == len(ledger) == 1
    assert requests[0]['stream'] is False
    assert ledger[0].get('failed', False) == failure


def test_native_sdk_ignores_heartbeat_comments_and_dispatches_once(monkeypatch):
    from deepseek_harness import DeepSeekHarness
    from tests.course_preparation.test_harness_intake import CONTEXT, TOOL
    provider = importlib.import_module('app.course_preparation.harness_provider')
    monkeypatch.setattr(provider, 'STREAM_HEARTBEAT_SECONDS', .02)
    requests = []

    def complete(request):
        body = json.loads(request.content)
        requests.append(body)
        time.sleep(.15)
        name = next(t['function']['name'] for t in body['tools']
                    if t['function']['name'] != 'skill')
        return httpx.Response(200, json={'id': 'native-heartbeat', 'object': 'chat.completion',
            'created': 1, 'model': 'test', 'choices': [{'index': 0, 'finish_reason': 'tool_calls',
                'message': {'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': 'c1', 'type': 'function', 'function': {
                        'name': name, 'arguments': '{"summary":"accepted once"}'}}]}}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 8}})

    model = adapter(DeepSeekHarness, client_factory=lambda **kwargs: httpx.Client(
        transport=httpx.MockTransport(complete), **kwargs))
    model.native_workflow = True
    model.gateway._build_headers = lambda key: {}
    model.gateway._thinking_params = lambda name: {}
    assert model.decide({**CONTEXT, 'phase': 'resource_write'}, [TOOL], timeout=30) == (
        'record_input_document', {'summary': 'accepted once'})
    assert len(requests) == 1
