"""Authenticated course tools and a cross-course personal resource library."""
from __future__ import annotations

import hashlib
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from app.auth import get_current_user
from app.services.personal_studio import namespace, read, public_resource, course_context, learning_service
from app.services.personal_tool_access import require_personal_tool, PersonalToolAccessDenied
from app.services.generation_command import generation_job_kind
from app.services.job_store import JobKind, create_job, get_job, list_job_page
from app.services.platform_task_handlers import enqueue_platform_task
from app.services.runtime_config_resolver import runtime_config_resolver
from core.course_storage import CourseStorageManager
from app.services.generation_command import GenerationCommandService

router = APIRouter(prefix='/api/personal-studio', tags=['personal-studio'])
KINDS = Literal['report', 'quiz', 'flashcard', 'graph', 'lesson_plan', 'blog', 'podcast', 'scenario']
ACTIVE_KINDS = Literal['report', 'quiz', 'flashcard', 'graph', 'podcast', 'scenario']

class Generate(BaseModel):
    course_id: str = Field(min_length=1, max_length=200)
    chapter_id: str = Field(min_length=1, max_length=200)
    request_id: str = Field(min_length=1, max_length=100)
    resource_type: ACTIVE_KINDS = 'report'
    mode: Literal['generate', 'research'] = 'generate'
    title: str = Field(min_length=2, max_length=200, pattern=r'\S')
    config: dict = Field(default_factory=dict)

class Attach(BaseModel):
    course_id: str = Field(min_length=1, max_length=200)
    chapter_id: str = Field(min_length=1, max_length=200)


def manager():
    return CourseStorageManager()


@router.get('')
def listing(user=Depends(get_current_user), storage=Depends(manager)):
    owner = user['username']
    materials = storage.list_generated_materials(namespace(owner), owner_user_id=owner, space='mine', aggregate=True)
    page = list_job_page(owner_user_id=owner, limit=200)
    jobs = [j.model_dump(mode='json') for j in page.items if j.input_summary.get('source') == 'personal-studio']
    # List payload stays small; full content is read when the resource opens.
    keys = ('material_id', 'material_type', 'title', 'studio_title', 'studio_mode', 'updated_at', 'created_at', 'version', 'studio_course_id', 'studio_course_title', 'studio_chapter_id', 'studio_chapter_title', 'studio_library_saved')
    return {'resources': [{k: m.get(k) for k in keys} for m in materials if m.get('studio_complete')], 'jobs': jobs}


@router.post('/generate', status_code=202)
def generate(payload: Generate, user=Depends(get_current_user), learning=Depends(learning_service)):
    from app.chat.api import schemas_v2 as schemas
    from app.services.studio_learning_resources import PodcastConfig, ScenarioConfig
    owner = user['username']
    kind = 'report' if payload.mode == 'research' else payload.resource_type
    try:
        require_personal_tool(user.get('role', ''), 'mind_map' if kind == 'graph' else kind)
    except PersonalToolAccessDenied as exc:
        raise HTTPException(403, '当前账号无法使用此工具') from exc
    models = {'report': schemas.KnowledgeBaseDirectReportRequestV2, 'quiz': schemas.KnowledgeBaseDirectQuizRequestV2,
        'flashcard': schemas.KnowledgeBaseDirectFlashcardRequestV2, 'graph': schemas.KnowledgeBaseDirectGraphRequestV2,
        'podcast': PodcastConfig, 'scenario': ScenarioConfig}
    if len(json.dumps(payload.config, ensure_ascii=False)) > 16000:
        raise HTTPException(422, '配置过长')
    try:
        if kind in {'podcast', 'scenario'}:
            validated = models[kind].model_validate({**payload.config, 'topic': payload.title}).model_dump(mode='json')
        else:
            validated = models[kind].model_validate({**payload.config, **({'question': payload.title} if kind == 'report' else {}),
                'course_id': namespace(owner), 'scope_type': 'course', 'scope_id': None, 'source_mode': 'none',
                'selected_doc_ids': [], 'idempotency_key': payload.request_id}).model_dump(mode='json')
    except ValidationError as exc:
        raise HTTPException(422, '请检查工具配置中的主题、数量和选项') from exc
    config = {k: v for k, v in validated.items() if k not in {'course_id', 'scope_type', 'scope_id', 'source_mode', 'selected_doc_ids', 'idempotency_key'}}
    config.setdefault('title', payload.title)
    fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    job_id = 'studio_' + hashlib.sha256(f'{owner}:{payload.request_id}'.encode()).hexdigest()[:28]
    with GenerationCommandService._submission_lock:
        existing = get_job(job_id)
        if existing:
            if existing.owner_user_id != owner or existing.input_summary.get('fingerprint') != fingerprint:
                raise HTTPException(409, '此请求编号已用于其他内容')
            return existing.model_dump(mode='json')
        binding = course_context(owner, payload.course_id, payload.chapter_id, learning)
        config['research_context'] = binding['research_context']
        snapshot = runtime_config_resolver.capture_snapshot(owner)
        job_kind = {'podcast': JobKind.GENERATE_PODCAST, 'scenario': JobKind.GENERATE_SCENARIO}.get(kind) or generation_job_kind(kind)
        job = create_job(edu_job_id=job_id, kind=job_kind, owner_user_id=owner, course_id=payload.course_id,
            input_summary={**{k: v for k, v in binding.items() if k not in {'research_context', 'studio_source_refs'}}, 'title': payload.title, 'source': 'personal-studio', 'resource_type': kind, 'studio_mode': payload.mode, 'fingerprint': fingerprint})
        command = {'resource_type': kind, 'course_id': namespace(owner), 'scope_type': 'course', 'source_mode': 'none',
            'selected_doc_ids': [], 'material_id': job_id, 'config': config, 'studio_context': binding, 'studio_mode': payload.mode, 'title': payload.title}
        return enqueue_platform_task(job=job, workflow_type='personal_studio', command=command,
            runtime_config_snapshot=snapshot).model_dump(mode='json')


