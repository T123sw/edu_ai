"""Strict buffered completion transport; cancellation closes the actual HTTP request."""
import asyncio
import json
import logging
import time
from types import SimpleNamespace
import httpx
class CompletionFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

AgentFailure = CompletionFailure


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def answer_json(raw):
    # Providers sometimes wrap final JSON in one Markdown fence. Only unwrap
    # that exact envelope; tool arguments always use strict_json unchanged.
    raw = raw.strip()
    if raw.startswith('```json\n') and raw.endswith('\n```'):
        raw = raw[8:-4]
    return strict_json(raw)


class BoundedModelAdapter:
    def __init__(self, gateway, client_factory=httpx.AsyncClient):
        self.gateway, self.client_factory = gateway, client_factory

    @classmethod
    def from_config(cls, config, client_factory=httpx.AsyncClient):
        # Do not construct the legacy gateway: its local synchronous failover
        # proxy outlives cancellation of the downstream HTTP connection.
        from core.config import Config
        from app.chat.harness.content_gateway import ContentGateway
        base = str(config['base_url']).rstrip('/')
        if not base.endswith('/v1'):
            base += '/v1'
        scoped = base.removesuffix('/v1') == str(Config.DEEPSEEK_BASE_URL or '').rstrip('/').removesuffix('/v1')
        primary = Config.resolve_llm_api_key(base, config.get('api_key')) if scoped else config.get('api_key')
        backup = str(Config.DEEPSEEK_API_KEY_BACKUP or '').strip() if scoped else ''
        candidates = [{'api_base': base, 'api_key': primary or backup, 'model_name': config['model'],
                       'trust_env': Config.DEEPSEEK_TRUST_ENV_PROXY if scoped else True}]
        if primary and backup and backup != primary:
            candidates.append({**candidates[0], 'api_key': backup, 'only_after_status': 402})
        return cls(SimpleNamespace(candidates=candidates, _thinking_params=ContentGateway._thinking_params,
                                   _build_headers=ContentGateway._build_headers), client_factory)

    @staticmethod
    def parse(data):
        try:
            choices = data['choices']
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError()
            choice = choices[0]
            message = choice['message']
            if choice['finish_reason'] == 'stop' and not message.get('tool_calls'):
                if not isinstance(message.get('content'), str) or not message['content'].strip():
                    raise ValueError()
                return {'content': message['content'], 'calls': []}
            if choice['finish_reason'] != 'tool_calls':
                raise ValueError()
            calls = message['tool_calls']
            if not isinstance(calls, list) or not calls or len(calls) > 16:
                raise ValueError()
            ids = set()
            for call in calls:
                if call['type'] != 'function' or not isinstance(call['id'], str) or not call['id'] or len(call['id']) > 200 or call['id'] in ids:
                    raise ValueError()
                ids.add(call['id'])
                fn = call['function']
                if not isinstance(fn['name'], str) or len(fn['name']) > 120 or not isinstance(fn['arguments'], str) or len(fn['arguments']) > 30000:
                    raise ValueError()
                if not isinstance(strict_json(fn['arguments']), dict):
                    raise ValueError()
            return {'content': message.get('content') or '', 'calls': calls}
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise AgentFailure('MODEL_PROTOCOL_ERROR') from exc

    async def complete(self, messages, tools, *, deadline):
        if len(json.dumps({'messages': messages, 'tools': tools}, ensure_ascii=False).encode()) > 64000:
            raise AgentFailure('CONTEXT_BUDGET_EXCEEDED')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AgentFailure('DEADLINE_EXCEEDED')
        try:
            async with asyncio.timeout(remaining):
                previous_status = None
                for candidate in self.gateway.candidates:
                    if candidate.get('only_after_status') and candidate['only_after_status'] != previous_status:
                        continue
                    received = False
                    model = candidate['model_name']
                    extra = self.gateway._thinking_params(model)
                    if str(model).lower().startswith('deepseek-v4'):
                        extra = {**extra, 'thinking': {'type': 'disabled'}}
                    payload = {'model': model, 'messages': messages, 'stream': False, 'max_tokens': 2000, 'temperature': 0.2, **extra}
                    if tools:
                        payload.update(tools=tools, tool_choice='auto', parallel_tool_calls=False)
                    try:
                        timeout = max(.01, deadline - time.monotonic())
                        async with self.client_factory(timeout=httpx.Timeout(timeout, connect=min(10, timeout)), trust_env=candidate.get('trust_env', True)) as client:
                            async with client.stream('POST', candidate['api_base'].rstrip('/') + '/chat/completions',
                                headers=self.gateway._build_headers(candidate.get('api_key')), json=payload) as response:
                                response.raise_for_status()
                                body = bytearray()
                                async for chunk in response.aiter_bytes():
                                    received = True
                                    body.extend(chunk)
                                    if len(body) > 2_000_000:
                                        raise AgentFailure('MODEL_PROTOCOL_ERROR')
                                return self.parse(strict_json(body))
                    except httpx.HTTPError as exc:
                        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
                        previous_status = status
                        logging.getLogger(__name__).warning('Learning model transport failed: %s', status)
                        if received:
                            raise AgentFailure('MODEL_CONNECTION_INTERRUPTED') from exc
                        continue
                    except (ValueError, TypeError) as exc:
                        raise AgentFailure('MODEL_PROTOCOL_ERROR') from exc
        except TimeoutError as exc:
            raise AgentFailure('DEADLINE_EXCEEDED') from exc
        raise AgentFailure('MODEL_UNAVAILABLE')
