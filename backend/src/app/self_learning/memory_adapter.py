"""Explicit preferences share the existing memory store and lifecycle watermark."""
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import AgentMemoryItem
from app.chat.memory.lifecycle import MemoryLifecycle, MemoryChanged, revision, expired
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.chat.memory.domain import MemoryRecordDraft


class MemoryAdapter:
    def __init__(self, engine):
        self.engine = engine
        self.lifecycle = MemoryLifecycle(engine)
        self.repository = SqlAlchemyMemoryRepository(engine)

    def read(self, owner, course):
        return self.lifecycle.read_effective(owner, course_id=course)

    def validate(self, owner, context):
        if self.lifecycle.current_epoch(owner) != context['memory_epoch']:
            raise MemoryChanged('MEMORY_EPOCH_CHANGED')

    def permits_history(self, owner, message):
        # Raw history remains stored. Suppressed source spans and old derived
        # replies are excluded from new prompts, even if an index is stale.
        with Session(self.engine) as session:
            invalid = session.scalars(select(AgentMemoryItem).where(
                AgentMemoryItem.subject_user_id == owner)).all()
            invalid = [row for row in invalid if row.status != 'active' or expired(row)]
            if any(span and span in message.content for row in invalid for span in (row.source_span, row.content)):
                return False
        result = (message.raw_payload or {}).get('answer_result', {})
        memory = result.get('memory_context')
        if memory:
            try: self.validate(owner, memory)
            except MemoryChanged: return False
        return True

    def update_preference(self, owner, memory_id, value, expected_revision):
        value = value.strip()
        if not value or len(value) > 2000:
            raise ValueError('INVALID_PREFERENCE_VALUE')
        with Session(self.engine) as session:
            record = session.get(AgentMemoryItem, memory_id)
            if record is None or record.subject_user_id != owner or not record.profile_axis:
                raise PermissionError('PREFERENCE_UNAVAILABLE')
            course, axis = record.course_id, record.profile_axis
        return self.repository.upsert_memory(MemoryRecordDraft(
            expected_memory_id=memory_id, expected_revision=expected_revision,
            subject_user_id=owner, owner_user_id=owner, course_id=course, memory_type='preference',
            fact_kind='preference', content=value, confidence=1, profile_axis=axis, supersedes_axis=True,
            source_type='user_confirmation', source_id='learning-preference:'+uuid4().hex, source_span=value,
            structured_payload={'confirmed_by_user':True}, extractor='user_confirmation'))

    def delete_preference(self, owner, memory_id, expected_revision):
        return self.repository.invalidate(memory_id=memory_id, subject_user_id=owner,
            expected_revision=expected_revision, reason='user_requested')

    def confirm_from_turn(self,turn,axis,value,scope,source_quote,expected_epoch):
        from app.chat.memory.lifecycle import source_digest,MemorySuppressed
        question=turn['request']['question']
        if not source_quote or source_quote not in question or value not in source_quote:
            raise ValueError('PREFERENCE_SOURCE_NOT_CURRENT_USER_QUOTE')
        if not any(marker in question for marker in ('记住','长期','以后都','始终')):
            raise ValueError('PREFERENCE_PERSISTENCE_NOT_REQUESTED')
        scope_markers=('所有课程','全局','以后都') if scope=='global' else ('本课程','这门课','当前课程')
        if not any(marker in question for marker in scope_markers): raise ValueError('PREFERENCE_SCOPE_AMBIGUOUS')
        source='learning-turn:'+turn['turn_id']+':'+axis
        with Session(self.engine) as db:
            previous=db.scalar(select(AgentMemoryItem).where(AgentMemoryItem.subject_user_id==turn['owner'],AgentMemoryItem.source_id==source))
            if previous:
                if previous.status!='active' or previous.content!=value: raise MemoryChanged('PREFERENCE_SOURCE_CHANGED_OR_DELETED')
                return {'memory_id':previous.memory_id,'revision':revision(previous),'value':previous.content}
        record=self.repository.upsert_memory(MemoryRecordDraft(expected_epoch=expected_epoch,
            subject_user_id=turn['owner'],owner_user_id=turn['owner'],course_id=turn['course_id'] if scope=='current_course' else None,
            conversation_id=turn['session_id'],memory_type='preference',fact_kind='preference',content=value,confidence=1,
            profile_axis=axis,supersedes_axis=True,source_type='user_confirmation',source_id=source,source_span=source_quote,
            structured_payload={'confirmed_by_user':True,'source_message_id':turn['turn_id']+':user'},extractor='user_confirmation'))
        return {'memory_id':record.memory_id,'value':record.content,'memory_epoch':record.memory_epoch}
