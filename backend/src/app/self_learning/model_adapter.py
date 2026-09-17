"""Strict buffered completion transport; cancellation closes the actual HTTP request."""
import asyncio
import json
import time
import logging
import httpx
from .turn_contracts import AgentFailure


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


class LearningModelAdapter:
    def __init__(self, gateway, client_factory=httpx.AsyncClient):
        self.gateway, self.client_factory = gateway, client_factory

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
                if call['type'] != 'function' or not isinstance(call['id'], str) or not call['id'] or call['id'] in ids:
                    raise ValueError()
                ids.add(call['id'])
                fn = call['function']
                if not isinstance(fn['name'], str) or not isinstance(fn['arguments'], str) or len(fn['arguments']) > 30000:
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
                for candidate in self.gateway.candidates:
                    received = False
                    model = candidate['model_name']
                    extra = self.gateway._thinking_params(model)
                    if str(model).lower().startswith('deepseek-v4'):
                        extra = {**extra, 'thinking': {'type': 'disabled'}}
                    payload = {'model': model, 'messages': messages, 'stream': False, 'max_tokens': 2000, 'temperature': 0.2, **extra}
                    if tools:
                        payload.update(tools=tools, tool_choice='auto', parallel_tool_calls=False)
                    else:
                        payload['response_format'] = {'type': 'json_object'}
                    try:
                        timeout = max(.01, deadline - time.monotonic())
                        async with self.client_factory(timeout=httpx.Timeout(timeout, connect=min(10, timeout))) as client:
                            async with client.stream('POST', candidate['api_base'].rstrip('/') + '/chat/completions',
                                headers=self.gateway._build_headers(candidate.get('api_key')), json=payload) as response:
                                response.raise_for_status()
                                body = bytearray()
                                async for chunk in response.aiter_bytes():
                                    received = True
                                    body.extend(chunk)
                                    if len(body) > 2_000_000:
                                        raise AgentFailure('MODEL_PROTOCOL_ERROR')
                                data=strict_json(body)
                                parsed=self.parse(data)
                                usage=data.get('usage') or {}
                                return {**parsed,'model':model,'usage':{k:v for k,v in usage.items()
                                    if k in ('prompt_tokens','completion_tokens','total_tokens') and type(v) is int and v>=0}}
                    except httpx.HTTPError as exc:
                        logging.getLogger(__name__).warning('Learning model attempt failed model=%s error=%s status=%s',
                            model, type(exc).__name__, exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None)
                        if received:
                            raise AgentFailure('MODEL_CONNECTION_INTERRUPTED') from exc
                        continue
                    except (ValueError, TypeError) as exc:
                        raise AgentFailure('MODEL_PROTOCOL_ERROR') from exc
        except TimeoutError as exc:
            raise AgentFailure('DEADLINE_EXCEEDED') from exc
        raise AgentFailure('MODEL_UNAVAILABLE')
