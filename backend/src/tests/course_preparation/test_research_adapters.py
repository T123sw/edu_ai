from copy import deepcopy
from types import SimpleNamespace
import json

import httpx
import pytest

from app.course_preparation.model_adapter import ResearchModelAdapter
from app.course_preparation.research_sources import ResearchSources, public_url
from app.course_preparation.research_agent import ResearchError
from app.course_preparation import research_sources as module


def response():
    return {'choices': [{'finish_reason': 'tool_calls', 'message': {'tool_calls': [
        {'id': 'call1', 'type': 'function', 'function': {'name': 'search_sources', 'arguments': '{"query":"recursion"}'}}
    ]}}]}


@pytest.mark.parametrize('change', [
    lambda d: d['choices'][0].update(finish_reason='length'),
    lambda d: d['choices'][0].update(finish_reason='stop'),
    lambda d: d['choices'][0]['message']['tool_calls'].append(deepcopy(d['choices'][0]['message']['tool_calls'][0])),
    lambda d: d['choices'][0]['message']['tool_calls'][0]['function'].update(arguments='{broken'),
    lambda d: d['choices'][0]['message']['tool_calls'][0]['function'].update(arguments='[]'),
    lambda d: d['choices'][0]['message']['tool_calls'][0]['function'].update(name='unmounted'),
])
def test_invalid_completion_never_dispatches(change):
    data = response()
    change(data)
    with pytest.raises(ValueError):
        ResearchModelAdapter.parse(data, {'search_sources'})


def test_valid_completion_and_http_failover():
    calls = []
    def handle(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        payload = json.loads(request.content)
        assert not payload['stream'] and payload['tool_choice'] == 'required'
        return httpx.Response(200, json=response())
    gateway = SimpleNamespace(candidates=[{'api_base': 'https://one.test', 'model_name': 'test'},
                                         {'api_base': 'https://two.test', 'model_name': 'test'}],
                              _thinking_params=lambda _: {}, _build_headers=lambda _: {})
    adapter = ResearchModelAdapter(gateway, client_factory=lambda **kw: httpx.Client(transport=httpx.MockTransport(handle), **kw))
    assert adapter.decide({'phase': 'research'}, [{'function': {'name': 'search_sources'}}], timeout=10) == ('search_sources', {'query': 'recursion'})
    assert len(calls) == 2


@pytest.mark.parametrize('url', ['http://127.0.0.1/x', 'http://10.0.0.1', 'http://localhost/',
                                  'http://foo.internal', 'file:///etc/passwd', 'https://user:pass@example.com',
                                  'http://example.com:5555', 'http://[::1]/'])
def test_private_or_unsupported_url_rejected(url):
    with pytest.raises(ValueError):
        public_url(url)


def test_search_snippet_is_not_body(monkeypatch):
    monkeypatch.setattr(module, 'search_tavily', lambda *a, **kw: [SimpleNamespace(
        url='https://example.edu/page#part', title='Title', content='search snippet')])
    monkeypatch.setattr(module, 'extract_tavily', lambda *a, **kw: [SimpleNamespace(
        url='https://example.edu/page', status='failed', content='')])
    source = ResearchSources(tavily_key='test')
    hit = source.search('query', limit=5, timeout=10)[0]
    assert hit['url'] == 'https://example.edu/page'
    with pytest.raises(ResearchError, match='EXTRACT_NO_BODY'):
        source.read(hit['url'], timeout=10)
    with pytest.raises(ResearchError, match='EXTRACT_NOT_CONFIGURED'):
        ResearchSources(tavily_key='').read(hit['url'], timeout=10)


@pytest.mark.parametrize('data', [[], {'choices': [None]}, {'choices': [{}]},
                                  {'choices': [{'finish_reason': 'tool_calls', 'message': []}]}])
def test_malformed_envelope_is_a_protocol_error(data):
    with pytest.raises(ValueError):
        ResearchModelAdapter.parse(data, {'search_sources'})


def test_each_fallback_is_charged_to_parent_budget(runtime_engine):
    from tests.course_preparation.test_runtime_foundation import repo,request
    from app.course_preparation.budget_meter import PreparationModelMeter
    repository=repo(runtime_engine); task=repository.submit('alice',request()); context=repository.claim('worker',preparation_id=task['preparation_id'])
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(503) if len(calls)==1 else httpx.Response(200,json={**response(),'usage':{'total_tokens':100}})
    gateway=SimpleNamespace(candidates=[{'api_base':'https://one.test','model_name':'fixture'},{'api_base':'https://two.test','model_name':'fixture'}],_thinking_params=lambda _: {},_build_headers=lambda _: {})
    adapter=ResearchModelAdapter(gateway,meter=PreparationModelMeter(repository,context),client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(handle),**kw))
    adapter.decide({'phase':'research'},[{'function':{'name':'search_sources'}}],timeout=10)
    budget=repository.get_public('alice',task['preparation_id'])['budget']
    assert budget['consumed']['calls']==2
    assert budget['consumed']['tokens']>100  # Unknown failed-provider use is conservative.
    assert budget['reserved']['calls']==0
    assert budget['consumed']['cost_micro_usd']>0
