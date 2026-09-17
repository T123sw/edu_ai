"""Authenticated endpoints for the new learning UI. No preview data is accepted."""
from __future__ import annotations
import json
import re
import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4
import anyio
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth import get_current_user
from app.self_learning.service import LearningService, gateway, graph_leaves
from app.self_learning.store import lock
from app.services.classroom_service import submit_classroom_generation_job
from app.services.material_publication_service import MaterialPublicationService
from app.services.job_store import list_job_page

router = APIRouter(prefix='/api/self-learning', tags=['self-learning'])

def service():
    return LearningService()

from app.self_learning.contracts import Actor
from app.self_learning.progress_contracts import LearningEvent

class CreateLearning(BaseModel):
    goal: str = Field(min_length=2, max_length=1000)
    request_id: UUID

class Evidence(BaseModel):
    position: float = Field(default=0, ge=0, le=10000000)
    completed: bool = False
    note: str = Field(default='', max_length=10000)
    answer: int | None = Field(default=None, ge=0, le=1000)

class LearningPatch(BaseModel):
    selectedId: str | None = Field(default=None, max_length=200)
    progress: dict[str, Evidence] = Field(default_factory=dict, max_length=1000)
    understanding: dict[str, Literal['review', 'understood'] | None] = Field(default_factory=dict, max_length=1000)

class Turn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    request_id: UUID
    resource_id: str = Field(min_length=1, max_length=200)

class Attach(BaseModel):
    chapter_id: str = Field(min_length=1, max_length=200)
    material_type: Literal['report', 'quiz', 'classroom', 'lesson_plan', 'blog', 'flashcard', 'graph', 'game']
    material_id: str = Field(min_length=1, max_length=200)

@router.get('/state')
def state(user=Depends(get_current_user), svc=Depends(service)):
    value = svc.overview(user['username'])
    jobs = list_job_page(owner_user_id=user['username'], limit=100)
    from app.api.jobs import _public_job
    value['serverJobs'] = [{k: v for k, v in _public_job(j).items() if k in {'edu_job_id', 'kind', 'status', 'progress', 'message', 'course_id', 'scope_id', 'retryable', 'error_message', 'error_code', 'result_ref'}} for j in jobs.items]
    return value

@router.get('/courses/{course_id}')
def get_room(course_id: str, user=Depends(get_current_user), svc=Depends(service)):
    return svc.room(course_id, user['username'])

@router.post('/courses', status_code=202)
async def create(payload: CreateLearning, user=Depends(get_current_user), svc=Depends(service)):
    owner = user['username']
    course_id = 'learn-' + payload.request_id.hex
    info = svc.manager.get_course_info(course_id)
    if info:
        svc.require(course_id, owner)
        if info.get('created_by') != owner or info.get('description') != payload.goal:
            raise HTTPException(409, '请求标识已用于其他课堂')
    else:
        try:
            raw = await anyio.to_thread.run_sync(lambda: svc.model_factory(owner).chat([
                {'role': 'system', 'content': '你是学习路径规划助手。根据用户目标规划2至4个循序渐进的知识点。只返回JSON：{"title":"课程名","topics":["知识点1","知识点2"]}。不要输出正文。'},
                {'role': 'user', 'content': payload.goal}], max_tokens=700))
            raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip())
            plan = json.loads(raw)
            topics = [t.strip()[:120] for t in plan['topics'] if isinstance(t, str) and t.strip()][:4]
            if not topics or not isinstance(plan.get('title'), str):
                raise ValueError('invalid plan')
        except Exception as exc:
            logging.getLogger(__name__).warning('Learning plan failed: %s', type(exc).__name__)
            raise HTTPException(502, '学习路径规划失败，请重试') from exc
        with lock:
            if not svc.manager.get_course_info(course_id):
                now = datetime.now(timezone.utc).isoformat()
                svc.manager.create_course_structure(course_id)
                if not svc.manager.save_course_info(course_id, {'id': course_id, 'title': plan['title'][:120], 'description': payload.goal,
                    'icon': 'BookOutlined', 'color': '#8c77c4', 'created_by': owner, 'created_at': now, 'updated_at': now, 'revision': 0, 'self_learning': True}):
                    raise HTTPException(500, '课堂保存失败')
                svc.memberships.upsert(course_id, owner, 'owner', added_by=owner)
                graph = {'root': {'id': course_id, 'label': plan['title'][:120], 'children': [
                    {'id': course_id + '-topic-' + str(i), 'label': topic, 'type': 'knowledge_point', 'children': []} for i, topic in enumerate(topics)]}}
                if not svc.manager.save_knowledge_graph(course_id, graph):
                    raise HTTPException(500, '学习路径保存失败')
    # Durable generation owns execution/recovery. Repeated requests reuse material identities.
    for leaf in graph_leaves(svc.manager.get_knowledge_graph(course_id)):
        await submit_classroom_generation_job(course_id=course_id, requirement=payload.goal + '\n本节仅讲解：' + leaf['title'], owner=owner,
            course_storage_manager=svc.manager, source_mode='none', topic=leaf['title'], scope_type='knowledge_point', scope_id=leaf['id'],
            scene_count=3, duration_minutes=5, enable_tts=True, include_visuals=False,
            material_id='lesson-' + leaf['id'], idempotency_key='initial-' + leaf['id'],
            material_metadata={'learning_course_resource': True})
    return svc.room(course_id, owner)

