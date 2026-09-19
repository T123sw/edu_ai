"""Request-scoped provider transport: meter every Harness completion before sending."""
from contextlib import contextmanager
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
import time

import httpx

from .context import encoded_size
from .research_agent import ResearchError


@contextmanager
def harness_provider(adapter, *, timeout, toolset=None, max_calls=4):
    token = secrets.token_urlsafe(32)
    deadline = time.monotonic() + timeout
    lock = threading.Lock()
    state = {'calls': 0, 'error': None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, body, content_type='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                self.send_error(403)
                return
            if self.path != '/v1/chat/completions':
                self.send_error(404)
                return
            with lock:
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 2_000_000:
                        raise ValueError('MODEL_PROTOCOL_ERROR: invalid request size')
                    payload = json.loads(self.rfile.read(length))
                    required_skill = getattr(adapter, 'required_skill', None)
                    if required_skill:
                        from .workflow_skills import skill_is_loaded
                        if not skill_is_loaded(payload.get('messages', []), required_skill):
                            raise ResearchError('SKILL_NOT_LOADED', '当前阶段 Skill 未由 Harness 加载，未调用模型')
                    if getattr(toolset, 'continuous', False):
                        toolset.check()
                    stream = payload.pop('stream', False)
                    payload.pop('stream_options', None)
                    payload.update(stream=False, max_tokens=6000, parallel_tool_calls=False, temperature=0.1)
                    if toolset is not None and toolset.result is not None:
                        payload['tool_choice'] = 'none'
                    size = encoded_size(payload) + 512
                    if size + 6000 > adapter.context_tokens:
                        raise ResearchError('CONTEXT_BUDGET_EXCEEDED', 'Harness 上下文超过窗口')
                    data = None
                    for candidate in adapter.gateway.candidates:
                        remaining = deadline - time.monotonic()
                        if state['calls'] >= max_calls or remaining <= 0:
                            raise ResearchError('BUDGET_EXHAUSTED', 'Harness 当前决策调用次数或时间已耗尽')
                        state['calls'] += 1
                        model = candidate['model_name']
                        payload['model'] = model
                        payload.update(adapter.gateway._thinking_params(model))
                        if str(model).startswith('deepseek-v4'):
                            payload['thinking'] = {'type': 'disabled'}
                        action = adapter.meter.start(input_upper_bound=size, output_limit=6000, model=model) if adapter.meter else None
                        try:
                            with adapter.client_factory(timeout=httpx.Timeout(remaining, connect=min(10, remaining))) as client:
                                with client.stream('POST', candidate['api_base'].rstrip('/') + '/chat/completions',
                                        headers=adapter.gateway._build_headers(candidate.get('api_key')), json=payload) as response:
                                    response.raise_for_status()
                                    body = bytearray()
                                    for chunk in response.iter_bytes():
                                        body.extend(chunk)
                                        if len(body) > 2_000_000 or time.monotonic() >= deadline:
                                            raise ValueError('MODEL_PROTOCOL_ERROR: response limit exceeded')
                                    data = json.loads(body)
                        except Exception as exc:
                            if adapter.meter:
                                adapter.meter.finish(action, failed=True)
                            if isinstance(exc, httpx.HTTPError):
                                continue
                            raise
                        if adapter.meter:
                            adapter.meter.finish(action, usage=data.get('usage'), response_data={
                                'runtime': 'deepseek-harness',
                                **({'skill': {'name': required_skill['name'], 'sha256': required_skill['sha256'], 'loaded': True}} if required_skill else {}),
                                'response': data})
                        break
                    if data is None:
                        raise ResearchError('PROVIDER_UNAVAILABLE', 'Harness 模型服务不可用')
                    choices = data.get('choices') or []
                    if len(choices) != 1 or choices[0].get('finish_reason') not in ('stop', 'tool_calls'):
                        raise ValueError('MODEL_PROTOCOL_ERROR: incomplete Harness completion')
                    if choices[0]['finish_reason'] == 'tool_calls':
                        from .model_adapter import ResearchModelAdapter
                        allowed = {t['function']['name'] for t in payload.get('tools', [])}
                        calls = (choices[0].get('message') or {}).get('tool_calls')
                        if toolset is None or not isinstance(calls, list) or not calls:
                            ResearchModelAdapter.parse(data, allowed)
                        else:
                            # Validate the entire batch before native SDK dispatch.
                            # Each bridge enforces its live execution policy.
                            ids = set()
                            for call in calls:
                                single = {**choices[0], 'message': {**choices[0]['message'], 'tool_calls': [call]}}
                                ResearchModelAdapter.parse({**data, 'choices': [single]}, allowed)
                                if call['id'] in ids:
                                    raise ValueError('MODEL_PROTOCOL_ERROR: duplicate tool call ID')
                                ids.add(call['id'])
                    state['error'] = None
                    if not stream:
                        self.reply(200, json.dumps(data).encode())
                        return
                    # SDK consumes SSE; keep a complete upstream response for accounting
                    # and deliver its assistant message as one standard delta.
                    choices = []
                    for choice in data['choices']:
                        delta = dict(choice['message'])
                        if delta.get('tool_calls'):
                            delta['tool_calls'] = [dict(call, index=i) for i, call in enumerate(delta['tool_calls'])]
                        choices.append({'index': choice.get('index', 0), 'delta': delta,
                                        'finish_reason': choice['finish_reason']})
                    event = {**data, 'object': 'chat.completion.chunk', 'choices': choices}
                    self.reply(200, ('data: ' + json.dumps(event) + '\n\ndata: [DONE]\n\n').encode(), 'text/event-stream')
                except Exception as exc:
                    state['error'] = exc
                    self.reply(502, b'{"error":{"message":"Preparation Harness completion failed"}}')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', token, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        with lock:
            pass