@router.get('/resources/{kind}/{material_id}')
def detail(kind: KINDS, material_id: str, user=Depends(get_current_user), storage=Depends(manager)):
    resource = read(user['username'], kind, material_id, storage)
    if not resource.get('studio_complete'):
        raise HTTPException(409, '资源仍在准备中')
    result = public_resource(resource)
    if kind == 'podcast':
        from urllib.parse import quote
        result['content'] = {**result['content'], 'audio_url': f"/api/personal-studio/resources/podcast/{quote(material_id, safe='')}/audio"}
    return result


@router.get('/resources/podcast/{material_id}/audio')
def podcast_audio(material_id: str, user=Depends(get_current_user), storage=Depends(manager)):
    from fastapi.responses import FileResponse
    from app.services.studio_learning_resources import podcast_directory
    resource = read(user['username'], 'podcast', material_id, storage)
    if not resource.get('studio_complete'):
        raise HTTPException(409, '播客仍在制作中')
    path = podcast_directory(storage, user['username'], material_id) / 'podcast.mp3'
    if not path.is_file():
        raise HTTPException(404, '播客音频暂时不可用')
    return FileResponse(path, media_type='audio/mpeg', headers={'Cache-Control': 'private, no-store'})


@router.post('/resources/{kind}/{material_id}/attach')
def attach(kind: KINDS, material_id: str, payload: Attach, user=Depends(get_current_user), storage=Depends(manager)):
    from app.self_learning.service import LearningService
    from app.self_learning.store import lock
    if kind not in {'report', 'quiz'}:
        raise HTTPException(422, '此类资源暂不支持加入课堂目录，可在我的资源中使用')
    owner = user['username']
    source = read(owner, kind, material_id, storage)
    if not source.get('studio_complete'):
        raise HTTPException(409, '资源仍在准备中')
    if source.get('studio_course_id') and source['studio_course_id'] != payload.course_id:
        raise HTTPException(422, '请加入资源所属课程')
    learning = LearningService().for_scope(owner, payload.course_id)
    room = learning.room(payload.course_id, owner)  # Enforces course membership.
    if payload.chapter_id not in {c['id'] for c in room['chapters']}:
        raise HTTPException(422, '请选择有效知识点')
    # Stable per-version copy makes repeated clicks safe, retaining the personal original.
    copy_id = 'studio-copy-' + hashlib.sha256(f'{namespace(owner)}:{kind}:{material_id}:{source["version"]}:{payload.chapter_id}'.encode()).hexdigest()[:24]
    with lock:
        if not storage.get_generated_material(payload.course_id, kind, copy_id, owner_user_id=owner):
            snapshot = {k: v for k, v in source.items() if k not in {'course_id', 'material_id', 'version', 'scope_type', 'scope_id', 'content_hash'}}
            if not storage.save_generated_material(payload.course_id, kind, copy_id, snapshot, owner_user_id=owner,
                    visibility='private', scope_type='knowledge_point', scope_id=payload.chapter_id):
                raise HTTPException(500, '保存课程副本失败')
        return learning.attach(payload.course_id, owner, payload.chapter_id, kind, copy_id)


class LibrarySelection(BaseModel):
    saved: bool


@router.put('/resources/{kind}/{material_id}/library')
def library_selection(kind: KINDS, material_id: str, payload: LibrarySelection, user=Depends(get_current_user), storage=Depends(manager)):
    owner = user['username']
    resource = read(owner, kind, material_id, storage)
    if resource.get('studio_mode') != 'research' or not resource.get('studio_complete'):
        raise HTTPException(409, '研究完成后可以收藏')
    if resource.get('studio_library_saved', True) != payload.saved:
        if not storage.save_generated_material(namespace(owner), kind, material_id,
                {'studio_library_saved': payload.saved}, owner_user_id=owner, visibility='private'):
            raise HTTPException(500, '暂时无法更新收藏')
    return public_resource(read(owner, kind, material_id, storage))


@router.get('/research/{job_id}')
def research_progress(job_id: str, user=Depends(get_current_user), storage=Depends(manager)):
    owner = user['username']
    job = get_job(job_id)
    if not job or job.owner_user_id != owner or job.input_summary.get('source') != 'personal-studio' or job.input_summary.get('studio_mode') != 'research':
        raise HTTPException(404, '研究记录不存在或无权访问')
    try:
        resource = read(owner, 'report', job_id, storage)
    except HTTPException as exc:
        if exc.status_code != 404: raise
        resource = None
    # Only expose sources while synthesis/publication is incomplete.
    value = public_resource(resource) if resource and resource.get('studio_complete') else None
    return {'job': job.model_dump(mode='json'), 'resource': value,
            'sources': (resource or {}).get('research_sources', [])}