@router.patch('/courses/{course_id}/learning')
def patch(course_id: str, payload: LearningPatch, user=Depends(get_current_user), svc=Depends(service)):
    return svc.patch(course_id, user['username'], payload.model_dump(exclude_unset=True))

@router.post('/courses/{course_id}/topics/{chapter_id}/turns')
def turn(course_id: str, chapter_id: str, payload: Turn, user=Depends(get_current_user), svc=Depends(service)):
    if svc.turns:
        raise HTTPException(409, '请刷新页面，使用持久化答疑入口')
    if not payload.question.strip():
        raise HTTPException(422, '请输入问题')
    return svc.answer(course_id, user['username'], chapter_id, payload.question.strip(), str(payload.request_id), payload.resource_id)


@router.post('/courses/{course_id}/topics/{chapter_id}/enter')
def enter_topic(course_id: str, chapter_id: str, user=Depends(get_current_user), svc=Depends(service)):
    svc.require(course_id, user['username'])
    if not svc.sessions:
        raise HTTPException(503, '知识点持久化会话尚未启用')
    return svc.sessions.enter(user['username'], course_id, chapter_id)


@router.get('/courses/{course_id}/topics/{chapter_id}/session')
def topic_history(course_id: str, chapter_id: str, before: str | None = Query(default=None, max_length=1024),
                  limit: int = Query(default=50, ge=1, le=100), user=Depends(get_current_user), svc=Depends(service)):
    svc.require(course_id, user['username'])
    if not svc.sessions:
        raise HTTPException(503, '知识点持久化会话尚未启用')
    return svc.sessions.messages(user['username'], course_id, chapter_id, before, limit)

@router.post('/courses/{course_id}/attachments')
def attach(course_id: str, payload: Attach, user=Depends(get_current_user), svc=Depends(service)):
    return svc.attach(course_id, user['username'], payload.chapter_id, payload.material_type, payload.material_id)

