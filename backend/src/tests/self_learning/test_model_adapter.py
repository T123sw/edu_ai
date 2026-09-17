import asyncio
import time
import httpx
import pytest
from app.self_learning.model_adapter import LearningModelAdapter
from app.self_learning.turn_contracts import AgentFailure

def response(finish='tool_calls', arguments='{}'):
    return {'choices': [{'finish_reason': finish, 'message': {'tool_calls': [
        {'id': 'call1', 'type': 'function', 'function': {'name': 'read_course_learning_summary', 'arguments': arguments}}]}}]}

@pytest.mark.parametrize('data', [response('length'), response(arguments='{'), response(arguments='[]'), response(arguments='{"x":1,"x":2}'), {'choices': []}])
def test_broken_or_truncated_calls_never_dispatch(data):
    with pytest.raises(AgentFailure):
        LearningModelAdapter.parse(data)

def test_normal_final_and_function_calls():
    assert LearningModelAdapter.parse(response())['calls'][0]['id'] == 'call1'
    assert LearningModelAdapter.parse({'choices': [{'finish_reason': 'stop', 'message': {'content': 'answer'}}]}) == {'content': 'answer', 'calls': []}

class Gateway:
    candidates = [{'api_base': 'http://model.test/v1', 'api_key': None, 'model_name': 'test'}]
    _thinking_params = staticmethod(lambda _: {})
    _build_headers = staticmethod(lambda _: {})

def test_deadline_cancels_underlying_http_stream():
    closed = []
    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            try:
                await asyncio.sleep(5)
                yield b'{}'
            finally:
                closed.append(True)
    def factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Slow())), **kwargs)
    async def run():
        with pytest.raises(AgentFailure) as failure:
            await LearningModelAdapter(Gateway(), factory).complete([], [], deadline=time.monotonic() + .04)
        assert failure.value.code == 'DEADLINE_EXCEEDED'
    asyncio.run(run())
    assert closed

def test_partial_response_does_not_fallback():
    seen = []
    class Broken(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"choices":'
            raise httpx.ReadError('interrupted')
    def handle(request):
        seen.append(request.url)
        return httpx.Response(200, stream=Broken())
    gateway = Gateway()
    gateway.candidates = gateway.candidates * 2
    async def run():
        with pytest.raises(AgentFailure) as failure:
            await LearningModelAdapter(gateway, lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handle), **kw)).complete([], [], deadline=time.monotonic() + 1)
        assert failure.value.code == 'MODEL_CONNECTION_INTERRUPTED'
    asyncio.run(run())
    assert len(seen) == 1

@pytest.mark.parametrize('status, expected', [(402, ['primary', 'backup']), (401, ['primary']), (400, ['primary'])])
def test_config_uses_direct_async_transport_and_scoped_402_backup(monkeypatch, status, expected):
    from core.config import Config
    monkeypatch.setattr(Config, 'DEEPSEEK_BASE_URL', 'https://provider.test')
    monkeypatch.setattr(Config, 'DEEPSEEK_API_KEY_BACKUP', 'backup')
    monkeypatch.setattr(Config, 'resolve_llm_api_key', staticmethod(lambda *_: 'primary'))
    seen = []
    def handle(request):
        assert request.url.host == 'provider.test'
        seen.append(request.headers['Authorization'].removeprefix('Bearer '))
        return httpx.Response(status if len(seen) == 1 else 200,
            json={'choices': [{'finish_reason': 'stop', 'message': {'content': 'ok'}}]})
    adapter = LearningModelAdapter.from_config({'base_url': 'https://provider.test', 'api_key': 'alias', 'model': 'deepseek-v4-pro'},
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handle), **kw))
    async def run():
        if status == 402:
            assert (await adapter.complete([], [], deadline=time.monotonic() + 1))['content'] == 'ok'
        else:
            with pytest.raises(AgentFailure):
                await adapter.complete([], [], deadline=time.monotonic() + 1)
    asyncio.run(run())
    assert seen == expected
    other = LearningModelAdapter.from_config({'base_url': 'https://other.test', 'api_key': 'own', 'model': 'test'})
    assert len(other.gateway.candidates) == 1
    assert other.gateway.candidates[0]['api_key'] == 'own'


def test_only_final_answer_accepts_single_json_fence():
    from app.self_learning.model_adapter import answer_json, strict_json
    assert answer_json('```json\n{"answer_markdown":"ok"}\n```')['answer_markdown'] == 'ok'
    for raw in ['prefix\n```json\n{}\n```', '```json\n{"x":1,"x":2}\n```', '{} trailing']:
        with pytest.raises(ValueError):
            answer_json(raw)
    with pytest.raises(ValueError):
        strict_json('```json\n{}\n```')
