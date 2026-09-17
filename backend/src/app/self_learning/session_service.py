"""Authenticated session entry, one-time legacy import, and history reads."""
from functools import lru_cache
import hashlib
import json
import os

from fastapi import HTTPException
from sqlalchemy import create_engine

from .postgres_repository import SessionRepository, SessionConflict, SessionMissing


@lru_cache(maxsize=4)
def _repository(database_url):
    if not database_url or not database_url.startswith(('postgresql:', 'postgresql+')):
        raise RuntimeError('Learning sessions require configured PostgreSQL')
    return SessionRepository(create_engine(database_url, pool_pre_ping=True))


def configured_repository():
    if os.getenv('LEARNING_SESSION_V1_ENABLED', '').lower() not in {'1', 'true'}:
        return None
    return _repository(os.getenv('DATABASE_URL', '').strip())


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
        room, chapter = self._chapter(owner, course_id, topic_id)
        if self.repository.find(owner, course_id, topic_id) is None:
            digest = hashlib.sha256(topic_id.encode()).hexdigest()[:24]
            path = self.learning.manager.get_classroom_qa_dir(course_id, 'learning_' + digest, owner) / 'session.json'
            # Read the original file, never load_or_empty's truncated projection.
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
            ready = next((r for r in chapter['resources'] if r.get('ready')), None)
            introduction = f'这一节围绕「{chapter["title"]}」学习。'
            introduction += (f'可以先阅读「{ready["title"]}」。' if ready else '资料尚未就绪时，可以先查看课程目录。')
            introduction += '遇到不清楚的地方随时提问，也可以直接开始阅读。'
            try:
                self.repository.ensure_session(owner, course_id, topic_id, introduction, legacy.get('turns', []),
                                               legacy_session_id=legacy.get('session_id'))
            except (KeyError, ValueError, SessionConflict) as exc:
                raise HTTPException(409, '旧会话记录需要核对，原始记录已保留') from exc
        result = self.messages(owner, course_id, topic_id)
        selected = next((r for r in chapter['resources'] if r['id'] == room['selectedId']), chapter['resources'][0])
        result['resume'] = {'resource_id': selected['id'], 'progress': room['progress'].get(selected['id'], {})}
        return result

    def messages(self, owner, course_id, topic_id, before=None, limit=50):
        self._chapter(owner, course_id, topic_id)
        current = self.repository.find(owner, course_id, topic_id)
        if current is None:
            raise HTTPException(404, '知识点会话尚未建立')
        try:
            return self.repository.messages(owner, current['session_id'], before, limit)
        except SessionMissing as exc:
            raise HTTPException(404, '会话不存在或无权访问') from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
