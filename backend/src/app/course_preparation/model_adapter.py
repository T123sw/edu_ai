"""Strict, non-streaming function calls using existing gateway provider configuration."""
import json
import time
from pathlib import Path

import httpx

from .research_agent import ResearchError

PROMPTS = Path(__file__).parent / 'prompts'


class ResearchModelAdapter:
    def __init__(self, gateway, *, client_factory=httpx.Client, context_tokens=128000, meter=None):
        self.gateway = gateway
        self.client_factory = client_factory
        self.context_tokens = context_tokens
        self.meter = meter

    @staticmethod
    def parse(data, allowed_names):
        if not isinstance(data, dict):
            raise ValueError('MODEL_PROTOCOL_ERROR: 响应必须是对象')
        choices = data.get('choices') or []
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict) or choices[0].get('finish_reason') != 'tool_calls':
            raise ValueError('MODEL_PROTOCOL_ERROR: 必须正常完成一次工具调用；截断或纯文本不能执行')
        message = choices[0].get('message')
        if not isinstance(message, dict):
            raise ValueError('MODEL_PROTOCOL_ERROR: message 必须是对象')
        calls = message.get('tool_calls') or []
        if not isinstance(calls, list) or len(calls) != 1 or not isinstance(calls[0], dict) or not calls[0].get('id') or calls[0].get('type') != 'function':
            raise ValueError('MODEL_PROTOCOL_ERROR: 每轮必须恰有一个有ID的function调用')
        function = calls[0].get('function') or {}
        if not isinstance(function, dict):
            raise ValueError('MODEL_PROTOCOL_ERROR: function 必须是对象')
        if function.get('name') not in allowed_names:
            raise ValueError('TOOL_NOT_AVAILABLE: 该工具未挂载')
        raw = function.get('arguments')
        if not isinstance(raw, str):
            raise ValueError('MODEL_PROTOCOL_ERROR: 参数必须是完整JSON字符串')
        args = json.loads(raw)
        if not isinstance(args, dict):
            raise ValueError('MODEL_PROTOCOL_ERROR: 参数必须是JSON对象')
        return function['name'], args

    def decide(self, context, tools, *, timeout):
        self.last_rejected_decision = None
        from .context import context_packet
        packet = context_packet(context, tools, max_tokens=self.context_tokens)
        self.last_packet_metadata = {key:value for key,value in packet.items() if key != 'messages'}
        messages = packet['messages']
        deadline = time.monotonic() + timeout
        for candidate in self.gateway.candidates:
            remaining = deadline - time.monotonic()
            if remaining <= 1:
                break
            model = str(candidate['model_name'])
            extra = self.gateway._thinking_params(model)
            if model.lower().startswith('deepseek-v4'):
                extra = {**extra, 'thinking': {'type': 'disabled'}}
            payload = {'model': model, 'messages': messages, 'tools': tools, 'tool_choice': 'required',
                       'temperature': 0.1, 'max_tokens': 6000, 'stream': False, 'parallel_tool_calls': False, **extra}
            action = self.meter.start(input_upper_bound=packet['input_token_upper_bound'], output_limit=6000, model=model) if self.meter else None
            try:
                with self.client_factory(timeout=httpx.Timeout(remaining, connect=min(10, remaining))) as client:
                    with client.stream('POST', candidate['api_base'].rstrip('/') + '/chat/completions',
                            headers=self.gateway._build_headers(candidate.get('api_key')), json=payload) as response:
                        response.raise_for_status()
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            body.extend(chunk)
                            if len(body) > 2_000_000 or time.monotonic() >= deadline:
                                raise ValueError('MODEL_PROTOCOL_ERROR: 响应超长或超过总时限')
                        data = json.loads(body)
                if self.meter:
                    self.meter.finish(action, usage=data.get('usage') if isinstance(data,dict) else None, response_data=data)
                try:
                    return self.parse(data, {t['function']['name'] for t in tools})
                except ValueError:
                    self.last_rejected_decision = data
                    raise
            except httpx.HTTPError:
                if self.meter:
                    self.meter.finish(action, failed=True)
                # No tool was executed; a fallback may retry only this completion.
                continue
        raise ResearchError('PROVIDER_UNAVAILABLE', '模型服务不可用，未执行未确认的工具动作')
