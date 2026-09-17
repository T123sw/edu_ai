"""Frozen P3 read-only registry. Identity and resource access remain server-owned."""
import base64
from dataclasses import dataclass
import json
import asyncio
import time
from typing import Annotated, Literal
from types import MappingProxyType
from pydantic import Field, ValidationError, model_validator
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database import ConversationMessage
from .db_models import LearningTopicSession
from .contracts import Actor, Contract, Identifier, Locator, ResourceRef
from .model_adapter import strict_json
from .progress_repository import digest
from .resource_reader import exact_material, excerpt, material_text
from app.chat.memory.repository import _tokens


class ReadExcerpt(Contract):
    resource_handle: Identifier
    locator: Locator | None = None
    query: str = Field(default='', max_length=500)
    max_chars: Annotated[int, Field(strict=True, ge=1, le=6000)] = 4000


class SearchResources(Contract):
    query: str = Field(min_length=1, max_length=500)
    scope_handle: Literal['current_course'] = 'current_course'
    topic_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    limit: Annotated[int, Field(strict=True, ge=1, le=8)] = 5
    cursor: str | None = Field(default=None, max_length=1024)


class SearchHistory(SearchResources):
    limit: Annotated[int, Field(strict=True, ge=1, le=4)] = 4


class ReadSummary(Contract):
    topic_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    include_open_questions: bool = True


class ReadPreferences(Contract):
    fields: list[Literal['language', 'detail', 'example_order', 'prior_knowledge', 'available_minutes']] = Field(default_factory=list, max_length=5)


class UpdatePreference(Contract):
    operation: Literal['set', 'delete']
    field: Literal['language', 'detail', 'example_order', 'prior_knowledge', 'available_minutes']
    scope: Literal['global', 'course']
    value: str | None = Field(default=None, max_length=600)
    source_quote: str = Field(min_length=1, max_length=2000)
    expected_revision: int | None = Field(default=None, ge=0)
    @model_validator(mode='after')
    def operation_value(self):
        if self.operation == 'set' and not self.value or self.operation == 'delete' and self.value is not None:
            raise ValueError('value is required only for set')
        return self


class OfferCheck(Contract):
    objective_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    preferred_form: Literal['choice', 'short_answer'] = 'choice'


class SubmitPreparation(Contract):
    operation: Literal['supplement_node', 'revise_resource']
    goal: str = Field(min_length=1, max_length=2000)
    resource_types: list[Literal['report', 'quiz']] = Field(default_factory=lambda: ['report'], min_length=1, max_length=2)
    resource_handle: Identifier | None = None


class GetPreparation(Contract):
    preparation_id: Identifier


class ToolResult(Contract):
    ok: bool
    data: dict | None = None
    citations: list[dict] = Field(default_factory=list)
    error: dict | None = None
    truncated: bool = False
    next_cursor: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[Contract]
    handler: object
    effect: str = 'read'
    min_phase: int = 3
    schema_version: int = 1
    modes: tuple[str, ...] = ('answer',)
    timeout_seconds: float = 3
    output_model: type[Contract] = ToolResult

    def schema(self):
        return {'type': 'function', 'function': {'name': self.name, 'description': self.description, 'parameters': self.input_model.model_json_schema()}}


