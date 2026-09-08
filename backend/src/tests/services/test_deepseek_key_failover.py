import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from core.config import Config
from app.services import deepseek_key_failover as failover


@pytest.fixture
def upstream(monkeypatch):
    calls = []
    settings = {'primary': 402, 'backup': 200, 'stream': False}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            key = self.headers.get('Authorization', '').removeprefix('Bearer ')
            body = self.rfile.read(int(self.headers['Content-Length']))
            calls.append((key, body))
            status = settings[key]
            self.send_response(status)
            self.send_header('Content-Type', 'text/event-stream' if settings['stream'] and status == 200 else 'application/json')
            self.end_headers()
            completion = {'id': 'mock', 'object': 'chat.completion', 'model': 'test',
                          'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'hello'}, 'finish_reason': 'stop'}]}
            self.wfile.write(b'data: {"text":"hello"}\n\ndata: [DONE]\n\n' if settings['stream'] and status == 200 else json.dumps(completion if status == 200 else {'status': status}).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}/v1'
    monkeypatch.setattr(Config, 'DEEPSEEK_BASE_URL', base)
    monkeypatch.setattr(Config, 'DEEPSEEK_API_KEY_BACKUP', 'backup')
    yield base, calls, settings
    for identity, (_, _, local) in list(failover._endpoints.items()):
        if identity[0] == base:
            local.shutdown()
            local.server_close()
            del failover._endpoints[identity]
    server.shutdown()
    server.server_close()
    thread.join()


def request(base, token, body=b'{"model":"same-model","messages":[]}'):
    return httpx.post(base + '/chat/completions', content=body, headers={'Authorization': 'Bearer ' + token}, trust_env=False)


def test_balance_failure_retries_same_request_with_second_key(upstream, caplog):
    base, calls, _ = upstream
    endpoint, token = failover.completion_endpoint(base, 'primary')
    assert token not in ('primary', 'backup')
    response = request(endpoint, token)
    assert response.status_code == 200
    assert [c[0] for c in calls] == ['primary', 'backup']
    assert calls[0][1] == calls[1][1]
    assert 'HTTP 402' in caplog.text


@pytest.mark.parametrize('status, expected', [(200, ['primary']), (400, ['primary']), (429, ['primary']), (500, ['primary'])])
def test_only_balance_failure_triggers_key_switch(upstream, status, expected):
    base, calls, settings = upstream
    settings['primary'] = status
    endpoint, token = failover.completion_endpoint(base, 'primary')
    assert request(endpoint, token).status_code == status
    assert [c[0] for c in calls] == expected


def test_both_empty_balances_stop_after_two_attempts(upstream):
    base, calls, settings = upstream
    settings['backup'] = 402
    assert request(*failover.completion_endpoint(base, 'primary')).status_code == 402
    assert len(calls) == 2


def test_stream_is_forwarded_once_after_switch(upstream):
    base, calls, settings = upstream
    settings['stream'] = True
    response = request(*failover.completion_endpoint(base, 'primary'))
    assert response.text == 'data: {"text":"hello"}\n\ndata: [DONE]\n\n'
    assert len(calls) == 2


def test_disabled_backup_and_other_hosts_are_untouched(upstream, monkeypatch):
    base, calls, _ = upstream
    assert failover.completion_endpoint('https://unrelated.example/v1', 'primary') == ('https://unrelated.example/v1', 'primary')
    for backup in ('', 'primary'):
        monkeypatch.setattr(Config, 'DEEPSEEK_API_KEY_BACKUP', backup)
        assert failover.completion_endpoint(base, 'primary') == (base, 'primary')
    assert calls == []


def test_local_transport_rejects_unauthenticated_requests(upstream):
    base, calls, _ = upstream
    endpoint, _ = failover.completion_endpoint(base, 'primary')
    assert request(endpoint, 'wrong').status_code == 403
    assert calls == []


def test_revision_model_client_uses_key_failover(upstream):
    from app.chat.agents.report_generation import _chat_model
    base, calls, _ = upstream
    model = _chat_model(api_key='primary', base_url=base, model='test', timeout_seconds=10)
    assert model.invoke('hello').content == 'hello'
    assert [c[0] for c in calls] == ['primary', 'backup']


def test_generation_gateway_uses_key_failover(upstream):
    from app.chat.model_gateway import ChatModelGateway
    base, calls, _ = upstream
    gateway = ChatModelGateway(api_base=base, api_key='primary', model_name='test')
    assert gateway.chat([{'role': 'user', 'content': 'hello'}]) == 'hello'
    assert [c[0] for c in calls] == ['primary', 'backup']


def test_harness_switches_current_completion_without_restarting_turn(upstream, tmp_path):
    from types import SimpleNamespace
    from app.chat.harness.runtime import HarnessRuntime
    from app.chat.harness.store import HarnessStore
    from app.chat.domain.conversation_snapshot import ConversationSnapshot
    from tests.chat.test_harness_runtime import request as chat_request, toolset
    base, calls, _ = upstream
    turns = []
    class SDK:
        def __init__(self, **kwargs): self.config = kwargs
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def close(self): pass
        def run(self, prompt, **kwargs):
            turns.append(prompt)
            response = request(self.config['base_url'], self.config['api_key'])
            return SimpleNamespace(final_response=response.json()['choices'][0]['message']['content'], finish_reason='stop')
    runtime = HarnessRuntime(store=HarnessStore(tmp_path), base_url=base, api_key='primary', sdk_factory=SDK,
                             tool_factory=lambda request, session, **kw: toolset(request, session, **kw))
    result = runtime.run(request=chat_request(question='你好', request_id='key-failover'), snapshot=ConversationSnapshot())
    assert result['message']['content'] == 'hello'
    assert len(turns) == 1
    assert [c[0] for c in calls] == ['primary', 'backup']
