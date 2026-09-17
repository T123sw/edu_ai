"""Frozen P3 read-only registry. Identity and resource access remain server-owned."""
import base64
from dataclasses import dataclass
import json
from typing import Annotated, Literal
from pydantic import Field, ValidationError
from sqlalchemy import select, or_
from app.chat.memory.repository import _tokens
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


class ReadPreferences(Contract):
    pass


class UpdatePreference(Contract):
    axis: Literal['language','response_detail','learning_style','prior_knowledge','available_minutes']
    value: str = Field(min_length=1,max_length=1000)
    scope: Literal['global','current_course']
    source_quote: str = Field(min_length=1,max_length=2000)


class PrepareMaterial(Contract):
    operation: Literal['create_course','supplement_node','revise_resource','adjust_course']
    goal: str = Field(min_length=1,max_length=2000)
    resource_type: Literal['report','quiz','classroom'] = 'report'
    changes: list[str] = Field(default_factory=list,max_length=10)


class OfferCheck(Contract):
    resource_handle: Identifier
    question_id: str | None = Field(default=None,max_length=200)
    stem: str = Field(default='',max_length=2000)
    source_quote: str = Field(default='',max_length=4000)
    reference_citation_id: Identifier | None = None
    objective_ids: list[Identifier] = Field(default_factory=list,max_length=8)


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
        if getattr(learning,'memory_adapter',None):
            specs.append(ToolSpec('read_learning_preferences','读取本人全局及当前课程有效偏好，本次要求优先',ReadPreferences,self.preferences))
            if any(marker in turn['request']['question'] for marker in ('记住','长期','以后都','始终')):
                specs.append(ToolSpec('update_learning_preference','仅按本轮用户原话和明确长期作用域保存偏好；一次性要求不保存，范围不清先询问',UpdatePreference,self.update_preference,effect='write',min_phase=4))
        from .preparation_adapter import requests_saved_work
        if getattr(learning,'checks',None):
            specs.append(ToolSpec('offer_understanding_check','用户要求检查理解时调用。优先用当前节点 quiz 的 question_id；没有合适题目时，提供短答题 stem、已有 reference_citation_id（如 ctx_01）和当前 objective_ids，服务端回读原文作为评价依据，无需重新抄写。也可提供连续逐字 source_quote，不能改写或拼接。保存成功后才展示检查。',OfferCheck,self.offer_check,effect='write',min_phase=4))
        if getattr(learning, 'prepared_courses', None) and requests_saved_work(turn['request']['question']):
            specs.append(ToolSpec('prepare_learning_material','仅在用户明确要求生成保存、补充或修订资料时提交后台准备任务；解释问题不调用。只修改当前阅读资料/节点。',PrepareMaterial,self.prepare,effect='write',min_phase=5))
        self.registry = {s.name: s for s in specs}
        if len(self.registry) != len(specs) or any(s.effect not in ('read','write') or not callable(s.handler) for s in specs):
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
        except HTTPException as exc:
            if exc.status_code==422:
                return ToolResult(ok=False,error={'code':'INVALID_ARGUMENTS','message':str(exc.detail)[:1000],'retryable':False}).model_dump()
            return ToolResult(ok=False, error={'code': 'ACCESS_OR_VERSION_UNAVAILABLE', 'message': '当前资料或版本不可读取', 'retryable': False}).model_dump()

    def preferences(self,args):
        return ToolResult(ok=True,data=self.learning.memory_adapter.read(self.turn['owner'],self.turn['course_id'])).model_dump()

    def update_preference(self,args):
        memory=self.learning.memory_adapter
        result=memory.confirm_from_turn(self.turn,args.axis,args.value,args.scope,args.source_quote,self.packet['memory_context']['memory_epoch'])
        # Own explicit write is acknowledged, then all context is rebuilt before
        # the next model step; old history cannot reintroduce superseded values.
        return ToolResult(ok=True,data=result).model_dump()

    def prepare(self, args):
        from .preparation_adapter import PreparationAdapter
        result=PreparationAdapter(self.learning).submit(self.turn,args.operation,args.goal,resource_type=args.resource_type,changes=args.changes)
        self.packet.setdefault('preparation_receipts',{})[result['preparation_id']]=result
        return ToolResult(ok=True,data={'preparation':result}).model_dump()

    def offer_check(self,args):
        raw=self.packet['handles'].get(args.resource_handle)
        if raw is None:raise ValueError('UNKNOWN_RESOURCE')
        ref=ResourceRef.model_validate(raw)
        if args.question_id:
            result=self.learning.checks.offer(self.turn['owner'],self.turn['course_id'],self.turn['topic_id'],raw,args.question_id)
        else:
            if not args.stem.strip():raise ValueError('QUESTION_REQUIRED')
            quote=args.source_quote
            if args.reference_citation_id:
                citation=self.packet['citations'].get(args.reference_citation_id)
                if citation is None or citation['resource_ref']!=raw:raise ValueError('UNKNOWN_REFERENCE')
                source=excerpt(exact_material(self.learning,self.turn['owner'],ref),locator=citation.get('locator'),max_chars=4000)
                if source['content_hash']!=citation['content_hash']:raise HTTPException(409,'引用版本已变化')
                quote=source['excerpt']
            result=self.learning.checks.offer_immediate(self.turn,ref,stem=args.stem,source_quote=quote,objective_ids=args.objective_ids)
        self.packet.setdefault('understanding_checks',{})[result['check_id']]=result
        return ToolResult(ok=True,data={'check':result}).model_dump()

    def read(self, args):
        raw = self.packet['handles'].get(args.resource_handle)
        if raw is None:
            return ToolResult(ok=False, error={'code': 'SCOPE_NOT_GRANTED', 'message': '未知资料句柄', 'retryable': False}).model_dump()
        ref = ResourceRef.model_validate(raw)
        room = self.room()
        if not any(r.get('remote') and r['remote']['materialType'] == ref.material_type and r['remote']['materialId'] == ref.material_id for c in room['chapters'] for r in c['resources']):
            if ref.model_dump()!=self.turn['request']['reading_context']['resource_ref']:
                raise HTTPException(404)
            from .context_builder import ContextBuilder
            ContextBuilder(self.learning).authorize(self.turn['owner'],ref.course_id,self.turn['topic_id'],self.turn['request']['reading_context'])
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
                haystack = (resource['title'] + '\n' + text).casefold()
                terms = _tokens(args.query) or {args.query.casefold()}
                matched = terms & _tokens(haystack)
                score = len(matched) / len(terms) + (2 if args.query.casefold() in haystack else 0)
                if score <= 0:
                    continue
                handle = 'res_' + digest(ref.model_dump())[:24]
                self.packet['handles'][handle] = ref.model_dump()
                snippet = excerpt(material, query=args.query, max_chars=500)['excerpt']
                items.append({'resource_handle': handle, 'title': resource['title'], 'topic_id': topic['id'], 'snippet': snippet, 'relevance': score})
        items.sort(key=lambda item: (-item['relevance'], item['topic_id'], item['resource_handle']))
        return self.page(args, items)

    def summary(self, args):
        if not self.learning.progress_service:
            return ToolResult(ok=True, data={'nodes': [], 'facts_revision': 0}).model_dump()
        projection = self.learning.progress_service.read(Actor(user_id=self.turn['owner']), self.turn['course_id'])
        nodes=[dict(t) for t in projection['topics'] if not args.topic_ids or t['topic_id'] in args.topic_ids]
        if args.include_open_questions:
            from .observations import ObservationService
            observations=ObservationService(self.learning)
            for node in nodes:
                node['open_questions']=[{'message_id':o['message_id'],'text':o['text'],'status':'hypothesis'} for o in observations.list(
                    self.turn['owner'],self.turn['course_id'],node['topic_id']) if o['status']=='hypothesis' and o['kind']=='confusion']
        return ToolResult(ok=True, data={'nodes': nodes,
                                        'facts_revision': projection['facts_revision']}).model_dump()

    def history(self, args):
        allowed = {t['id'] for t in self.room()['chapters']}
        if args.topic_ids:
            allowed &= set(args.topic_ids)
        terms = sorted(_tokens(args.query) or {args.query.casefold()})
        with Session(self.learning.session_repository.engine) as db:
            rows = db.execute(select(ConversationMessage, LearningTopicSession.topic_id).join(LearningTopicSession,
                LearningTopicSession.session_id == ConversationMessage.conversation_id).where(
                LearningTopicSession.owner == self.turn['owner'], LearningTopicSession.course_id == self.turn['course_id'],
                LearningTopicSession.topic_id.in_(allowed), or_(*[ConversationMessage.content.contains(term, autoescape=True) for term in terms])
            ).order_by(ConversationMessage.occurred_at.desc(), ConversationMessage.message_id).limit(200)).all()
            items = []
            for message, topic in rows:
                memory = getattr(self.learning, 'memory_adapter', None)
                if memory and not memory.permits_history(self.turn['owner'], message): continue
                matched = [term for term in terms if term in message.content.casefold()]
                at = min((message.content.casefold().find(term) for term in matched), default=0)
                items.append({'message_ids': [message.message_id], 'topic_id': topic, 'session_ref': message.conversation_id,
                    'excerpt': message.content[max(0, at - 100):max(0, at - 100) + 600], 'occurred_at': message.occurred_at.isoformat(), 'relevance': len(matched) / len(terms)})
        items.sort(key=lambda item: (-item['relevance'], item['message_ids'][0]))
        return self.page(args, items)
