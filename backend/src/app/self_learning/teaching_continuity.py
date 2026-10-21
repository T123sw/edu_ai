"""Source-bound teaching notes, isolated by owner/course/topic."""
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import ConversationMessage
from .db_models import LearningTopicSession, LearningAnswerRun
from .enrichment_models import LearningObservation


def teaching_notes(learning, owner, course, topic, *, limit=8, active_only=False):
    learning.sessions._chapter(owner, course, topic)
    memory = getattr(learning, 'memory', None)
    if not memory:
        return []
    with Session(memory.engine) as db:
        query = select(LearningObservation).where(LearningObservation.owner == owner,
            LearningObservation.course_id == course, LearningObservation.topic_id == topic)
        if active_only:
            query = query.where(LearningObservation.status == 'hypothesis')
        query = query.join(LearningAnswerRun, LearningAnswerRun.turn_id == LearningObservation.turn_id).where(
            LearningAnswerRun.owner == owner, LearningAnswerRun.course_id == course,
            LearningAnswerRun.topic_id == topic).order_by(func.coalesce(
                LearningObservation.payload['status_changed_at'].as_float(), LearningAnswerRun.created_at).desc()).limit(40)
        items = []
        for row in db.scalars(query):
            source_ids = row.payload.get('source_message_ids', [])
            if not source_ids or any(memory.suppressed(owner, sid, db) for sid in source_ids):
                continue
            sources = list(db.scalars(select(ConversationMessage).join(LearningTopicSession,
                LearningTopicSession.session_id == ConversationMessage.conversation_id).where(
                ConversationMessage.message_id.in_(source_ids), LearningTopicSession.owner == owner,
                LearningTopicSession.course_id == course,
                func.coalesce(ConversationMessage.raw_payload['topic_id'].as_string(), LearningTopicSession.topic_id) == topic,
                ConversationMessage.role == 'user')))
            if len(sources) != len(set(source_ids)):
                continue
            run = db.get(LearningAnswerRun, row.turn_id)
            snapshot = run.request.get('reading_context', {})
            items.append({'turn_id': row.turn_id, 'topic_id': topic, **row.payload, 'status': row.status,
                'created_at': run.created_at, 'resource_ref': snapshot.get('resource_ref'),
                'locator': snapshot.get('locator'),
                'sources': [{'message_id': m.message_id, 'quote': m.content[:600]} for m in sources]})
            if len(items) >= limit:
                break
        return items