@router.post('/courses/{course_id}/publish')
def publish(course_id: str, user=Depends(get_current_user), svc=Depends(service)):
    _, membership = svc.require(course_id, user['username'])
    if user['role'] not in {'teacher', 'admin'} or membership.role != 'owner':
        raise HTTPException(403, '仅课堂所有者教师可以共享课堂')
    if svc.prepared_courses and svc.prepared_courses.lookup(user['username'],course_id):
        from app.course_preparation.publication import PreparedPublication
        try: manifest=PreparedPublication(svc.prepared_courses.engine).publish(user['username'],course_id)
        except PermissionError as exc:raise HTTPException(403,'当前课程不可发布') from exc
        svc.store.put('__published__',course_id,{'published':True,'course_id':course_id})
        return {'published':True,'manifest_version':manifest['version']}
    owned = svc.manager.list_generated_materials(course_id, owner_user_id=user['username'], space='mine', aggregate=True)
    originals = [m for m in owned if m.get('learning_course_resource') and m.get('visibility') == 'private']
    shared = svc.manager.list_generated_materials(course_id, owner_user_id=user['username'], space='course', aggregate=True)
    if not originals and not shared:
        raise HTTPException(409, '请等待课堂内容生成完成后再共享')
    for material in originals:
        MaterialPublicationService(svc.manager).publish(course_id=course_id, material_type=material['material_type'], material_id=material['material_id'], owner_user_id=user['username'])
    svc.store.put('__published__', course_id, {'published': True, 'course_id': course_id})
    return {'published': True}

@router.post('/courses/{course_id}/join')
def join(course_id: str, user=Depends(get_current_user), svc=Depends(service)):
    if not svc.store.get('__published__', course_id).get('published') or not svc.manager.get_course_info(course_id):
        raise HTTPException(404, '共享课堂不存在')
    if svc.prepared_courses:
        from sqlalchemy.orm import Session
        from app.course_preparation.publication import PreparedPublication
        from app.database.models import CourseMembership
        with Session(svc.prepared_courses.engine) as db,db.begin():
            if PreparedPublication.current(db,course_id):
                actor=svc.prepared_courses.identity(db,user['username'])
                if db.get(CourseMembership,(course_id,actor.user_id)) is None:
                    db.add(CourseMembership(course_id=course_id,user_id=actor.user_id,role='viewer'))
                db.flush()
                # Resolve the room after membership commit, using the immutable identity.
                prepared=True
            else:prepared=False
        if prepared:return svc.room(course_id,user['username'])
    if not svc.memberships.get(course_id, user['username']):
        svc.memberships.upsert(course_id, user['username'], 'viewer', added_by=user['username'])
    svc.patch(course_id, user['username'], {})
    return svc.room(course_id, user['username'])

class Practice(BaseModel):
    version: int = Field(ge=1)
    answers: dict[str, str] = Field(max_length=200)

@router.get('/courses/{course_id}/practice/{material_id}')
def practice_state(course_id: str, material_id: str, user=Depends(get_current_user), svc=Depends(service)):
    material = svc.material(course_id, 'quiz', material_id, user['username'])
    return svc.store.get(user['username'], course_id).get('practice', {}).get(material_id, {}) if material else {}

@router.post('/courses/{course_id}/practice/{material_id}')
def practice(course_id: str, material_id: str, payload: Practice, user=Depends(get_current_user), svc=Depends(service)):
    return svc.practice(course_id, user['username'], material_id, payload.version, payload.answers)


@router.get('/courses/{course_id}/progress')
def learning_progress(course_id: str, user=Depends(get_current_user), svc=Depends(service)):
    svc.require(course_id, user['username'])
    if not svc.progress_service:
        raise HTTPException(503, '版本化学习记录尚未启用')
    return svc.progress_service.read(Actor(user_id=user['username']), course_id)


@router.post('/courses/{course_id}/topics/{chapter_id}/events')
def learning_event(course_id: str, chapter_id: str, payload: LearningEvent, user=Depends(get_current_user), svc=Depends(service)):
    svc.require(course_id, user['username'])
    if not svc.progress_service:
        raise HTTPException(503, '版本化学习记录尚未启用')
    return svc.progress_service.record(Actor(user_id=user['username']), course_id, chapter_id, payload)


from app.self_learning.turn_contracts import AnswerRequest
from app.self_learning.contracts import ResourceRef
from app.self_learning.resource_reader import exact_material


def turn_service(svc):
    if not svc.turns:
        raise HTTPException(503, '学习 Agent 答疑运行尚未启用')
    return svc.turns


