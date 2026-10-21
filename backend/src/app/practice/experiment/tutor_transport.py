"""Streaming chat transport using the application's configured model and failover."""
import json

import httpx

from app.chat.bounded_completion import BoundedModelAdapter, strict_json
from app.services.runtime_config_resolver import runtime_config_resolver


class TutorModel:
    def __init__(self, gateway, client_factory=httpx.AsyncClient):
        self.gateway, self.client_factory = gateway, client_factory

    @classmethod
    def for_owner(cls, owner):
        config = runtime_config_resolver.resolve('llm', owner_user_id=owner)
        return cls(BoundedModelAdapter.from_config(config).gateway)

    async def stream(self, messages, tools):
        if len(json.dumps(messages, ensure_ascii=False).encode()) > 450000:
            raise ValueError('本次相关记录过大，请选择一个具体操作提问')
        previous_status = None
        for candidate in self.gateway.candidates:
            if candidate.get('only_after_status') and candidate['only_after_status'] != previous_status:
                continue
            model = candidate['model_name']
            extra = self.gateway._thinking_params(model)
            if str(model).lower().startswith('deepseek-v4'):
                extra = {**extra, 'thinking': {'type': 'disabled'}}
            payload = {'model': model, 'messages': messages, 'stream': True,
                       'max_tokens': 2400, 'temperature': 0.3, **extra}
            if tools:
                payload.update(tools=tools, tool_choice='auto', parallel_tool_calls=False)
            emitted = False
            try:
                async with self.client_factory(timeout=httpx.Timeout(85, connect=15), trust_env=candidate.get('trust_env', True)) as client:
                    async with client.stream('POST', candidate['api_base'].rstrip('/') + '/chat/completions',
                                             headers=self.gateway._build_headers(candidate.get('api_key')), json=payload) as response:
                        response.raise_for_status()
                        if 'text/event-stream' not in response.headers.get('content-type', ''):
                            # Some compatible providers ignore stream=true.
                            body = bytearray()
                            async for chunk in response.aiter_bytes():
                                body.extend(chunk)
                                if len(body) > 1000000:
                                    raise ValueError('模型回答过大')
                            parsed = BoundedModelAdapter.parse(strict_json(body))
                            if parsed['content']:
                                yield {'type': 'delta', 'text': parsed['content']}
                            yield {'type': 'result', **parsed}
                            return
                        content, calls, finished, size = '', {}, None, 0
                        async for line in response.aiter_lines():
                            size += len(line)
                            if size > 1000000:
                                raise ValueError('模型回答过大')
                            if not line.startswith('data:'):
                                continue
                            raw = line[5:].strip()
                            if raw == '[DONE]':
                                break
                            if not raw:
                                continue
                            data = strict_json(raw)
                            if data.get('error'):
                                raise ValueError('模型流中断')
                            choices = data.get('choices', [])
                            if not choices:
                                continue
                            if len(choices) != 1:
                                raise ValueError('模型返回了多个回答')
                            choice = choices[0]
                            delta = choice.get('delta') or {}
                            text = delta.get('content') or ''
                            if not isinstance(text, str):
                                raise ValueError('模型流格式无效')
                            if text:
                                emitted = True
                                content += text
                                yield {'type': 'delta', 'text': text}
                            for fragment in delta.get('tool_calls') or []:
                                index = fragment.get('index')
                                if not isinstance(index, int) or not 0 <= index < 8:
                                    raise ValueError('工具调用过多')
                                call = calls.setdefault(index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                                if fragment.get('id'):
                                    call['id'] += fragment['id']
                                function = fragment.get('function') or {}
                                call['function']['name'] += function.get('name') or ''
                                call['function']['arguments'] += function.get('arguments') or ''
                            if choice.get('finish_reason'):
                                finished = choice['finish_reason']
                        # Reject truncated streams even if they contain convincing text.
                        parsed = BoundedModelAdapter.parse({'choices': [{
                            'finish_reason': finished,
                            'message': {'content': content, 'tool_calls': [calls[i] for i in sorted(calls)]}}]})
                        yield {'type': 'result', **parsed}
                        return
            except httpx.HTTPStatusError as exc:
                previous_status = exc.response.status_code
                if emitted or previous_status != 402:
                    raise RuntimeError('教学模型服务暂不可用') from None
        raise RuntimeError('教学模型服务暂不可用，请检查模型配置')