class LearningTools:
    def __init__(self, learning, turn, packet):
        self.learning, self.turn, self.packet = learning, turn, packet
        specs = [ToolSpec('read_resource_excerpt', '读取已授权资料准确版本的片段；已有片段足够时无需调用', ReadExcerpt, self.read),
                 ToolSpec('search_course_resources', '搜索当前可读课程资料，结果不代表已读正文', SearchResources, self.resources),
                 ToolSpec('read_course_learning_summary', '读取本人当前课程的学习事实和自评，不推断掌握', ReadSummary, self.summary),
                 ToolSpec('search_learning_history', '搜索本人当前课程对话的短片段', SearchHistory, self.history)]
        if getattr(learning, 'memory', None):
            specs.extend([ToolSpec('read_learning_preferences', '读取本人有效长期偏好；当前要求优先', ReadPreferences, self.preferences, min_phase=4),
                ToolSpec('update_learning_preference', '仅依据当前用户明确长期设置/删除原话修改指定作用域偏好；value 必须直接出现在原话中', UpdatePreference, self.preference_update, effect='write', min_phase=4)])
        if getattr(learning, 'checks', None):
            specs.append(ToolSpec('offer_understanding_check', '用户愿意检查时提供一道可跳过的理解检查；保存题目不代表已作答或已掌握', OfferCheck, self.offer_check, effect='write', min_phase=4, timeout_seconds=30))
        if getattr(learning, 'preparations', None):
            specs.extend([ToolSpec('submit_preparation_request', '仅依据用户当前明确保存/生成资料或修改当前资料的请求提交后台准备任务；目标不清先询问。收据accepted不是交付成功', SubmitPreparation, self.submit_preparation, effect='write', min_phase=5),
                ToolSpec('get_preparation_status', '读取本人准备任务真实状态；成功后用户自行打开，不自动跳转', GetPreparation, self.preparation_status, min_phase=5)])
        self.registry = MappingProxyType({s.name: s for s in specs})
        if len(self.registry) != len(specs) or any(s.effect not in {'read', 'write'} or not callable(s.handler) for s in specs):
            raise ValueError('invalid learning registry')
        json.dumps(self.schemas())

    def schemas(self):
        return [spec.schema() for spec in self.registry.values()]

    def room(self):
        return self.learning.room(self.turn['course_id'], self.turn['owner'])

    def dispatch(self, call):
        try:
            name = call['function']['name']
            spec = self.registry.get(name)
            if spec is None:
                return ToolResult(ok=False, error={'code': 'UNKNOWN_TOOL', 'message': '本轮未挂载此工具', 'retryable': False}).model_dump()
            if spec.effect != 'read':
                return ToolResult(ok=False, error={'code': 'ASYNC_DISPATCH_REQUIRED', 'message': '写工具须使用有界幂等执行入口'}).model_dump()
            args = spec.input_model.model_validate(strict_json(call['function']['arguments']))
            self.learning.require(self.turn['course_id'], self.turn['owner'])
            return spec.output_model.model_validate(spec.handler(args)).model_dump(mode='json')
        except (ValidationError, ValueError, TypeError, KeyError):
            return ToolResult(ok=False, error={'code': 'INVALID_ARGUMENTS', 'message': '工具参数无效', 'retryable': False}).model_dump()
        except HTTPException:
            return ToolResult(ok=False, error={'code': 'ACCESS_OR_VERSION_UNAVAILABLE', 'message': '当前资料或版本不可读取', 'retryable': False}).model_dump()

    async def dispatch_write(self, call):
        spec = self.registry[call['function']['name']]
        try:
            args = spec.input_model.model_validate(strict_json(call['function']['arguments']))
            self.learning.require(self.turn['course_id'], self.turn['owner'])
            operation_id = self.turn['turn_id'] + ':' + digest([spec.name, args.model_dump()])[:32]
            result = spec.handler(args, operation_id)
            if asyncio.iscoroutine(result):
                result = await result
            return ToolResult(ok=True, data=result).model_dump(mode='json')
        except (ValueError, ValidationError, TypeError):
            return ToolResult(ok=False, error={'code': 'INVALID_ARGUMENTS', 'message': '工具参数无效'}).model_dump()
        except HTTPException as exc:
            return ToolResult(ok=False, error={'code': 'WRITE_REJECTED', 'message': str(exc.detail), 'retryable': exc.status_code == 409}).model_dump()

    def reconcile_memory_epoch(self, call, current_epoch):
        if call['function']['name'] != 'update_learning_preference':
            return False
        from .enrichment_models import LearningEnrichmentReceipt
        try:
            args = UpdatePreference.model_validate(strict_json(call['function']['arguments']))
        except ValueError:
            return False
        operation_id = self.turn['turn_id'] + ':' + digest(['update_learning_preference', args.model_dump()])[:32]
        with Session(self.learning.session_repository.engine) as db:
            receipt = db.get(LearningEnrichmentReceipt, (self.turn['owner'], operation_id))
            return bool(receipt and receipt.result.get('memory_epoch') == current_epoch)

    def submit_preparation(self, args, operation_id):
        return self.learning.preparations.submit(self.turn, args.model_dump(), self.packet, operation_id)

    def preparation_status(self, args):
        result = self.learning.preparations.get(self.turn['owner'], args.preparation_id)
        if result['target']['course_id'] != self.turn['course_id']:
            raise HTTPException(404)
        return ToolResult(ok=True, data=result).model_dump()

    def preferences(self, args):
        result = self.learning.memory.read(self.turn['owner'], self.turn['course_id'])
        if args.fields:
            result['items'] = [i for i in result['items'] if i['field'] in args.fields]
        return ToolResult(ok=True, data=result).model_dump()

    def preference_update(self, args, operation_id):
        result = self.learning.memory.apply_explicit_request(self.turn, args.model_dump(), operation_id, self.packet.get('memory_epoch'))
        self.packet['memory_epoch'] = result['memory_epoch']
        return result

    async def offer_check(self, args, operation_id):
        result = await self.learning.checks.offer(self.turn['owner'], self.turn['course_id'], self.turn['topic_id'], operation_id,
            objective_ids=args.objective_ids, preferred_form=args.preferred_form)
        self.packet.setdefault('actions', {})[result['check_id']] = {'kind': 'understanding_check', **result}
        return result

    def read(self, args):
        raw = self.packet['handles'].get(args.resource_handle)
        if raw is None:
            return ToolResult(ok=False, error={'code': 'SCOPE_NOT_GRANTED', 'message': '未知资料句柄', 'retryable': False}).model_dump()
        ref = ResourceRef.model_validate(raw)
        room = self.room()
        if not any(r.get('remote') and r['remote']['materialType'] == ref.material_type and r['remote']['materialId'] == ref.material_id for c in room['chapters'] for r in c['resources']):
            raise HTTPException(404)
        material = exact_material(self.learning, self.turn['owner'], ref)
        piece = excerpt(material, locator=args.locator.model_dump(exclude_none=True) if args.locator else None, query=args.query, max_chars=args.max_chars)
        cid = 'ctx_' + str(len(self.packet['citations']) + 1).zfill(2)
        citation = {'citation_id': cid, 'title': material.get('title', ''), 'visibility': material.get('visibility', 'private'), 'resource_ref': raw, 'locator': piece['resolved_locator'], 'content_hash': piece['content_hash']}
        self.packet['citations'][cid] = citation
        return ToolResult(ok=True, data=piece, citations=[citation], truncated=piece['truncated']).model_dump()

    def cursor_scope(self, args):
        fingerprint = digest([self.turn['owner'], self.turn['turn_id'], args.model_dump(exclude={'cursor'})])
        offset = 0
        if args.cursor:
            parsed = json.loads(base64.urlsafe_b64decode(args.cursor.encode()))
            if parsed[0] != fingerprint or type(parsed[1]) is not int or parsed[1] < 0:
                raise ValueError()
            offset = parsed[1]
        return fingerprint, offset

    def page(self, args, items, already_paged=False):
        fingerprint, offset = self.cursor_scope(args)
        more = len(items) > args.limit if already_paged else offset + args.limit < len(items)
        cursor = base64.urlsafe_b64encode(json.dumps([fingerprint, offset + args.limit]).encode()).decode() if more else None
        return ToolResult(ok=True, data={'items': items[:args.limit] if already_paged else items[offset:offset + args.limit]}, truncated=more, next_cursor=cursor).model_dump()

    def resources(self, args):
        items = []
        for topic in self.room()['chapters']:
            if args.topic_ids and topic['id'] not in args.topic_ids:
                continue
            for resource in topic['resources']:
                remote = resource.get('remote')
                if not remote:
                    continue
                ref = ResourceRef(course_id=remote['courseId'], material_type=remote['materialType'], material_id=remote['materialId'], version=remote['version'])
                try:
                    material = exact_material(self.learning, self.turn['owner'], ref)
                except HTTPException:
                    continue
                text = material_text(material)
                searchable = resource['title'] + '\n' + text
                overlap = _tokens(searchable) & _tokens(args.query)
                at = searchable.casefold().find(args.query.casefold())
                if at < 0 and not overlap:
                    continue
                handle = 'res_' + digest(ref.model_dump())[:24]
                self.packet['handles'][handle] = ref.model_dump()
                snippet = excerpt(material, query=args.query, max_chars=500)['excerpt']
                items.append({'resource_handle': handle, 'title': resource['title'], 'topic_id': topic['id'], 'snippet': snippet,
                              '_rank': (at >= 0, len(overlap))})
        items.sort(key=lambda i: (-int(i['_rank'][0]), -i['_rank'][1], i['resource_handle']))
        for item in items:
            item.pop('_rank')
        return self.page(args, items)

    def summary(self, args):
        if not self.learning.progress_service:
            return ToolResult(ok=True, data={'nodes': [], 'facts_revision': 0}).model_dump()
        projection = self.learning.progress_service.read(Actor(user_id=self.turn['owner']), self.turn['course_id'])
        return ToolResult(ok=True, data={'nodes': [t for t in projection['topics'] if not args.topic_ids or t['topic_id'] in args.topic_ids],
                                        'facts_revision': projection['facts_revision']}).model_dump()

    def history(self, args):
        allowed = {t['id'] for t in self.room()['chapters']}
        if args.topic_ids:
            allowed &= set(args.topic_ids)
        query_tokens = sorted(_tokens(args.query))[:32]
        with Session(self.learning.session_repository.engine) as db:
            rows = db.execute(select(ConversationMessage, LearningTopicSession.topic_id).join(LearningTopicSession,
                LearningTopicSession.session_id == ConversationMessage.conversation_id).where(
                LearningTopicSession.owner == self.turn['owner'], LearningTopicSession.course_id == self.turn['course_id'],
                LearningTopicSession.topic_id.in_(allowed),
                or_(ConversationMessage.content.contains(args.query, autoescape=True),
                    *[ConversationMessage.content.contains(token, autoescape=True) for token in query_tokens])
            ).order_by(ConversationMessage.occurred_at.desc(), ConversationMessage.message_id)).all()
            memory = getattr(self.learning, 'memory', None)
            items = []
            for message, topic in rows:
                if memory and memory.suppressed(self.turn['owner'], message.message_id, db):
                    continue
                at = message.content.casefold().find(args.query.casefold())
                items.append({'role': message.role, 'message_ids': [message.message_id], 'topic_id': topic, 'session_ref': message.conversation_id,
                    'excerpt': message.content[max(0, at - 100):max(0, at - 100) + 600], 'occurred_at': message.occurred_at.isoformat(),
                    '_rank': (at >= 0, len(set(query_tokens) & _tokens(message.content)))})
        items.sort(key=lambda i: (-int(i['_rank'][0]), -i['_rank'][1], i['message_ids'][0]))
        for item in items:
            item.pop('_rank')
        return self.page(args, items)
