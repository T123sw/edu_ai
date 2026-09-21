"""Phase-bound native Harness sessions for private preparation candidates."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import threading
import time

import httpx

from .budget_meter import PreparationModelMeter
from .harness_adapter import HarnessPreparationAdapter
from .research_agent import ResearchError
from .workflow_skills import CONTENT_PHASE_SKILLS


def accept_resource_text(arguments):
    if not isinstance(arguments, dict) or set(arguments) != {'text'}:
        raise ValueError('RESOURCE_TEXT_ARGUMENTS_INVALID')
    text = arguments.get('text')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('RESOURCE_TEXT_EMPTY')
    return text


class ContentTools:
    """One ephemeral submission, with no filesystem or publication capability."""
    terminal_on_result = True
    content_submission = True

    def __init__(self, guard, *, structured=False, response_schema=None):
        self.guard = guard
        self.structured = structured
        self.response_schema = deepcopy(response_schema)
        self.lock = threading.RLock()
        self.result = None
        self.invalid = False
        self.fatal = None
        self.tools = {'submit_resource_text': {
            'name': 'submit_resource_text',
            'description': '提交本轮完整正文或 JSON 字符串；由业务层校验与存储。',
            'parameters': {'type': 'object', 'properties': {'text': {'type': 'string', 'minLength': 1}},
                           'required': ['text'], 'additionalProperties': False},
        }}
        if structured:
            value_schema = deepcopy(response_schema) if response_schema is not None else {'type': 'object', 'additionalProperties': True}
            # References are rooted at the tool parameters, not at value.
            definitions = value_schema.pop('$defs', None)
            self.tools = {'submit_resource_json': {
                'name': 'submit_resource_json',
                'description': '提交本轮结构化结果对象；value 直接放 JSON 对象，不要再次编码为字符串。业务层随后独立校验。',
                'parameters': {'type': 'object', 'properties': {
                    'value': value_schema},
                    'required': ['value'], 'additionalProperties': False},
            }}

            if definitions is not None:
                self.tools['submit_resource_json']['parameters']['$defs'] = definitions

    def schemas(self):
        return [{'name': name, 'description': spec['description'], 'inputSchema': spec['parameters']}
                for name, spec in self.tools.items()]

    def validate_arguments(self, name, arguments):
        if self.response_schema is None or not self.structured:
            return
        from jsonschema import Draft202012Validator
        from .harness_provider import ContentSchemaError
        parameters = self.tools[name]['parameters']
        error = next(Draft202012Validator(parameters).iter_errors(arguments), None)
        if error is not None:
            path = '.'.join(map(str, error.absolute_path)) or '$'
            raise ContentSchemaError(f'{path}: {error.message}'[:1000])

    def check(self):
        if self.fatal is not None:
            raise self.fatal
        self.guard()

    def call(self, name, arguments):
        with self.lock:
            try:
                self.check()
                if name not in self.tools:
                    raise ValueError('TOOL_NOT_AVAILABLE')
                self.validate_arguments(name, arguments)
                if self.structured:
                    if (not isinstance(arguments, dict) or set(arguments) != {'value'}
                            or not isinstance(arguments['value'], dict)):
                        from .harness_provider import CompletionFormatError
                        raise CompletionFormatError('RESOURCE_JSON_OBJECT_REQUIRED')
                    text = json.dumps(arguments['value'], ensure_ascii=False)
                else:
                    text = accept_resource_text(arguments)
                if self.result is not None and self.result != text:
                    raise ValueError('RESOURCE_TEXT_ALREADY_SUBMITTED')
                self.result = text
                return {'ok': True, 'message': '候选已接收；结束本轮，业务层随后校验。'}
            except Exception as exc:
                self.invalid = True
                self.fatal = exc
                return {'ok': False, 'error': getattr(exc, 'code', 'RESOURCE_TEXT_INVALID')}


class PreparationHarnessGateway:
    """Each binding and each chat gets independent context and an SDK session.

    The unbound gateway cannot chat: consumers must explicitly choose write,
    review or repair. The store remains the authority for leases and accounting.
    """
    preparation_harness = True

    def __init__(self, configured, store, context, *, deadline, canceled=lambda: False,
                 guard=lambda: None, client_factory=httpx.Client, sdk_factory=None,
                 context_tokens=128000):
        self.configured, self.store = configured, store
        self.context = deepcopy(context)
        self.deadline, self.canceled, self.guard = deadline, canceled, guard
        self.client_factory, self.sdk_factory = client_factory, sdk_factory
        self.context_tokens = context_tokens
        self.phase = None
        self._phase_context = {}

    def for_phase(self, phase, *, context):
        if phase not in CONTENT_PHASE_SKILLS:
            raise ResearchError('HARNESS_PHASE_UNKNOWN', '备课内容阶段未注册')
        view = type(self)(self.configured, self.store, self.context, deadline=self.deadline,
                          canceled=self.canceled, guard=self.guard, client_factory=self.client_factory,
                          sdk_factory=self.sdk_factory, context_tokens=self.context_tokens)
        view.phase = phase
        view._phase_context = deepcopy(context)
        return view

    def with_response_schema(self, schema):
        return self.for_phase(self.phase, context={**self._phase_context, 'response_schema': schema})

    def chat(self, messages, temperature=.2, max_tokens=12000):
        if self.phase is None:
            raise ResearchError('HARNESS_PHASE_REQUIRED', '备课生成必须显式绑定写作、审阅或修复阶段')
        # Preserve the existing 65k classroom review allowance without raising
        # every writer's quota. Reservations still use the caller's exact limit.
        ceiling = 65536 if self.phase == 'resource_review' else 12000
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 0 < max_tokens <= ceiling:
            raise ResearchError('OUTPUT_BUDGET_INVALID', '当前阶段输出预算不合法')
        remaining = (datetime.fromisoformat(self.deadline) - datetime.now(timezone.utc)).total_seconds()
        timeout = min(120, remaining)
        started = time.monotonic()
        session_deadline = started + timeout
        parent_deadline = started + remaining
        toolset = None

        def check():
            if self.canceled():
                raise ResearchError('CANCELED', '备课生成已取消')
            now = time.monotonic()
            if now >= parent_deadline:
                raise ResearchError('BUDGET_EXHAUSTED', '备课父任务时限耗尽')
            if now >= session_deadline and (toolset is None or toolset.result is None):
                raise ResearchError('PROVIDER_TIMEOUT', 'Harness 本次会话超过时限，尚未提交结果')
            # Submission is checked before result is set. Native final ACK and
            # shutdown may finish afterwards, but cancellation/lease/parent
            # deadline guards still apply to the accepted result.
            self.guard()

        check()
        toolset = ContentTools(check, structured=self._phase_context.get('response_format') == 'json',
                               response_schema=self._phase_context.get('response_schema'))
        adapter = HarnessPreparationAdapter(self.configured, client_factory=self.client_factory,
            context_tokens=self.context_tokens, sdk_factory=self.sdk_factory,
            meter=PreparationModelMeter(self.store, self.context))
        spec = self.context.get('spec', {})
        phase_context = {k: v for k, v in self._phase_context.items() if k != 'response_schema'}
        context = {**phase_context, 'phase': self.phase, 'messages': deepcopy(messages),
                   'artifact_id': self.context.get('artifact_id'),
                   'node_id': spec.get('node_id', self._phase_context.get('node_id'))}
        if self.context.get('spec_digest'):
            context['spec_digest'] = self.context['spec_digest']
        tools = [{'type': 'function', 'function': spec} for spec in toolset.tools.values()]
        try:
            result = adapter._run(context, tools, timeout=timeout, toolset=toolset,
                                  output_tokens=max_tokens, temperature=temperature)
            check()
            return result
        except Exception as exc:
            exc.preparation_phase = self.phase
            raise


def scoped_gateway(gateway, *, phase, context, preparation):
    if not preparation:
        return gateway
    if not getattr(gateway, 'preparation_harness', False) or not callable(getattr(gateway, 'for_phase', None)):
        raise ResearchError('PREPARATION_HARNESS_REQUIRED', '备课阶段需要原生 Harness 网关')
    return gateway.for_phase(phase, context=context)
