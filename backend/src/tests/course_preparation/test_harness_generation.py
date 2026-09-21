"""Native SDK protocol evidence is distinct from real-model content quality."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading
from types import SimpleNamespace
from urllib.request import Request, urlopen

import httpx
import pytest

from app.course_preparation.harness_generation import (
    ContentTools, PreparationHarnessGateway, accept_resource_text, scoped_gateway,
)
from app.course_preparation import workflow_skills


@pytest.fixture
def content_skills(tmp_path, monkeypatch):
    # Business-owned D/E/F skills are intentionally not authored by these tests.
    root = tmp_path / 'skills'
    for name in set(workflow_skills.CONTENT_PHASE_SKILLS.values()):
        directory = root / name
        directory.mkdir(parents=True)
        (directory / 'SKILL.md').write_text(
            f'---\nname: {name}\ndescription: Protocol fixture only\n---\n'
            'Return the requested candidate using the mounted submission tool.\n')
    monkeypatch.setattr(workflow_skills, 'SKILLS_ROOT', root)


class Ledger:
    def __init__(self):
        self.actions = []
        self.lock = threading.Lock()

    def begin_action(self, context, key, kind, payload, cost):
        with self.lock:
            action = {'action_id': key, 'kind': kind, 'payload': payload,
                      'reserved': cost.model_dump(), 'context': context.copy()}
            self.actions.append(action)
        return action

    def finish_action(self, context, action_id, receipt, actual=None, failed=False):
        action = next(a for a in self.actions if a['action_id'] == action_id)
        action.update(receipt=receipt, status='failed' if failed else 'completed', actual=actual)


class ProtocolHarness:
    """Deterministic SDK stand-in to inject faults around the real bridges."""
    missing_skill = False
    close_error = False
    closes = 0

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.patch = json.loads(Path(kwargs['patches'][0]).read_text())

    def __enter__(self):
        return self

    def close(self):
        type(self).closes += 1
        if self.close_error:
            raise RuntimeError('close fault')

    def run(self, prompt, **kwargs):
        entries = self.patch[-1]['insert']
        config = next(p['config'] for p in entries if p['id'] == 'preparation-mcp')
        skill_root = next(p['config']['customSkillDirs'][0] for p in entries if p['id'] == 'preparation-skill-files')
        skill_file = next(Path(skill_root).glob('*/SKILL.md'))
        body = skill_file.read_text().split('---', 2)[2].strip()
        loaded = f'<skill_content name="{skill_file.parent.name}"><skill_instructions>\n{body}\n</skill_instructions></skill_content>'
        payload = {'messages': [{'role': 'user', 'content': prompt if self.missing_skill else loaded + '\n' + prompt}],
                   'tools': [{'type': 'function', 'function': {'name': 'submit_resource_text'}}]}

        def post(url, token, data):
            request = Request(url, data=json.dumps(data).encode(), headers={
                'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            with urlopen(request, timeout=5) as response:
                return json.load(response)

        response = post(self.kwargs['base_url'] + '/chat/completions', self.kwargs['api_key'], payload)
        message = response['choices'][0]['message']
        for call in message.get('tool_calls', []):
            post(config['env']['EDU_MCP_URL'], self.kwargs['env']['EDU_MCP_TOKEN'], {
                'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
                    'name': call['function']['name'], 'arguments': json.loads(call['function']['arguments'])}})
        if message.get('tool_calls'):
            # A terminal acknowledgement must never reach the upstream model.
            post(self.kwargs['base_url'] + '/chat/completions', self.kwargs['api_key'], payload)
        return SimpleNamespace(finish_reason='stop')


def gateway(complete, *, sdk_factory=ProtocolHarness, context=None, **kwargs):
    configured = SimpleNamespace(candidates=[{'model_name': 'deepseek-v4-flash', 'api_base': 'http://provider/v1',
        'api_key': 'test-secret', 'provider': 'fixture'}], _build_headers=lambda key: {}, _thinking_params=lambda name: {})
    ledger = Ledger()
    root = PreparationHarnessGateway(configured, ledger, context or {'artifact_id': 'a', 'spec_digest': 'spec-a'},
        deadline=(datetime.now(timezone.utc) + timedelta(seconds=40)).isoformat(),
        sdk_factory=sdk_factory, client_factory=lambda **kw: httpx.Client(transport=httpx.MockTransport(complete), **kw), **kwargs)
    return root, ledger


def completion(text='正文', *, arguments=None, reason='tool_calls', mutate=None):
    def complete(request):
        payload = json.loads(request.content)
        name = next(t['function']['name'] for t in payload['tools'] if t['function']['name'] != 'skill')
        assert name.endswith('submit_resource_text')
        if mutate:
            mutate(payload)
        message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'c1', 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps({'text': text} if arguments is None else arguments)}}]}
        if reason == 'stop':
            message = {'role': 'assistant', 'content': 'no submission'}
        return httpx.Response(200, json={'id': 'fixture', 'object': 'chat.completion', 'created': 1,
            'model': payload['model'], 'choices': [{'index': 0, 'message': message, 'finish_reason': reason}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}})
    return complete


@pytest.mark.parametrize('arguments', [{}, {'text': ''}, {'text': ' '}, {'text': 2}, {'text': 'ok', 'path': '/tmp/x'}, []])
def test_submission_is_strict_and_does_not_deliver_invalid_text(arguments):
    with pytest.raises(ValueError):
        accept_resource_text(arguments)
    tools = ContentTools(lambda: None)
    assert not tools.call('submit_resource_text', arguments)['ok']
    assert tools.result is None
    assert tools.fatal is not None


def test_only_submission_tool_and_one_result_are_available():
    tools = ContentTools(lambda: None)
    assert [tool['name'] for tool in tools.schemas()] == ['submit_resource_text']
    assert tools.call('submit_resource_text', {'text': 'one'})['ok']
    assert not tools.call('submit_resource_text', {'text': 'two'})['ok']
    assert tools.invalid
    assert not ContentTools(lambda: None).call('shell', {'command': 'anything'})['ok']


@pytest.mark.parametrize('phase', workflow_skills.CONTENT_PHASE_SKILLS)
def test_real_sdk_and_mcp_submit_report_or_quiz_with_phase_evidence(content_skills, phase):
    from deepseek_harness import DeepSeekHarness
    text = '# 工具调用\n模型提出调用，服务端验证后执行。' if phase.endswith('write') else '{"questions":[{"id":"q1","answer":"A"}]}'
    requests = []
    root, ledger = gateway(completion(text, mutate=requests.append), sdk_factory=DeepSeekHarness)
    bound = scoped_gateway(root, phase=phase, context={'node_id': 'tools'}, preparation=True)
    assert bound.chat([{'role': 'user', 'content': '提交指定内容'}], max_tokens=10000) == text
    assert len(requests) == len(ledger.actions) == 1
    action = ledger.actions[0]
    response = action['receipt']['model_response']
    assert response['phase'] == phase
    assert response['runtime'] == 'deepseek-harness'
    assert response['skill']['loaded'] is True and response['skill']['sha256']
    assert response['spec_digest'] == 'spec-a'
    assert response['provider'] == 'fixture'
    assert response['model'] == 'deepseek-v4-flash'
    assert response['response']['usage']['total_tokens'] == 70
    assert action['actual'].tokens == 70
    assert action['payload']['output_limit'] == requests[0]['max_tokens'] == 10000
    names = [t['function']['name'] for t in requests[0]['tools']]
    assert len(names) == 2 and 'skill' in names


@pytest.mark.parametrize('case', ['empty', 'arguments', 'unsubmitted', 'truncated', 'skill_unloaded'])
def test_protocol_failures_never_deliver_or_fall_back(content_skills, case):
    factory = type('Harness', (ProtocolHarness,), {'missing_skill': case == 'skill_unloaded', 'closes': 0})
    complete = completion(text='' if case == 'empty' else 'ok',
        arguments={'text': 'ok', 'path': 'bad'} if case == 'arguments' else None,
        reason={'unsubmitted': 'stop', 'truncated': 'length'}.get(case, 'tool_calls'))
    root, ledger = gateway(complete, sdk_factory=factory)
    with pytest.raises((ValueError, RuntimeError)):
        root.for_phase('resource_write', context={}).chat([])
    assert len(ledger.actions) == (0 if case == 'skill_unloaded' else 3 if case == 'truncated' else 1)
    assert factory.closes == 1


def test_missing_business_skill_fails_before_model(monkeypatch, tmp_path):
    monkeypatch.setattr(workflow_skills, 'SKILLS_ROOT', tmp_path)
    root, ledger = gateway(lambda request: pytest.fail('no provider call'))
    with pytest.raises(RuntimeError, match='WORKFLOW_SKILL_UNAVAILABLE'):
        root.for_phase('resource_write', context={}).chat([])
    assert not ledger.actions


def test_preparation_requires_explicit_phase_and_legacy_workbench_is_unchanged():
    old = SimpleNamespace(chat=lambda messages: 'legacy')
    assert scoped_gateway(old, phase='anything', context={}, preparation=False) is old
    with pytest.raises(RuntimeError, match='PREPARATION_HARNESS_REQUIRED'):
        scoped_gateway(old, phase='resource_write', context={}, preparation=True)
    root, _ = gateway(completion())
    with pytest.raises(RuntimeError, match='HARNESS_PHASE_REQUIRED'):
        root.chat([])
    with pytest.raises(RuntimeError, match='HARNESS_PHASE_UNKNOWN'):
        root.for_phase('unknown', context={})


def test_concurrent_views_preserve_node_phase_and_output_budgets(content_skills):
    requests = []
    root, ledger = gateway(completion(mutate=requests.append))
    context = {'node_id': 'n1', 'requirements': ['exact requirement']}
    write = root.for_phase('resource_write', context=context)
    review = root.for_phase('resource_review', context={'node_id': 'n2'})
    context['requirements'].clear()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pair: pair[0].chat([], max_tokens=pair[1]), [(write, 12000), (review, 65536)]))
    assert results == ['正文', '正文']
    assert root.phase is None
    assert write._phase_context['requirements'] == ['exact requirement']
    by_phase = {a['receipt']['model_response']['phase']: a for a in ledger.actions}
    assert by_phase['resource_review']['payload']['output_limit'] == 65536
    assert by_phase['resource_write']['payload']['output_limit'] == 12000
    for body in requests:
        prompt = body['messages'][0]['content']
        assert ('"node_id": "n1"' in prompt) != ('"node_id": "n2"' in prompt)


def test_cancel_during_response_settles_usage_but_never_submits(content_skills):
    canceled = threading.Event()
    root, ledger = gateway(completion(mutate=lambda _: canceled.set()), canceled=canceled.is_set)
    with pytest.raises(RuntimeError, match='CANCELED'):
        root.for_phase('resource_write', context={}).chat([])
    assert len(ledger.actions) == 1 and ledger.actions[0]['actual'].tokens == 70


def test_close_failure_keeps_original_protocol_error(content_skills):
    factory = type('Harness', (ProtocolHarness,), {'close_error': True, 'closes': 0})
    root, ledger = gateway(completion(reason='length'), sdk_factory=factory)
    with pytest.raises(ValueError, match='MODEL_PROTOCOL_ERROR: incomplete response after two corrections'):
        root.for_phase('resource_write', context={}).chat([])
    assert len(ledger.actions) == 3 and factory.closes == 1


def test_successful_submission_with_close_failure_is_not_deliverable(content_skills):
    factory = type('Harness', (ProtocolHarness,), {'close_error': True, 'closes': 0})
    root, _ = gateway(completion(), sdk_factory=factory)
    with pytest.raises(RuntimeError, match='HARNESS_SHUTDOWN_FAILED'):
        root.for_phase('resource_write', context={}).chat([])


def test_hard_context_limits_and_phase_quotas_fail_before_provider(content_skills):
    root, ledger = gateway(completion(), context_tokens=13000)
    bound = root.for_phase('resource_write', context={'requirements': ['must keep ' * 4000]})
    with pytest.raises(RuntimeError, match='CONTEXT_BUDGET_EXCEEDED'):
        bound.chat([])
    with pytest.raises(RuntimeError, match='OUTPUT_BUDGET_INVALID'):
        bound.chat([], max_tokens=65536)
    assert not ledger.actions


def test_course_review_uses_native_structured_tool_route(content_skills):
    from deepseek_harness import DeepSeekHarness
    from app.course_preparation.harness_adapter import HarnessPreparationAdapter
    tool = {'type': 'function', 'function': {'name': 'review_course_delivery', 'description': 'review',
        'parameters': {'type': 'object', 'properties': {'decision': {'type': 'string'}}, 'required': ['decision']}}}
    calls = []

    def complete(request):
        body = json.loads(request.content)
        calls.append(body)
        results = [m for m in body['messages'] if m['role'] == 'tool']
        if results:
            message = {'role': 'assistant', 'content': 'finished'}
        else:
            name = next(t['function']['name'] for t in body['tools'] if t['function']['name'] != 'skill')
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'course', 'type': 'function',
                'function': {'name': name, 'arguments': '{"decision":"pass"}'}}]}
        return httpx.Response(200, json={'id': 'course', 'object': 'chat.completion', 'created': 1,
            'model': body['model'], 'choices': [{'index': 0, 'message': message,
                'finish_reason': 'stop' if results else 'tool_calls'}], 'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}})

    root, _ = gateway(complete, sdk_factory=DeepSeekHarness)
    adapter = HarnessPreparationAdapter(root.configured, sdk_factory=DeepSeekHarness, client_factory=root.client_factory)
    assert adapter.decide({'phase': 'course_review', 'node': {'node_key': 'n1'}}, [tool], timeout=30) == (
        'review_course_delivery', {'decision': 'pass'})
    assert adapter.last_packet_metadata['phase'] == 'course_review'
    assert adapter.last_packet_metadata['skill_name'] == 'review-course-delivery'
    assert len(calls) == 1


@pytest.mark.parametrize('case', ['canceled', 'expired', 'lease_lost'])
def test_lifecycle_guard_prevents_new_requests(content_skills, case):
    def guard():
        if case == 'lease_lost':
            raise RuntimeError('STALE_ARTIFACT_LEASE')
    root, ledger = gateway(lambda request: pytest.fail('provider must not run'),
                           canceled=lambda: case == 'canceled', guard=guard)
    if case == 'expired':
        root.deadline = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    code = {'canceled': 'CANCELED', 'expired': 'BUDGET_EXHAUSTED', 'lease_lost': 'STALE_ARTIFACT_LEASE'}[case]
    with pytest.raises(RuntimeError, match=code):
        root.for_phase('resource_write', context={}).chat([])
    assert not ledger.actions


def test_slow_canceled_response_is_joined_and_cannot_leave_background_work(content_skills):
    import time
    canceled, entered, finished = threading.Event(), threading.Event(), threading.Event()
    def slow(payload):
        entered.set()
        time.sleep(.15)
        finished.set()
    factory = type('Harness', (ProtocolHarness,), {'closes': 0})
    root, ledger = gateway(completion(mutate=slow), sdk_factory=factory, canceled=canceled.is_set)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(root.for_phase('resource_write', context={}).chat, [])
        assert entered.wait(3)
        canceled.set()
        with pytest.raises(RuntimeError, match='CANCELED'):
            pending.result(timeout=5)
    assert finished.is_set() and factory.closes == 1
    assert ledger.actions[0]['actual'].tokens == 70


def test_sdk_unavailable_fails_without_model_or_fallback(content_skills, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'deepseek_harness', None)
    root, ledger = gateway(lambda request: pytest.fail('no model call'), sdk_factory=None)
    with pytest.raises(RuntimeError, match='HARNESS_UNAVAILABLE'):
        root.for_phase('resource_write', context={}).chat([])
    assert not ledger.actions


def test_long_review_crosses_legacy_bridge_limit_without_truncation(content_skills):
    from deepseek_harness import DeepSeekHarness
    text = '审' * 50000
    root, ledger = gateway(completion(text), sdk_factory=DeepSeekHarness)
    assert root.for_phase('resource_review', context={}).chat([], max_tokens=65536) == text
    assert len(ledger.actions) == 1


@pytest.mark.parametrize('response', [httpx.Response(200, json=[]), httpx.Response(200, content=b'{broken')])
def test_invalid_provider_json_settles_reservation_once_with_phase(content_skills, response):
    root, ledger = gateway(lambda request: response)
    with pytest.raises(ValueError):
        root.for_phase('resource_write', context={}).chat([])
    assert len(ledger.actions) == 1
    action = ledger.actions[0]
    assert action['status'] == 'failed'
    assert action['actual'].tokens == action['reserved']['tokens']
    assert action['receipt']['model_response']['phase'] == 'resource_write'
    assert action['receipt']['model_response']['skill']['loaded'] is True