@router.post('/courses/{course_id}/topics/{chapter_id}/agent-turns', status_code=202)
def accept_answer(course_id: str, chapter_id: str, payload: AnswerRequest, user=Depends(get_current_user), svc=Depends(service)):
    svc.require(course_id, user['username'])
    return turn_service(svc).accept(user['username'], course_id, chapter_id, payload)


@router.get('/courses/{course_id}/topics/{chapter_id}/agent-turns')
def list_answers(course_id: str, chapter_id: str, user=Depends(get_current_user), svc=Depends(service)):
    svc.require(course_id, user['username'])
    return turn_service(svc).list_topic(user['username'], course_id, chapter_id)


@router.get('/agent-turns/{turn_id}')
def get_answer(turn_id: str, user=Depends(get_current_user), svc=Depends(service)):
    return turn_service(svc).get(user['username'], turn_id)


@router.post('/agent-turns/{turn_id}/{operation}')
def control_answer(turn_id: str, operation: Literal['retry', 'cancel'], user=Depends(get_current_user), svc=Depends(service)):
    return turn_service(svc).control(user['username'], turn_id, operation)


@router.get('/courses/{course_id}/materials/{kind}/{material_id}/versions/{version}')
def version_material(course_id: str, kind: str, material_id: str, version: int, user=Depends(get_current_user), svc=Depends(service)):
    if version < 1:
        raise HTTPException(422, '无效版本')
    material=exact_material(svc, user['username'], ResourceRef(course_id=course_id, material_type=kind, material_id=material_id, version=version))
    from app.self_learning.rollout import enabled
    return {**material,'learning_checks_enabled':bool(svc.checks) and enabled(user['username'],course_id)}


class CheckOffer(BaseModel):
    resource_ref: ResourceRef
    question_id: str = Field(min_length=1,max_length=200)


class CheckAnswer(BaseModel):
    request_id: UUID
    answer: dict = Field(default_factory=dict)
    skip: bool = False


def checks(svc):
    if not svc.checks: raise HTTPException(503,'学习检查尚未启用')
    return svc.checks


@router.post('/courses/{course_id}/topics/{topic_id}/checks')
def offer_check(course_id: str,topic_id: str,payload: CheckOffer,user=Depends(get_current_user),svc=Depends(service)):
    return checks(svc).offer(user['username'],course_id,topic_id,payload.resource_ref.model_dump(),payload.question_id)


@router.post('/checks/{check_id}/attempts')
def submit_check(check_id: str,payload: CheckAnswer,user=Depends(get_current_user),svc=Depends(service)):
    return checks(svc).submit(user['username'],check_id,payload.request_id,payload.answer,skip=payload.skip)


@router.get('/checks/{check_id}/attempts')
def check_attempts(check_id: str,user=Depends(get_current_user),svc=Depends(service)):
    return {'attempts':checks(svc).attempts(user['username'],check_id)}


@router.get('/checks/{check_id}')
def get_check(check_id: str,user=Depends(get_current_user),svc=Depends(service)):
    return checks(svc).get(user['username'],check_id)


def notification_service(svc):
    if not svc.prepared_courses: raise HTTPException(503,'课程准备通知尚未启用')
    from app.self_learning.notifications import NotificationService
    return NotificationService(svc.prepared_courses.engine)


@router.get('/notifications')
def preparation_notifications(user=Depends(get_current_user),svc=Depends(service)):
    return {'items':notification_service(svc).list(user['username'])}


@router.post('/notifications/{event_id}/read')
def read_preparation_notification(event_id: str,user=Depends(get_current_user),svc=Depends(service)):
    try: notification_service(svc).mark_read(user['username'],event_id)
    except PermissionError as exc: raise HTTPException(404,'通知不可访问') from exc
    return {'read':True}


@router.post('/checks/{check_id}/attempts/{request_id}/evaluate')
async def evaluate_check(check_id: str,request_id: UUID,user=Depends(get_current_user),svc=Depends(service)):
    return await checks(svc).evaluate(user['username'],check_id,request_id)
