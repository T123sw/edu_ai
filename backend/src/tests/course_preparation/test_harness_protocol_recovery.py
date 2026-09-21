import json
import httpx
import pytest
from deepseek_harness import DeepSeekHarness
from tests.course_preparation.test_harness_intake import adapter, CONTEXT, TOOL


@pytest.mark.parametrize('first_failure', ['invalid_json', 'length'])
def test_native_session_requests_corrected_json_without_dispatching_invalid_arguments(first_failure):
    requests, ledger = [], []
    def complete(request):
        payload = json.loads(request.content)
        requests.append(payload)
        name = next(t['function']['name'] for t in payload['tools'] if t['function']['name'] != 'skill')
        if len(requests) == 1:
            arguments = '{"summary":"bad"'
        else:
            assert ('JSON' if first_failure == 'invalid_json' else '截断') in json.dumps(payload['messages'], ensure_ascii=False)
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
