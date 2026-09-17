"""Durable answer queue with fenced leases and append-only conversation messages."""
import time
from uuid import uuid4
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from .db_models import LearningAnswerRun, LearningAgentToolCall
from .postgres_repository import SessionRepository
from .progress_repository import digest
from .repository import SessionConflict, SessionMissing


class LostLease(Exception):
    pass


class TurnRepository(SessionRepository):
    def __init__(self, engine, clock=time.time):
        super().__init__(engine)
        self.clock = clock

    @staticmethod
    def view(row):
        return {k: getattr(row, k) for k in ('turn_id', 'session_id', 'request_id', 'owner', 'course_id', 'topic_id',
            'request', 'status', 'stage', 'token', 'lease_until', 'deadline', 'attempt', 'checkpoint', 'result', 'error_code')}

    def accept(self, owner, sid, request):
        body = request.model_dump(mode='json')
        with self._write('learning-answer-queue') as db:
            session = self._owned(db, owner, sid)
            old = db.scalar(select(LearningAnswerRun).where(LearningAnswerRun.session_id == sid, LearningAnswerRun.request_id == body['request_id']))
            if old:
                if old.payload_hash != digest(body):
                    raise SessionConflict('请求标识已用于其他问题或阅读上下文')
                return self.view(old)
            active = db.scalar(select(LearningAnswerRun).where(LearningAnswerRun.session_id == sid,
                LearningAnswerRun.status.in_(['accepted', 'running'])))
            if active:
                raise SessionConflict('当前知识点仍有答疑执行中，可以继续阅读或取消该轮次')
            tid = 'answer-' + uuid4().hex
            row = LearningAnswerRun(turn_id=tid, session_id=sid, request_id=body['request_id'], owner=owner,
                course_id=session.course_id, topic_id=session.topic_id, payload_hash=digest(body), request=body,
                status='accepted', stage='accepted', token='', lease_until=0, deadline=0, created_at=self.clock(), attempt=0, checkpoint={})
            db.add(row)
            # Lock the same session row as other appenders, even during mixed-worker drain.
            db.refresh(session, with_for_update=True)
            self._append(db, session, tid + ':user', 'user', body['question'], 'user_content',
                         {'request_id': body['request_id'], 'resource_id': body['reading_context']['resource_ref']['material_id'], 'reading_context': body['reading_context']})
            db.flush()
            return self.view(row)

    def get(self, owner, tid):
        with Session(self.engine) as db:
            row = db.get(LearningAnswerRun, tid)
            if row is None or row.owner != owner:
                raise SessionMissing()
            return self.view(row)

    def list_topic(self, owner, sid):
        with Session(self.engine) as db:
            self._owned(db, owner, sid)
            return [self.view(r) for r in db.scalars(select(LearningAnswerRun).where(
                LearningAnswerRun.session_id == sid).order_by(LearningAnswerRun.created_at.desc()).limit(20))]

    def claim(self):
        with self._write('learning-answer-queue') as db:
            row = db.scalar(select(LearningAnswerRun).where(or_(LearningAnswerRun.status == 'accepted',
                (LearningAnswerRun.status == 'running') & (LearningAnswerRun.lease_until <= self.clock())))
                .order_by(LearningAnswerRun.created_at).limit(1))
            if row is None:
                return None
            if row.deadline and row.deadline <= self.clock():
                row.status, row.stage, row.error_code = 'failed', 'failed', 'DEADLINE_EXCEEDED'
                return None
            row.status, row.stage, row.token = 'running', 'reading_context', uuid4().hex
            row.attempt += 1
            row.lease_until = self.clock() + 15
            row.deadline = row.deadline or self.clock() + 90
            return self.view(row)

    def _fenced(self, db, claim):
        row = db.get(LearningAnswerRun, claim['turn_id'])
        if not row or row.status != 'running' or row.token != claim['token'] or row.lease_until <= self.clock() or row.deadline <= self.clock():
            raise LostLease()
        return row

    def heartbeat(self, claim):
        with self._write('learning-answer-queue') as db:
            row = self._fenced(db, claim)
            row.lease_until = min(row.deadline, self.clock() + 15)

    def save(self, claim, checkpoint, stage='organizing_answer', call=None):
        with self._write('learning-answer-queue') as db:
            row = self._fenced(db, claim)
            row.checkpoint, row.stage = checkpoint, stage
            if call:
                key = (row.turn_id, call['operation_id'])
                entry = db.get(LearningAgentToolCall, key)
                if entry:
                    entry.payload = call
                else:
                    db.add(LearningAgentToolCall(turn_id=row.turn_id, operation_id=call['operation_id'], payload=call))

    def finish(self, claim, result=None, error=None):
        with self._write('learning-answer-queue') as db:
            if result and result.get('memory_context'):
                from app.chat.memory.lifecycle import lock_epoch, MemoryChanged
                if lock_epoch(db, claim['owner']).epoch != result['memory_context']['memory_epoch']:
                    raise MemoryChanged('MEMORY_CHANGED_BEFORE_ANSWER_COMMIT')
            row = self._fenced(db, claim)
            row.result, row.error_code = result, error
            row.status = row.stage = 'failed' if error else 'succeeded'
            if result:
                session = self._owned(db, row.owner, row.session_id)
                db.refresh(session, with_for_update=True)
                self._append(db, session, row.turn_id + ':assistant', 'assistant', result['answer_markdown'], 'assistant_content',
                    {'request_id': row.request_id, 'resource_id': row.request['reading_context']['resource_ref']['material_id'], 'answer_result': result})

    def control(self, owner, tid, operation):
        with self._write('learning-answer-queue') as db:
            row = db.get(LearningAnswerRun, tid)
            if row is None or row.owner != owner:
                raise SessionMissing()
            if operation == 'cancel' and row.status in {'accepted', 'running'}:
                row.status = row.stage = 'canceled'
            elif operation == 'retry' and row.status in {'failed', 'canceled'}:
                if db.scalar(select(LearningAnswerRun).where(LearningAnswerRun.session_id == row.session_id,
                    LearningAnswerRun.status.in_(['accepted', 'running']))):
                    raise SessionConflict('当前知识点已有执行中的轮次')
                row.status = row.stage = 'accepted'
                row.error_code, row.deadline, row.checkpoint = None, 0, {}
            return self.view(row)
