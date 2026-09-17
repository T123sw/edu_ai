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


def test_complete_preserves_provider_usage_without_transport_metadata():
    payload={'choices':[{'finish_reason':'stop','message':{'content':'{}'}}],
             'usage':{'prompt_tokens':123,'completion_tokens':8,'total_tokens':131,'internal':'omit'}}
    def factory(**kwargs):return httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=payload)),**kwargs)
    result=asyncio.run(LearningModelAdapter(Gateway(),factory).complete([],[],deadline=time.monotonic()+5))
    assert result['model']=='test' and result['usage']=={'prompt_tokens':123,'completion_tokens':8,'total_tokens':131}
