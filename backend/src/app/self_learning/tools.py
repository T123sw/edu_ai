"""Frozen P3 read-only registry. Identity and resource access remain server-owned."""
import base64
from dataclasses import dataclass
import json
from typing import Annotated, Literal
from pydantic import Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database import ConversationMessage
from .db_models import LearningTopicSession
from .contracts import Actor, Contract, Identifier, Locator, ResourceRef
from .model_adapter import strict_json
from .progress_repository import digest
from .resource_reader import exact_material, excerpt, material_text


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

    def schema(self):
        return {'type': 'function', 'function': {'name': self.name, 'description': self.description, 'parameters': self.input_model.model_json_schema()}}


class LearningTools:
    def __init__(self, learning, turn, packet):
        self.learning, self.turn, self.packet = learning, turn, packet
        specs = [ToolSpec('read_resource_excerpt', '读取已授权资料准确版本的片段；已有片段足够时无需调用', ReadExcerpt, self.read),
                 ToolSpec('search_course_resources', '搜索当前可读课程资料，结果不代表已读正文', SearchResources, self.resources),
                 ToolSpec('read_course_learning_summary', '读取本人当前课程的学习事实和自评，不推断掌握', ReadSummary, self.summary),
                 ToolSpec('search_learning_history', '搜索本人当前课程对话的短片段', SearchHistory, self.history)]
        self.registry = {s.name: s for s in specs}
        if len(self.registry) != len(specs) or any(s.effect != 'read' or not callable(s.handler) for s in specs):
            raise ValueError('invalid P3 registry')
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
            args = spec.input_model.model_validate(strict_json(call['function']['arguments']))
            self.learning.require(self.turn['course_id'], self.turn['owner'])
            return ToolResult.model_validate(spec.handler(args)).model_dump(mode='json')
        except (ValidationError, ValueError, TypeError, KeyError):
            return ToolResult(ok=False, error={'code': 'INVALID_ARGUMENTS', 'message': '工具参数无效', 'retryable': False}).model_dump()
        except HTTPException:
            return ToolResult(ok=False, error={'code': 'ACCESS_OR_VERSION_UNAVAILABLE', 'message': '当前资料或版本不可读取', 'retryable': False}).model_dump()

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
        citation = {'citation_id': cid, 'resource_ref': raw, 'locator': piece['resolved_locator'], 'content_hash': piece['content_hash']}
        self.packet['citations'][cid] = citation
        return ToolResult(ok=True, data=piece, citations=[citation], truncated=piece['truncated']).model_dump()

    def page(self, args, items):
        fingerprint = digest([self.turn['owner'], self.turn['turn_id'], args.model_dump(exclude={'cursor'})])
        offset = 0
        if args.cursor:
            parsed = json.loads(base64.urlsafe_b64decode(args.cursor.encode()))
            if parsed[0] != fingerprint or type(parsed[1]) is not int or parsed[1] < 0:
                raise ValueError()
            offset = parsed[1]
        more = offset + args.limit < len(items)
        cursor = base64.urlsafe_b64encode(json.dumps([fingerprint, offset + args.limit]).encode()).decode() if more else None
        return ToolResult(ok=True, data={'items': items[offset:offset + args.limit]}, truncated=more, next_cursor=cursor).model_dump()

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
                at = (resource['title'] + '\n' + text).casefold().find(args.query.casefold())
                if at < 0:
                    continue
                handle = 'res_' + digest(ref.model_dump())[:24]
                self.packet['handles'][handle] = ref.model_dump()
                snippet = excerpt(material, query=args.query, max_chars=500)['excerpt']
                items.append({'resource_handle': handle, 'title': resource['title'], 'topic_id': topic['id'], 'snippet': snippet})
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
        with Session(self.learning.session_repository.engine) as db:
            rows = db.execute(select(ConversationMessage, LearningTopicSession.topic_id).join(LearningTopicSession,
                LearningTopicSession.session_id == ConversationMessage.conversation_id).where(
                LearningTopicSession.owner == self.turn['owner'], LearningTopicSession.course_id == self.turn['course_id'],
                LearningTopicSession.topic_id.in_(allowed), ConversationMessage.content.contains(args.query, autoescape=True)
            ).order_by(ConversationMessage.occurred_at.desc(), ConversationMessage.message_id).limit(200)).all()
            items = []
            for message, topic in rows:
                at = message.content.casefold().find(args.query.casefold())
                items.append({'message_ids': [message.message_id], 'topic_id': topic, 'session_ref': message.conversation_id,
                    'excerpt': message.content[max(0, at - 100):max(0, at - 100) + 600], 'occurred_at': message.occurred_at.isoformat()})
        return self.page(args, items)
