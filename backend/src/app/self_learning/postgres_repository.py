"""Transactional append-only learning sessions, with a SQLite contract-test dialect."""
from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import time
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import Conversation, ConversationMessage
from .db_models import LearningAgentTurn, LearningTopicSession
from .repository import SessionMissing, SessionConflict


def payload_hash(question, resource_id):
    return hashlib.sha256(json.dumps([question, resource_id], ensure_ascii=False).encode()).hexdigest()


class SessionRepository:
    def __init__(self, engine):
        self.engine = engine

    @contextmanager
    def _write(self, key):
        with Session(self.engine) as db:
            try:
                if self.engine.dialect.name == 'postgresql':
                    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], signed=True)
                    db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_id})
                elif self.engine.dialect.name == 'sqlite':
                    db.execute(text('BEGIN IMMEDIATE'))
                else:
                    raise RuntimeError('unsupported learning session database')
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    @staticmethod
    def identity(owner, course_id, topic_id):
        return 'learning-' + hashlib.sha256(json.dumps([owner, course_id, topic_id]).encode()).hexdigest()

    @staticmethod
    def _owned(db, owner, session_id):
        record = db.get(LearningTopicSession, session_id)
        if record is None or record.owner != owner:
            raise SessionMissing()
        return record

    @staticmethod
    def _view(record):
        return {'session_id': record.session_id, 'course_id': record.course_id,
                'topic_id': record.topic_id, 'message_count': record.next_position,
                'import_metadata': record.import_metadata}

    def find(self, owner, course_id, topic_id):
        with Session(self.engine) as db:
            record = db.get(LearningTopicSession, self.identity(owner, course_id, topic_id))
            return self._view(record) if record and record.owner == owner else None

    @staticmethod
    def _append(db, record, message_id, role, content, kind, payload=None, occurred_at=None):
        existing = db.get(ConversationMessage, message_id)
        if existing is not None:
            if existing.conversation_id != record.session_id or existing.content != content:
                raise SessionConflict('消息标识冲突')
            return
        db.add(ConversationMessage(message_id=message_id, conversation_id=record.session_id,
            position=record.next_position, role=role, content=content, message_kind=kind,
            occurred_at=occurred_at or datetime.now(timezone.utc), raw_payload=payload or {}))
        record.next_position += 1
        db.flush()

    def ensure_session(self, owner, course_id, topic_id, introduction, legacy=(), *, legacy_session_id=None):
        sid = self.identity(owner, course_id, topic_id)
        with self._write(sid) as db:
            record = db.get(LearningTopicSession, sid)
            if record is not None:
                return self._view(self._owned(db, owner, sid))
            if any(not isinstance(t, dict) or not isinstance(t.get('question'), str)
                   or not isinstance(t.get('answer_text'), str) for t in legacy):
                raise ValueError('invalid legacy turn')
            now = datetime.now(timezone.utc)
            db.add(Conversation(conversation_id=sid, owner=owner, title=topic_id,
                course_id=course_id, scope_type='knowledge_point', scope_id=topic_id,
                state={'learning_session': True}, raw_payload={}, created_at=now, updated_at=now))
            db.flush()
            record = LearningTopicSession(session_id=sid, owner=owner, course_id=course_id,
                topic_id=topic_id, next_position=0, import_metadata={'completed': True, 'turn_count': len(legacy), 'legacy_session_id': legacy_session_id,
                    'source_sha256': hashlib.sha256(json.dumps(legacy, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})
            db.add(record)
            db.flush()
            self._append(db, record, sid + ':intro', 'assistant', introduction, 'introduction')
            seen = set()
            for i, turn in enumerate(legacy):
                request_id = str(turn.get('client_turn_id') or turn.get('turn_id') or f'legacy-{i}')
                if request_id in seen:
                    raise SessionConflict('旧会话存在重复请求标识，请先核对')
                seen.add(request_id)
                question, answer = turn['question'], turn['answer_text']
                resource_id = str(turn.get('resource_id') or '')
                digest = hashlib.sha256(request_id.encode()).hexdigest()
                meta = {'resource_id': resource_id, 'source': 'legacy', 'legacy_turn_id': turn.get('turn_id'),
                        'legacy_created_at': turn.get('created_at'), 'request_id': request_id}
                self._append(db, record, sid + ':' + digest + ':user', 'user', question, 'user_content', meta)
                self._append(db, record, sid + ':' + digest + ':assistant', 'assistant', answer, 'assistant_content', meta)
                db.add(LearningAgentTurn(session_id=sid, request_id=request_id,
                    payload_hash=payload_hash(question, resource_id), status='succeeded', token='imported',
                    lease_until=0, attempt=1, question=question, resource_id=resource_id, answer=answer))
            db.flush()
            return self._view(record)

    def messages(self, owner, session_id, before=None, limit=50):
        if not 1 <= limit <= 100:
            raise ValueError('limit must be between 1 and 100')
        with Session(self.engine) as db:
            record = self._owned(db, owner, session_id)
            position = record.next_position
            if before:
                try:
                    data = json.loads(base64.urlsafe_b64decode(before.encode()))
                    if data['s'] != session_id or type(data['p']) is not int or data['p'] < 0:
                        raise ValueError()
                    position = min(position, data['p'])
                except Exception as exc:
                    raise ValueError('无效的会话分页游标') from exc
            rows = list(db.scalars(select(ConversationMessage).where(
                ConversationMessage.conversation_id == session_id, ConversationMessage.position < position
            ).order_by(ConversationMessage.position.desc()).limit(limit + 1)))
            more = len(rows) > limit
            rows = list(reversed(rows[:limit]))
            items = [dict(id=m.message_id, role=m.role, text=m.content, kind=m.message_kind,
                position=m.position, sessionId=session_id, chapterId=record.topic_id,
                resourceId=(m.raw_payload or {}).get('resource_id', ''), resourceTitle='',
                createdAt=m.occurred_at.isoformat(), answerResult=(m.raw_payload or {}).get('answer_result')) for m in rows]
            cursor = base64.urlsafe_b64encode(json.dumps({'s': session_id, 'p': rows[0].position}).encode()).decode() if more else None
            return {**self._view(record), 'items': items, 'next_cursor': cursor}

    def recent_turns(self, owner, session_id, limit=6):
        # Message order, not timestamp ties or request UUIDs, determines history order.
        with Session(self.engine) as db:
            self._owned(db, owner, session_id)
            rows = db.scalars(select(ConversationMessage).where(
                ConversationMessage.conversation_id == session_id,
                ConversationMessage.message_kind == 'assistant_content'
            ).order_by(ConversationMessage.position.desc()).limit(limit)).all()
            turns = [db.get(LearningAgentTurn, (session_id, m.raw_payload['request_id'])) for m in reversed(rows)]
            return [{'question': t.question, 'answer_text': t.answer} for t in turns if t and t.status == 'succeeded']

    def begin_turn(self, owner, session_id, request_id, question, resource_id, now=None):
        now = time.time() if now is None else now
        with self._write(session_id) as db:
            record = self._owned(db, owner, session_id)
            turn = db.get(LearningAgentTurn, (session_id, request_id))
            digest = payload_hash(question, resource_id)
            if turn:
                if turn.payload_hash != digest:
                    raise SessionConflict('请求标识已用于不同问题或资料')
                if turn.status == 'succeeded':
                    return {'status': 'succeeded', 'token': turn.token}
            active = db.scalars(select(LearningAgentTurn).where(
                LearningAgentTurn.session_id == session_id, LearningAgentTurn.status == 'running')).all()
            for running in active:
                if running.lease_until > now:
                    raise SessionConflict('这个知识点的上一条回复仍在生成')
                running.status, running.error = 'failed', 'LEASE_EXPIRED'
            if turn is None:
                turn = LearningAgentTurn(session_id=session_id, request_id=request_id, payload_hash=digest,
                    question=question, resource_id=resource_id, status='running', token='', lease_until=0, attempt=0)
                db.add(turn)
                self._append(db, record, session_id + ':' + hashlib.sha256(request_id.encode()).hexdigest() + ':user',
                    'user', question, 'user_content', {'resource_id': resource_id, 'request_id': request_id})
            turn.status, turn.token, turn.lease_until = 'running', uuid4().hex, now + 300
            turn.error = None
            turn.attempt += 1
            db.flush()
            return {'status': turn.status, 'token': turn.token, 'attempt': turn.attempt}

    def finish_turn(self, owner, session_id, request_id, token, *, answer=None, error=None, now=None):
        now = time.time() if now is None else now
        with self._write(session_id) as db:
            record = self._owned(db, owner, session_id)
            turn = db.get(LearningAgentTurn, (session_id, request_id))
            if turn is None or turn.status != 'running' or turn.token != token or turn.lease_until <= now:
                return False
            if error:
                turn.status, turn.error = 'failed', error
            else:
                if not answer or not answer.strip():
                    raise ValueError('empty answer')
                self._append(db, record, session_id + ':' + hashlib.sha256(request_id.encode()).hexdigest() + ':assistant',
                    'assistant', answer, 'assistant_content', {'resource_id': turn.resource_id, 'request_id': request_id})
                turn.status, turn.answer = 'succeeded', answer
            return True
