"""Authenticated session entry, one-time legacy import, and history reads."""
from functools import lru_cache
import hashlib
import json
import os

from fastapi import HTTPException
from sqlalchemy import create_engine

from .postgres_repository import SessionRepository, SessionConflict, SessionMissing
from .learning_orientation import learning_orientation


@lru_cache(maxsize=4)
def _repository(database_url):
    if not database_url or not database_url.startswith(('postgresql:', 'postgresql+')):
        raise RuntimeError('Learning sessions require configured PostgreSQL')
    return SessionRepository(create_engine(database_url, pool_pre_ping=True))


def configured_repository():
    from .rollout import scoped_enabled
    if os.getenv('LEARNING_SESSION_V1_ENABLED', '').lower() not in {'1', 'true'} and not scoped_enabled():
        return None
    repository = _repository(os.getenv('DATABASE_URL', '').strip())
    if scoped_enabled():
        from sqlalchemy import inspect
        if not inspect(repository.engine).has_table('learning_rollout_scopes'):
            raise RuntimeError('Apply migration 20260917_0029 before scoped rollout')
    return repository


class SessionService:
    def __init__(self, learning_service, repository):
        self.learning = learning_service
        self.repository = repository

    def _chapter(self, owner, course_id, topic_id):
        room = self.learning.room(course_id, owner)
        chapter = next((c for c in room['chapters'] if c['id'] == topic_id), None)
        if chapter is None:
            raise HTTPException(404, '知识点不存在或无权访问')
        return room, chapter

    def enter(self, owner, course_id, topic_id):
        from .rollout import scoped_enabled, phase
        if scoped_enabled() and phase(self.learning, owner, course_id) < 1:
            raise HTTPException(503, '当前课程尚未启用持久化学习会话')
        room, chapter = self._chapter(owner, course_id, topic_id)
        if self.repository.find_course(owner, course_id) is None:
            # Import existing file histories before consolidating the course. Files remain unchanged.
            for node in room['chapters']:
                self._import_legacy(owner, course_id, node['id'])
            introduction = f'当前课程是「{room["title"]}」。整门课程共用这段对话，切换知识点后可以接着提问。'
            try:
                self.repository.ensure_course_session(owner, course_id, introduction)
            except SessionConflict as exc:
                raise HTTPException(409, str(exc)) from exc
        result = self.messages(owner, course_id, topic_id)
        selected = next((r for r in chapter['resources'] if r['id'] == room['selectedId']), chapter['resources'][0])
        result['resume'] = {'resource_id': selected['id'], 'progress': room['progress'].get(selected['id'], {})}
        result['learning_context'] = learning_orientation(room, topic_id)
        return result

    def _import_legacy(self, owner, course_id, topic_id):
        if self.repository.find(owner, course_id, topic_id) is not None:
            return
        digest = hashlib.sha256(topic_id.encode()).hexdigest()[:24]
        path = self.learning.manager.get_classroom_qa_dir(course_id, 'learning_' + digest, owner) / 'session.json'
        try:
            legacy = json.loads(path.read_text()) if path.exists() else {}
            if not isinstance(legacy, dict) or not isinstance(legacy.get('turns', []), list):
                raise ValueError('invalid legacy session')
            expected = {'course_id': course_id, 'owner_user_id': owner, 'classroom_id': 'learning_' + digest}
            if any(key in legacy and legacy[key] != value for key, value in expected.items()):
                raise ValueError('legacy session scope mismatch')
        except (ValueError, OSError) as exc:
            raise HTTPException(409, '旧会话无法读取，原始记录已保留，请先核对') from exc
        if legacy.get('active_turn'):
            raise HTTPException(409, '旧会话仍有未结束的提问，请先完成恢复再切换')
        if legacy.get('turns'):
            try:
                self.repository.ensure_session(owner, course_id, topic_id, '', legacy['turns'],
                                               legacy_session_id=legacy.get('session_id'))
            except (KeyError, ValueError, SessionConflict) as exc:
                raise HTTPException(409, '旧会话记录需要核对，原始记录已保留') from exc

    def messages(self, owner, course_id, topic_id, before=None, limit=50):
        self._chapter(owner, course_id, topic_id)
        current = self.repository.find_course(owner, course_id)
        if current is None:
            raise HTTPException(404, '课程会话尚未建立')
        try:
            return self.repository.messages(owner, current['session_id'], before, limit)
        except SessionMissing as exc:
            raise HTTPException(404, '会话不存在或无权访问') from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
