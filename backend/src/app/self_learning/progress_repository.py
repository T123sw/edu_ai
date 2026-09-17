"""Atomic facts, replay receipts and outbox. Serialized per owner across workers."""
import hashlib
import json
from sqlalchemy import select
from .postgres_repository import SessionRepository
from .db_models import (LearningFactRevision, LearningEventRecord, LearningResourceState,
                        LearningReadingStream, LearningTopicState, LearningProgressOutbox)

TABLES = ('self_learning_fact_revisions', 'self_learning_events', 'self_learning_resource_states',
          'self_learning_reading_streams', 'self_learning_topic_states', 'learning_progress_outbox')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class ProgressConflict(Exception):
    def __init__(self, message, current=None):
        self.detail = {'message': message, 'current': current}


class ProgressRepository(SessionRepository):
    def _snapshot(self, db, owner, course_id):
        revision = db.get(LearningFactRevision, (owner, course_id))
        resources = db.scalars(select(LearningResourceState).where(
            LearningResourceState.owner == owner, LearningResourceState.course_id == course_id)).all()
        topics = db.scalars(select(LearningTopicState).where(
            LearningTopicState.owner == owner, LearningTopicState.course_id == course_id)).all()
        return {**({'check_evidence': self.evidence_reader(db, owner, course_id)} if getattr(self, 'evidence_reader', None) else {}),
                'facts_revision': revision.revision if revision else 0,
                'resources': [{'resource_ref': r.resource_ref, **r.state} for r in resources],
                'resource_revisions': [{'resource_ref': r.resource_ref, 'revision': r.revision} for r in resources],
                'self_assessments': {t.topic_id: t.value for t in topics},
                'self_assessment_revisions': {t.topic_id: t.revision for t in topics}}

    def read(self, owner, course_id):
        with self._write('learning-facts:' + owner) as db:
            return self._snapshot(db, owner, course_id)

    def record(self, owner, course_id, topic_id, event, project=lambda value: value):
        body = event.model_dump(mode='json')
        fingerprint = digest([course_id, topic_id, body])
        eid = str(event.event_id)
        with self._write('learning-facts:' + owner) as db:
            old = db.get(LearningEventRecord, (owner, eid))
            if old:
                if old.payload_hash != fingerprint:
                    raise ProgressConflict('事件标识已用于其他内容')
                return old.receipt
            revision = db.get(LearningFactRevision, (owner, course_id))
            if revision is None:
                revision = LearningFactRevision(owner=owner, course_id=course_id, revision=0)
                db.add(revision)
            applied, reason, object_revision = True, None, None
            payload = body['payload']
            if event.type == 'self_assessment_set':
                state = db.get(LearningTopicState, (owner, course_id, topic_id))
                current = state.revision if state else 0
                if current != event.expected_revision:
                    raise ProgressConflict('自评已在其他页面更新，请刷新后重新选择',
                                           {'revision': current, 'value': state.value if state else 'unset'})
                if state is None:
                    state = LearningTopicState(owner=owner, course_id=course_id, topic_id=topic_id, revision=0)
                    db.add(state)
                state.value, state.revision = payload['value'], current + 1
                object_revision = state.revision
            else:
                ref = body['resource_ref']
                key = digest(ref)
                state = db.get(LearningResourceState, (owner, course_id, key))
                if state is None:
                    state = LearningResourceState(owner=owner, course_id=course_id, resource_key=key,
                        resource_ref=ref, state={'opened': False, 'reached_end': False, 'completed': False, 'locator': None}, revision=0)
                    db.add(state)
                value = dict(state.state)
                if event.type == 'resource_completion_set':
                    if state.revision != event.expected_revision:
                        raise ProgressConflict('完成记录已在其他页面更新，请刷新后重新操作',
                                               {'revision': state.revision, **value})
                    value['completed'] = payload['completed']
                    state.revision += 1
                elif event.type == 'resource_opened':
                    value['opened'] = True
                elif event.type == 'resource_end_reached':
                    value['reached_end'] = True
                else:
                    stream_key = (owner, course_id, key, str(payload['stream_id']))
                    stream = db.get(LearningReadingStream, stream_key)
                    if stream and stream.sequence >= payload['sequence']:
                        applied, reason = False, 'stale_position'
                    else:
                        if stream is None:
                            stream = LearningReadingStream(owner=owner, course_id=course_id,
                                resource_key=key, stream_id=str(payload['stream_id']))
                            db.add(stream)
                        stream.sequence, stream.locator = payload['sequence'], payload['locator']
                        value['locator'] = payload['locator']
                        value['opened'] = True
                state.state = value
                object_revision = state.revision
            if applied:
                revision.revision += 1
            db.flush()
            receipt = {'event_id': eid, 'applied': applied, 'reason': reason, 'object_revision': object_revision,
                       'facts_revision': revision.revision, 'projection_delta': project(self._snapshot(db, owner, course_id))}
            db.add(LearningEventRecord(owner=owner, event_id=eid, course_id=course_id, topic_id=topic_id,
                                      payload_hash=fingerprint, event=body, receipt=receipt))
            if applied:
                db.add(LearningProgressOutbox(owner=owner, event_id=eid,
                    payload={'course_id': course_id, 'topic_id': topic_id, 'facts_revision': revision.revision, 'type': event.type}))
            return receipt
