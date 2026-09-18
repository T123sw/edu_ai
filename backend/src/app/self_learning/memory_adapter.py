"""Explicit preferences in the shared memory tables, with synchronous invalidation fencing."""
from datetime import datetime, timezone
from uuid import uuid4
import re
from fastapi import HTTPException
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app.database import AgentMemoryItem, UserProfileFact, AgentMemoryAuditEvent
from .enrichment_models import LearningMemoryEpoch, LearningMemorySuppression, LearningContextSummary, LearningEnrichmentReceipt, LearningMemoryOutbox
from .postgres_repository import SessionRepository
from .progress_repository import digest

FIELDS = {'language': 'language', 'detail': 'response_detail', 'example_order': 'learning_style',
          'prior_knowledge': 'prior_knowledge', 'available_minutes': 'available_minutes'}

class MemoryAdapter(SessionRepository):
    def __init__(self, learning, engine):
        super().__init__(engine)
        self.learning = learning

    def epoch(self, owner, db=None):
        if db is None:
            with Session(self.engine) as session:
                return self.epoch(owner, session)
        row = db.get(LearningMemoryEpoch, owner)
        return row.epoch if row else 0

    @staticmethod
    def identity(owner, course, field):
        return 'mem-learning-' + digest([owner, course, field])[:40]

    def suppressed(self, owner, source_id, db=None, field=None):
        if db is None:
            with Session(self.engine) as session:
                return self.suppressed(owner, source_id, session, field)
        query = select(LearningMemorySuppression.source_id).where(
            LearningMemorySuppression.owner == owner, LearningMemorySuppression.source_id == source_id)
        if field:
            query = query.where(LearningMemorySuppression.field == field)
        return db.scalar(query.limit(1)) is not None

    def read(self, owner, course=None):
        if course and self.learning:
            self.learning.require(course, owner)
        with Session(self.engine) as db:
            rows = db.scalars(select(AgentMemoryItem).where(AgentMemoryItem.subject_user_id == owner,
                AgentMemoryItem.status == 'active', or_(AgentMemoryItem.course_id.is_(None), AgentMemoryItem.course_id == course))).all()
            chosen = {}
            for row in sorted(rows, key=lambda r: (r.course_id is not None, r.updated_at, r.memory_id)):
                meta = row.structured_payload or {}
                field = meta.get('learning_field')
                if field not in FIELDS or not meta.get('explicit') or self.suppressed(owner, row.source_id, db, field + ':' + digest(row.course_id)[:12]):
                    continue
                chosen[field] = {'memory_id': row.memory_id, 'field': field, 'value': row.content,
                    'scope': 'course' if row.course_id else 'global', 'revision': meta['revision'], 'source_ref': row.source_id}
            return {'items': [chosen[k] for k in sorted(chosen)], 'memory_epoch': self.epoch(owner, db)}

    def manage(self, owner, course=None):
        # Include tombstone revisions so a later explicit set can use CAS.
        if course and self.learning:
            self.learning.require(course, owner)
        with Session(self.engine) as db:
            rows = db.scalars(select(AgentMemoryItem).where(AgentMemoryItem.subject_user_id == owner,
                or_(AgentMemoryItem.course_id.is_(None), AgentMemoryItem.course_id == course))).all()
            return {'items': [{'memory_id': r.memory_id, 'field': r.structured_payload['learning_field'], 'value': r.content if r.status == 'active' else '',
                'scope': 'course' if r.course_id else 'global', 'revision': r.structured_payload['revision'], 'status': r.status}
                for r in rows if r.structured_payload.get('learning_field') in FIELDS], 'memory_epoch': self.epoch(owner, db)}

    def update(self, owner, course, field, scope, value, expected_revision, *, operation_id, source_id='', source_quote='', explicit=False, expected_epoch=None):
        return self._mutate(owner, course, field, scope, value, expected_revision, operation_id, source_id, source_quote, explicit, expected_epoch)

    def delete(self, owner, course, field, scope, expected_revision, *, operation_id, expected_epoch=None):
        return self._mutate(owner, course, field, scope, None, expected_revision, operation_id, '', '', True, expected_epoch)

    def _mutate(self, owner, course, field, scope, value, expected_revision, operation_id, source_id, quote, explicit, expected_epoch):
        if field not in FIELDS or scope not in {'global', 'course'} or not explicit:
            raise HTTPException(422, '偏好字段、作用域或明确授权无效')
        if scope == 'course' and not course:
            raise HTTPException(422, '缺少课程作用域')
        if course and self.learning:
            self.learning.require(course, owner)
        if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 600):
            raise HTTPException(422, '偏好值无效')
        if field == 'available_minutes' and value is not None and (not value.isdigit() or not 1 <= int(value) <= 1440):
            raise HTTPException(422, '学习时间应为 1 到 1440 分钟')
        target_course = course if scope == 'course' else None
        scoped_field = field + ':' + digest(target_course)[:12]
        fingerprint = digest([target_course, field, value, expected_revision, source_id, quote])
        identity = self.identity(owner, target_course, field)
        now = datetime.now(timezone.utc)
        with self._write('learning-memory:' + owner) as db:
            old_receipt = db.get(LearningEnrichmentReceipt, (owner, operation_id))
            if old_receipt:
                if old_receipt.payload_hash != fingerprint:
                    raise HTTPException(409, '偏好操作标识冲突')
                return old_receipt.result
            row = db.get(AgentMemoryItem, identity)
            revision = (row.structured_payload or {}).get('revision', 0) if row else 0
            if expected_revision != revision:
                raise HTTPException(409, {'message':'偏好已更新，请刷新后重试', 'revision':revision})
            epoch = self.epoch(owner, db)
            if expected_epoch is not None and epoch != expected_epoch:
                raise HTTPException(409, '记忆上下文已变化')
            if source_id and self.suppressed(owner, source_id, db, scoped_field):
                raise HTTPException(409, '该来源已从记忆排除，不能重新抽取')
            if value is None and row is None:
                return {'field': field, 'scope': scope, 'revision': 0, 'memory_epoch': epoch, 'changed': False}
            epoch_row = db.get(LearningMemoryEpoch, owner)
            if not epoch_row:
                epoch_row = LearningMemoryEpoch(owner=owner, epoch=0)
                db.add(epoch_row)
            epoch_row.epoch += 1
            from app.chat.memory.lifecycle import lock_epoch, changed
            from sqlalchemy import inspect
            preparation_epoch = lock_epoch(db, owner) if inspect(db.connection()).has_table('agent_memory_epochs') else None
            scope_filter = AgentMemoryItem.course_id == target_course if target_course else AgentMemoryItem.course_id.is_(None)
            previous = list(db.scalars(select(AgentMemoryItem).where(AgentMemoryItem.subject_user_id == owner,
                scope_filter, AgentMemoryItem.profile_axis == FIELDS[field])))
            for prior in previous:
                prior.status = 'invalidated' if value is None else 'superseded'
                source_ids = set(prior.structured_payload.get('learning_sources', []) + [prior.source_id])
                for source in list(source_ids):
                    if source.endswith(':user'):
                        source_ids.add(source[:-5] + ':assistant')
                for source in source_ids:
                    if source and source != source_id and not db.get(LearningMemorySuppression, (owner, source, scoped_field)):
                        db.add(LearningMemorySuppression(owner=owner, source_id=source, field=scoped_field, epoch=epoch_row.epoch))
            if row is None:
                row = AgentMemoryItem(memory_id=identity, subject_user_id=owner, owner_user_id=owner,
                    course_id=target_course, memory_type='preference', fact_kind='explicit_user_preference', content=value,
                    structured_payload={}, confidence=1., importance=.8, visibility='private', status='active', source_type='learning_explicit',
                    source_id=source_id or 'preference-form:' + operation_id, source_span=quote or value, profile_axis=FIELDS[field],
                    evidence_count=1, fingerprint=digest(['learning',owner,target_course,field]), extractor='user', extractor_version='learning-v1',
                    valid_from=now, created_at=now, updated_at=now)
                db.add(row)
            row.structured_payload = {'learning_field': field, 'revision': revision + 1, 'explicit': True,
                'learning_sources': [source_id] if source_id else [], 'memory_epoch': epoch_row.epoch}
            row.status, row.updated_at = ('invalidated' if value is None else 'active'), now
            if value is not None:
                row.content, row.source_id, row.source_span = value.strip(), source_id or 'preference-form:' + operation_id, quote or value
            profiles = list(db.scalars(select(UserProfileFact).where(UserProfileFact.subject_user_id == owner,
                UserProfileFact.course_scope_key == (target_course or ''), UserProfileFact.profile_axis == FIELDS[field])))
            for profile in profiles:
                profile.status = 'invalidated'
            if value is not None:
                profile = next((p for p in profiles if p.profile_fact_id == 'profile-' + identity[13:]), None)
                if not profile:
                    profile = UserProfileFact(profile_fact_id='profile-' + identity[13:], subject_user_id=owner, course_id=target_course,
                        course_scope_key=target_course or '', profile_axis=FIELDS[field], value=value, evidence_count=1,
                        source_memory_ids=[identity], confidence=1., visibility='private', status='active',
                        last_seen_at=now, created_at=now, updated_at=now)
                    db.add(profile)
                profile.value, profile.status, profile.last_seen_at, profile.last_confirmed_at = value, 'active', now, now
            for summary in db.scalars(select(LearningContextSummary).where(LearningContextSummary.owner == owner)):
                summary.status = 'invalidated'
            if preparation_epoch is not None:
                changed(db, preparation_epoch, [identity, *[p.memory_id for p in previous]])
            result = {'field': field, 'scope': scope, 'revision': revision + 1, 'memory_epoch': epoch_row.epoch, 'changed': True}
            db.add(LearningEnrichmentReceipt(owner=owner, operation_id=operation_id, payload_hash=fingerprint, result=result))
            db.add(LearningMemoryOutbox(owner=owner, operation_id=operation_id, payload={**result, 'course_id': target_course, 'memory_id': identity}))
            db.add(AgentMemoryAuditEvent(audit_id='audit-' + uuid4().hex, subject_user_id=owner, event_type='learning.preference.changed',
                provider='user', decision=row.status, reason='explicit_request', payload={**result, 'memory_id': identity}, latency_ms=0, created_at=now))
            return result

    def apply_explicit_request(self, turn, args, operation_id, expected_epoch=None):
        question, quote = turn['request']['question'], args['source_quote']
        if not quote or quote not in question or re.search(r'这次|本次|暂时|(不要|不用|不必|无需|不需要).{0,4}(记住|保存|设置)|如果|假设|解释.{0,8}(这句|这段)|[“”「」]', question):
            raise HTTPException(422, '未找到当前原话中的长期设置授权')
        deleting = args['operation'] == 'delete'
        intent = r'删除|忘记|清除|取消.*偏好' if deleting else r'以后|今后|一直|长期|记住|默认|更新.*偏好|修改.*偏好'
        if not re.search(intent, quote):
            raise HTTPException(422, '一次性教学要求不自动保存为偏好')
        global_intent = bool(re.search(r'所有课程|全局|以后都|今后都|一直都', quote))
        if args['scope'] == 'global' and not global_intent:
            raise HTTPException(422, '未明确授权全局作用域，请使用当前课程')
        value = args.get('value')
        if not deleting and (not value or value not in quote):
            raise HTTPException(422, '偏好值必须来自当前原话')
        # Tool operation IDs are derived from the immutable source turn + full
        # validated arguments. A replay must use its saved receipt, not resolve
        # an omitted expected_revision again after the original write committed.
        with Session(self.engine) as db:
            receipt = db.get(LearningEnrichmentReceipt, (turn['owner'], operation_id))
            if receipt:
                return receipt.result
        current = next((i for i in self.manage(turn['owner'], turn['course_id'])['items'] if i['field'] == args['field'] and i['scope'] == args['scope']), None)
        revision = args.get('expected_revision')
        revision = (current['revision'] if current else 0) if revision is None else revision
        if deleting:
            return self.delete(turn['owner'], turn['course_id'], args['field'], args['scope'], revision,
                operation_id=operation_id, expected_epoch=expected_epoch)
        return self.update(turn['owner'], turn['course_id'], args['field'], args['scope'], value, revision,
            operation_id=operation_id, source_id=turn['turn_id'] + ':user', source_quote=quote, explicit=True, expected_epoch=expected_epoch)
