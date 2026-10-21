"""Replay node decision failures through the real SDK and MCP bridge."""
from copy import deepcopy
import json

import httpx
import pytest
from deepseek_harness import DeepSeekHarness

from app.course_preparation.harness_adapter import PreparationTools
from app.course_preparation.harness_provider import CompletionFormatError
from app.course_preparation.node_research import NodeEvidenceAssessment, review_node
from app.course_preparation.research_agent import ResearchAgent
from tests.course_preparation.test_harness_intake import adapter
from tests.course_preparation.test_research_flow import Model, Sources, run


@pytest.mark.parametrize('failure', [None, 'extra', 'missing', 'type', 'source', 'batch', 'insufficient', 'persistent'])
def test_node_review_recovers_schema_before_dispatch_and_preserves_judgment(monkeypatch, failure):
    state = run(ResearchAgent(model=Model(), sources=Sources()))
    before = state.model_dump(mode='json')
    requests, ledger, dispatched = [], [], []
    original_call = PreparationTools.call

    def record_call(self, name, arguments):
        dispatched.append((name, arguments))
        return original_call(self, name, arguments)

    monkeypatch.setattr(PreparationTools, 'call', record_call)
    valid = {'sufficient': failure != 'insufficient', 'reason': '按已读正文独立核对',
             'source_refs': ['source_1'], 'gap_queries': ['补充递减参数的具体实例'] if failure == 'insufficient' else []}

    def complete(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert not dispatched  # No malformed or partial batch reached MCP.
        name = next(t['function']['name'] for t in payload['tools'] if t['function']['name'].endswith('assess_node_evidence'))
        arguments = deepcopy(valid)
        invalid = failure is not None and (len(requests) == 1 or failure == 'persistent')
        if invalid:
            if failure == 'missing':
                arguments.pop('sufficient')
            elif failure == 'type':
                arguments['sufficient'] = 'yes'
            elif failure == 'source':
                arguments['source_refs'] = ['source_invented']
            else:
                arguments['sufficient_again'] = True
        if len(requests) > 1:
            feedback = payload['messages'][-1]['content']
            assert 'schema' in feedback and '整批工具均未执行' in feedback
            if failure in ('extra', 'batch', 'insufficient', 'persistent'):
                assert 'sufficient_again' in feedback
        values = [valid, arguments] if failure == 'batch' and invalid else [arguments]
        return httpx.Response(200, json={'id': 'node-review', 'object': 'chat.completion', 'created': 1,
            'model': 'test', 'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {
                'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': f'node-{i}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(value)}}
                    for i, value in enumerate(values)]}}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 10, 'total_tokens': 60}})

    class Meter:
        def start(self, **kwargs):
            ledger.append({})
            return ledger[-1]

        def finish(self, action, **kwargs):
            action.update(kwargs)

    model = adapter(DeepSeekHarness, client_factory=lambda **kw: httpx.Client(transport=httpx.MockTransport(complete), **kw), meter=Meter())
    model.gateway._build_headers = lambda key: {}
    model.gateway._thinking_params = lambda name: {}
    if failure == 'persistent':
        with pytest.raises(CompletionFormatError, match='after two corrections') as error:
            review_node(model, state, state.path.nodes[0], timeout=30)
        assert error.value.code == 'MODEL_RESPONSE_INVALID'
        assert len(requests) == len(ledger) == 3
        assert not dispatched
    else:
        result = review_node(model, state, state.path.nodes[0], timeout=30)
        assert result.sufficient == valid['sufficient']
        assert result.source_ids == (state.evidence[0].source_id,)
        assert result.gap_queries == tuple(valid['gap_queries'])
        assert dispatched == [('assess_node_evidence', valid)]
        assert len(requests) == len(ledger) == (1 if failure is None else 2)
    assert state.model_dump(mode='json') == before
    assert [row['response_data']['protocol_recovery_attempt'] for row in ledger] == list(range(len(ledger)))
    assert all(row['usage']['total_tokens'] == 60 for row in ledger)


def test_direct_mcp_cannot_accept_out_of_schema_node_review():
    tool = {'type': 'function', 'function': {'name': 'assess_node_evidence', 'description': 'review',
                                           'parameters': NodeEvidenceAssessment.model_json_schema()}}
    tools = PreparationTools([tool])
    result = tools.call('assess_node_evidence', {'sufficient': True, 'reason': '已核验',
                                             'source_refs': ['source_1'], 'sufficient_again': True})
    assert result['ok'] is False and result['error'] == 'MODEL_RESPONSE_INVALID'
    assert tools.result is None
