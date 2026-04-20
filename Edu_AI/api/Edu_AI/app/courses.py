"""Course management and persisted course-material APIs."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.knowledge_graph_hours import (
    KnowledgeGraphHourAllocationError,
    allocate_graph_hours_from_llm,
)
from app.teaching_video_bridge import get_teaching_video_bridge_service
from app.ai_lecture_sessions import (
    AiLectureRecordingRequest,
    CreateAiLectureSessionRequest,
    PatchAiLectureSessionSnapshotRequest,
    get_ai_lecture_session_service,
)
from core import Config
from core.auth import auth_manager
from core.course_storage import (
    LIBRARY_TYPE_COURSE,
    LIBRARY_TYPE_PERSONAL,
    CourseStorageManager,
    storage_manager,
)
from rag_v2.api import get_rag_system
from rag_v2.document_resolver import resolve_rag_document
from app.workspace_scope import SCOPE_TYPE_COURSE, collect_scope_ids_for_query


security = HTTPBearer()
router = APIRouter(prefix="/api/courses", tags=["courses"])
_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "GIT_HTTP_PROXY",
    "GIT_HTTPS_PROXY",
)


class CourseInfo(BaseModel):
    id: str = Field(..., description="课程 ID")
    title: str = Field(..., description="课程名称")
    description: str = Field(..., description="课程描述")
    icon: str = Field(..., description="前端图标名")
    color: str = Field(..., description="主题色")
    objectives: Optional[List[str]] = Field(default=None, description="教学目标")
    knowledgeGraph: Optional[str] = Field(default=None, description="知识图谱")


class KnowledgeBaseDocument(BaseModel):
    id: str
    name: str
    type: str
    file_path: Optional[str] = None
    url: Optional[str] = None
    course_id: str
    scope_type: str = SCOPE_TYPE_COURSE
    scope_id: Optional[str] = None
    library_type: str = LIBRARY_TYPE_COURSE
    owner_user_id: Optional[str] = None
    promoted_from_document_id: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class AddRAGDocumentRequest(BaseModel):
    rag_file_path: str = Field(..., description="RAG document identifier")
    scope_type: str = Field(default=SCOPE_TYPE_COURSE, description="workspace scope type")
    scope_id: Optional[str] = Field(default=None, description="workspace scope identifier")
    library_type: str = Field(default=LIBRARY_TYPE_COURSE, description="target library type")
    promoted_from_document_id: Optional[str] = Field(default=None, description="source personal document id when promoting into course knowledge base")


class PinMaterialRequest(BaseModel):
    is_pinned: bool = Field(..., description="是否置顶")


class KnowledgeGraphData(BaseModel):
    root: dict = Field(..., description="知识图谱根节点")


class KnowledgeGraphHourAllocationRequest(BaseModel):
    total_hours: float = Field(..., description="Course total hours, with at most one decimal place")


class KnowledgeGraphHourAllocationResponse(KnowledgeGraphData):
    allocation: Dict[str, Any] = Field(default_factory=dict, description="Hour allocation metadata")


class TeachingVideoPptItem(BaseModel):
    material_id: str
    title: str
    pptx_url: str
    html_full_url: Optional[str] = None
    slide_count: Optional[int] = None
    updated_at: Optional[str] = None


class CreateTeachingVideoTaskRequest(BaseModel):
    ppt_material_id: str = Field(..., description="璇剧▼ PPT 璧勬簮 ID")


class TeachingVideoTaskResponse(BaseModel):
    task_id: str
    material_id: Optional[str] = None
    status: str
    video_url: Optional[str] = None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    return auth_manager.get_current_user(token)


def _get_manager() -> CourseStorageManager:
    return storage_manager


def _resolve_scope_ids_for_course(
    *,
    mgr: CourseStorageManager,
    course_id: str,
    scope_type: str,
    scope_id: Optional[str],
) -> Optional[set[str]]:
    if scope_type != "knowledge_point":
        return None
    graph_root = mgr.get_knowledge_graph(course_id)
    return collect_scope_ids_for_query(
        graph_root,
        scope_type=scope_type,
        scope_id=scope_id,
    )


@contextmanager
def _without_proxy_env():
    previous = {key: os.environ.get(key) for key in _PROXY_ENV_KEYS}
    try:
        for key in _PROXY_ENV_KEYS:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


DEFAULT_COURSES: List[CourseInfo] = [
    CourseInfo(
        id="computational-thinking",
        title="计算思维",
        description="培养计算思维，学习问题分解、模式识别、抽象和算法设计",
        icon="CommentOutlined",
        color="#1890ff",
        objectives=[
            "理解计算思维的核心概念和方法",
            "掌握问题分解和模式识别技巧",
            "培养抽象思维和算法设计能力",
            "通过实践项目提升计算思维能力",
        ],
        knowledgeGraph="",
    ),
    CourseInfo(
        id="data-structures",
        title="数据结构",
        description="深入学习各种数据结构及其应用，掌握算法设计与分析",
        icon="DatabaseOutlined",
        color="#52c41a",
    ),
    CourseInfo(
        id="operating-systems",
        title="操作系统",
        description="理解操作系统原理，学习进程管理、内存管理和文件系统",
        icon="CloudServerOutlined",
        color="#fa8c16",
    ),
    CourseInfo(
        id="computer-networks",
        title="计算机网络",
        description="掌握网络协议、网络架构和网络安全等核心知识",
        icon="FileTextOutlined",
        color="#722ed1",
    ),
    CourseInfo(
        id="computer-organization",
        title="计算机组成原理",
        description="学习计算机硬件组成、指令系统、存储系统和 I/O 系统",
        icon="CloudServerOutlined",
        color="#13c2c2",
    ),
    CourseInfo(
        id="database-principles",
        title="数据库原理",
        description="掌握数据库设计、SQL 语言、事务处理和数据库管理系统",
        icon="DatabaseOutlined",
        color="#eb2f96",
    ),
]


def ensure_default_courses() -> None:
    mgr = _get_manager()
    for course in DEFAULT_COURSES:
        if mgr.get_course_info(course.id) is None:
            mgr.create_course_structure(course.id)
            mgr.save_course_info(course.id, course.model_dump())


@router.on_event("startup")
def _init_default_courses() -> None:
    ensure_default_courses()


@router.get("", response_model=List[CourseInfo], summary="获取课程列表")
def list_courses() -> List[CourseInfo]:
    mgr = _get_manager()
    results: List[CourseInfo] = []

    if not mgr.courses_dir.exists():
        ensure_default_courses()

    for course_dir in mgr.courses_dir.iterdir():
        if not course_dir.is_dir():
            continue
        info = mgr.get_course_info(course_dir.name)
        if not info:
            continue
        try:
            results.append(CourseInfo(**info))
        except Exception:
            continue

    if not results:
        ensure_default_courses()
        results = list(DEFAULT_COURSES)

    return results


@router.get("/{course_id}", response_model=CourseInfo, summary="获取课程详情")
def get_course(course_id: str) -> CourseInfo:
    mgr = _get_manager()
    info = mgr.get_course_info(course_id)
    if not info:
        raise HTTPException(status_code=404, detail="课程不存在")
    try:
        return CourseInfo(**info)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"课程数据格式错误: {exc}") from exc


@router.put("/{course_id}", response_model=CourseInfo, summary="更新课程信息")
def update_course(course_id: str, payload: CourseInfo) -> CourseInfo:
    if payload.id != course_id:
        raise HTTPException(status_code=400, detail="课程 ID 不一致")

    mgr = _get_manager()
    mgr.create_course_structure(course_id)
    if not mgr.save_course_info(course_id, payload.model_dump()):
        raise HTTPException(status_code=500, detail="保存课程信息失败")
    return payload


@router.post("", response_model=CourseInfo, summary="新建课程")
def create_course(payload: CourseInfo) -> CourseInfo:
    mgr = _get_manager()
    if mgr.get_course_info(payload.id) is not None:
        raise HTTPException(status_code=400, detail="课程 ID 已存在")

    mgr.create_course_structure(payload.id)
    if not mgr.save_course_info(payload.id, payload.model_dump()):
        raise HTTPException(status_code=500, detail="保存课程信息失败")
    return payload


@router.delete("/{course_id}", summary="删除课程")
def delete_course(course_id: str):
    mgr = _get_manager()
    if not mgr.delete_course(course_id):
        raise HTTPException(status_code=500, detail="删除课程失败")
    return {"message": "课程已删除"}


@router.get("/{course_id}/materials", summary="获取课程生成资源列表")
def get_course_materials(
    course_id: str,
    material_type: Optional[str] = None,
    scope_type: str = SCOPE_TYPE_COURSE,
    scope_id: Optional[str] = None,
    aggregate: bool = False,
    limit: Optional[int] = None,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    owner_user_id = current_user.get("username") if current_user else None
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    scope_ids = _resolve_scope_ids_for_course(
        mgr=mgr,
        course_id=course_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    materials = mgr.list_generated_materials(
        course_id,
        material_type=material_type,
        scope_type=scope_type,
        scope_ids=scope_ids,
        aggregate=aggregate,
    )
    if limit is None:
        return materials

    start = max(int(offset or 0), 0)
    end = start + max(int(limit), 0)
    paged_items = materials[start:end]
    return {
        "items": paged_items,
        "count": len(paged_items),
        "total": len(materials),
        "limit": int(limit),
        "offset": start,
    }


@router.delete("/{course_id}/materials/{material_type}/{material_id}", summary="删除课程生成资源")
def delete_course_material(
    course_id: str,
    material_type: str,
    material_id: str,
    current_user: dict = Depends(get_current_user),
):
    owner_user_id = current_user.get("username") if current_user else None
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    if not mgr.delete_generated_material(course_id, material_type, material_id):
        raise HTTPException(status_code=404, detail="资源不存在或删除失败")
    return {"ok": True}


@router.post("/{course_id}/materials/{material_type}/{material_id}/pin", summary="置顶课程生成资源")
def pin_course_material(
    course_id: str,
    material_type: str,
    material_id: str,
    payload: PinMaterialRequest,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    if not mgr.pin_generated_material(course_id, material_type, material_id, payload.is_pinned):
        raise HTTPException(status_code=404, detail="资源不存在或置顶失败")

    updated = mgr.get_generated_material(course_id, material_type, material_id)
    if not updated:
        raise HTTPException(status_code=404, detail="资源不存在")

    updated["material_id"] = material_id
    updated["material_type"] = updated.get("material_type") or material_type
    return updated


@router.get(
    "/{course_id}/teaching-videos/ppts",
    response_model=List[TeachingVideoPptItem],
    summary="获取可用于生成教学视频的 PPT 列表",
)
def list_teaching_video_ready_ppts(
    course_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    return get_teaching_video_bridge_service().list_available_ppts(course_id)


@router.post(
    "/{course_id}/teaching-videos",
    response_model=TeachingVideoTaskResponse,
    summary="为指定 PPT 创建教学视频任务",
)
def create_teaching_video_task(
    course_id: str,
    payload: CreateTeachingVideoTaskRequest,
    current_user: dict = Depends(get_current_user),
):
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    try:
        return get_teaching_video_bridge_service().create_task(
            course_id=course_id,
            ppt_material_id=payload.ppt_material_id,
            owner=str(current_user.get("username") or "").strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/{course_id}/teaching-videos/tasks/{task_id}",
    response_model=TeachingVideoTaskResponse,
    summary="查询教学视频任务状态",
)
def get_teaching_video_task_status(
    course_id: str,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    try:
        return get_teaching_video_bridge_service().get_task_status(course_id=course_id, task_id=task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{course_id}/lecture-sessions", summary="Create an AI lecture session resource")
def create_ai_lecture_session(
    course_id: str,
    payload: CreateAiLectureSessionRequest,
    current_user: dict = Depends(get_current_user),
):
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    return get_ai_lecture_session_service().create_session(
        course_id=course_id,
        source_ppt_material_id=payload.source_ppt_material_id,
        title=payload.title,
        owner=str(current_user.get("username") or "").strip(),
    )


@router.get("/{course_id}/lecture-sessions/{session_id}", summary="Get an AI lecture session")
def get_ai_lecture_session(
    course_id: str,
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        return get_ai_lecture_session_service().get_session(course_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{course_id}/lecture-sessions/{session_id}/snapshot", summary="Patch an AI lecture session snapshot")
def patch_ai_lecture_session_snapshot(
    course_id: str,
    session_id: str,
    payload: PatchAiLectureSessionSnapshotRequest,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        return get_ai_lecture_session_service().patch_snapshot(
            course_id=course_id,
            session_id=session_id,
            payload=payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{course_id}/lecture-sessions/{session_id}/recording/start", summary="Start AI lecture recording")
def start_ai_lecture_session_recording(
    course_id: str,
    session_id: str,
    payload: AiLectureRecordingRequest,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        return get_ai_lecture_session_service().start_recording(
            course_id,
            session_id,
            livetalking_session_id=payload.livetalking_session_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{course_id}/lecture-sessions/{session_id}/recording/stop", summary="Stop AI lecture recording")
def stop_ai_lecture_session_recording(
    course_id: str,
    session_id: str,
    payload: AiLectureRecordingRequest,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        return get_ai_lecture_session_service().stop_recording(
            course_id,
            session_id,
            livetalking_session_id=payload.livetalking_session_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{course_id}/lecture-sessions/{session_id}/recording", response_class=FileResponse, summary="Download AI lecture recording")
def get_ai_lecture_session_recording(
    course_id: str,
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        return get_ai_lecture_session_service().recording_response(course_id, session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/{course_id}/knowledge-base/documents",
    response_model=List[KnowledgeBaseDocument],
    summary="获取课程知识库文档列表",
)
def get_knowledge_base_documents(
    course_id: str,
    scope_type: str = SCOPE_TYPE_COURSE,
    scope_id: Optional[str] = None,
    aggregate: bool = False,
    library_type: str = LIBRARY_TYPE_COURSE,
    include_descendants: bool = True,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    owner_user_id = current_user.get("username") if current_user else None
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    if scope_type == "knowledge_point" and include_descendants:
        scope_ids = _resolve_scope_ids_for_course(
            mgr=mgr,
            course_id=course_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )
    elif scope_type == "knowledge_point":
        normalized_scope_id = str(scope_id or "").strip()
        scope_ids = {normalized_scope_id} if normalized_scope_id else set()
    else:
        scope_ids = None

    index = mgr.get_knowledge_base_index(
        course_id,
        scope_type=scope_type,
        scope_ids=scope_ids,
        aggregate=aggregate,
        library_type=library_type,
        owner_user_id=owner_user_id if library_type == LIBRARY_TYPE_PERSONAL else None,
    )
    if offset > 0 or limit > 0:
        index = index[max(offset, 0): max(offset, 0) + max(limit, 0)]
    documents: List[KnowledgeBaseDocument] = []
    for item in index:
        doc_type = "web" if "url" in item else "file"
        documents.append(
            KnowledgeBaseDocument(
                id=item.get("id", f"doc-{datetime.now().timestamp()}"),
                name=item.get("filename", item.get("name", "未命名文档")),
                type=doc_type,
                file_path=item.get("path") if doc_type == "file" else None,
                url=item.get("url") if doc_type == "web" else None,
                course_id=course_id,
                scope_type=str(item.get("scope_type") or SCOPE_TYPE_COURSE),
                scope_id=str(item.get("scope_id") or "").strip() or None,
                library_type=str(item.get("library_type") or LIBRARY_TYPE_COURSE),
                owner_user_id=str(item.get("owner_user_id") or "").strip() or None,
                promoted_from_document_id=str(item.get("promoted_from_document_id") or "").strip() or None,
                created_at=item.get("uploaded_at", datetime.now().isoformat()),
                updated_at=item.get("updated_at"),
            )
        )

    return documents


@router.post(
    "/{course_id}/knowledge-base/documents",
    response_model=KnowledgeBaseDocument,
    summary="上传文档到课程知识库",
)
async def upload_knowledge_base_document(
    course_id: str,
    scope_type: str = Form(default=SCOPE_TYPE_COURSE),
    scope_id: Optional[str] = Form(default=None),
    library_type: str = Form(default=LIBRARY_TYPE_COURSE),
    file: UploadFile = File(..., description="文档文件"),
    current_user: dict = Depends(get_current_user),
):
    owner_user_id = current_user.get("username") if current_user else None
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    file_data = await file.read()
    relative_path = mgr.save_knowledge_base_file(
        course_id,
        file_data,
        file.filename,
        scope_type=scope_type,
        scope_id=scope_id,
        library_type=library_type,
        owner_user_id=owner_user_id if library_type == LIBRARY_TYPE_PERSONAL else None,
    )
    if not relative_path:
        raise HTTPException(status_code=500, detail="保存文档失败")

    try:
        course_dir = mgr.get_course_dir(course_id)
        full_file_path = course_dir / relative_path
        rag_system = get_rag_system()
        rag_system.import_document(str(full_file_path), force_reimport=False)
    except Exception as exc:
        print(f"Warning: failed to import course document into RAG: {exc}")

    latest = None
    for item in reversed(mgr.get_knowledge_base_index(course_id)):
        if item.get("filename") == file.filename:
            latest = item
            break

    if latest is None:
        raise HTTPException(status_code=500, detail="读取上传后的文档信息失败")

    return KnowledgeBaseDocument(
        id=latest.get("id", f"doc-{datetime.now().timestamp()}"),
        name=latest.get("filename", file.filename),
        type="file",
        file_path=latest.get("path"),
        course_id=course_id,
        scope_type=str(latest.get("scope_type") or SCOPE_TYPE_COURSE),
        scope_id=str(latest.get("scope_id") or "").strip() or None,
        library_type=str(latest.get("library_type") or LIBRARY_TYPE_COURSE),
        owner_user_id=str(latest.get("owner_user_id") or "").strip() or None,
        promoted_from_document_id=str(latest.get("promoted_from_document_id") or "").strip() or None,
        created_at=latest.get("uploaded_at", datetime.now().isoformat()),
    )


@router.post(
    "/{course_id}/knowledge-base/documents/add-from-rag",
    response_model=KnowledgeBaseDocument,
    summary="把 RAG 文档加入课程知识库",
)
def add_rag_document_to_course_kb(
    course_id: str,
    request: AddRAGDocumentRequest,
    current_user: dict = Depends(get_current_user),
):
    mgr = _get_manager()
    rag_system = get_rag_system()
    owner = current_user.get("username") if current_user else None

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    course_dir = mgr.get_course_dir(course_id).resolve()
    requested_course_path = (course_dir / request.rag_file_path).resolve()
    try:
        requested_course_path.relative_to(course_dir)
        is_course_relative_path = True
    except ValueError:
        is_course_relative_path = False
    if is_course_relative_path and requested_course_path.exists():
        resolved_document = SimpleNamespace(physical_path=str(requested_course_path))
    else:
        resolved_document = resolve_rag_document(rag_system, request.rag_file_path, owner=owner)
    if not resolved_document:
        raise HTTPException(status_code=404, detail="RAG 系统中未找到该文档")

    rag_path = Path(resolved_document.physical_path)
    if not rag_path.exists():
        raise HTTPException(status_code=404, detail="RAG 文档不存在")

    all_docs = rag_system.list_documents(owner=owner) if owner else rag_system.list_documents()

    with open(rag_path, "rb") as f:
        file_data = f.read()

    relative_path = mgr.save_knowledge_base_file(
        course_id,
        file_data,
        rag_path.name,
        scope_type=request.scope_type,
        scope_id=request.scope_id,
        library_type=request.library_type,
        owner_user_id=owner if request.library_type == LIBRARY_TYPE_PERSONAL else None,
        promoted_from_document_id=request.promoted_from_document_id,
    )
    if not relative_path:
        raise HTTPException(status_code=500, detail="保存文档失败")

    try:
        course_dir = mgr.get_course_dir(course_id)
        full_file_path = course_dir / relative_path
        if not any(doc.get("file_path") == str(full_file_path) for doc in all_docs):
            rag_system.import_document(str(full_file_path), force_reimport=False)
    except Exception as exc:
        print(f"Warning: failed to sync added RAG document back into RAG index: {exc}")

    latest = None
    for item in reversed(mgr.get_knowledge_base_index(course_id)):
        if item.get("filename") == rag_path.name:
            latest = item
            break

    if latest is None:
        raise HTTPException(status_code=500, detail="读取文档信息失败")

    return KnowledgeBaseDocument(
        id=latest.get("id", f"doc-{datetime.now().timestamp()}"),
        name=latest.get("filename", rag_path.name),
        type="file",
        file_path=latest.get("path"),
        course_id=course_id,
        scope_type=str(latest.get("scope_type") or SCOPE_TYPE_COURSE),
        scope_id=str(latest.get("scope_id") or "").strip() or None,
        library_type=str(latest.get("library_type") or LIBRARY_TYPE_COURSE),
        owner_user_id=str(latest.get("owner_user_id") or "").strip() or None,
        promoted_from_document_id=str(latest.get("promoted_from_document_id") or "").strip() or None,
        created_at=latest.get("uploaded_at", datetime.now().isoformat()),
    )


@router.delete(
    "/{course_id}/knowledge-base/documents/{document_id}",
    summary="删除课程知识库文档",
)
def delete_knowledge_base_document(
    course_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    index = mgr.get_knowledge_base_index(course_id)
    doc_to_delete = next((item for item in index if item.get("id") == document_id), None)
    if not doc_to_delete:
        raise HTTPException(status_code=404, detail="文档不存在")

    if doc_to_delete.get("path"):
        file_path = mgr.get_file_path(course_id, doc_to_delete["path"])
        if file_path.exists():
            file_path.unlink()
            try:
                rag_system = get_rag_system()
                rag_system.delete_document(str(file_path))
            except Exception as exc:
                print(f"Warning: failed to delete document from RAG system: {exc}")

    next_index = [item for item in index if item.get("id") != document_id]
    mgr.save_knowledge_base_index(course_id, next_index)
    return {"message": "文档已删除"}


def _find_kg_node(root: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    if not isinstance(root, dict):
        return None
    if str(root.get("id")) == node_id:
        return root

    children = root.get("children")
    if not isinstance(children, list):
        return None

    for child in children:
        if not isinstance(child, dict):
            continue
        found = _find_kg_node(child, node_id)
        if found is not None:
            return found
    return None


def _call_knowledge_graph_hour_llm(prompt: str) -> str:
    rag_system = get_rag_system()
    model_config = Config.get_deep_model()
    with _without_proxy_env():
        raw = rag_system._call_llm(prompt, llm_config=model_config)  # type: ignore[attr-defined]
    return str(raw or "")


@router.get("/{course_id}/knowledge-graph", response_model=KnowledgeGraphData, summary="获取课程知识图谱")
def get_knowledge_graph(
    course_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    graph_data = mgr.get_knowledge_graph(course_id)
    if graph_data is None:
        return KnowledgeGraphData(
            root={
                "id": "root",
                "label": "知识图谱",
                "data": {
                    "level": 0,
                    "summary": "课程知识图谱",
                    "hasChildren": False,
                    "type": "concept",
                },
                "children": [],
            }
        )

    return KnowledgeGraphData(root=graph_data)


@router.get(
    "/{course_id}/knowledge-graph/nodes/{node_id}",
    response_model=KnowledgeGraphData,
    summary="按节点 ID 获取知识图谱子树",
)
def get_knowledge_graph_subtree(
    course_id: str,
    node_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    graph_data = mgr.get_knowledge_graph(course_id)
    if graph_data is None:
        raise HTTPException(status_code=404, detail="课程知识图谱不存在")

    node = _find_kg_node(graph_data, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="知识图谱节点不存在")

    return KnowledgeGraphData(root=node)


@router.post(
    "/{course_id}/knowledge-graph/allocate-hours",
    response_model=KnowledgeGraphHourAllocationResponse,
    summary="Allocate teaching hours for course knowledge graph nodes",
)
def allocate_knowledge_graph_hours(
    course_id: str,
    payload: KnowledgeGraphHourAllocationRequest,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    graph_data = mgr.get_knowledge_graph(course_id)
    if graph_data is None:
        raise HTTPException(status_code=404, detail="课程知识图谱不存在")

    try:
        updated_graph, allocation_meta = allocate_graph_hours_from_llm(
            graph_data,
            payload.total_hours,
            _call_knowledge_graph_hour_llm,
        )
    except KnowledgeGraphHourAllocationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"调用大模型分配课时失败: {exc}") from exc

    if not mgr.save_knowledge_graph(course_id, updated_graph):
        raise HTTPException(status_code=500, detail="保存知识图谱课时分配失败")

    return KnowledgeGraphHourAllocationResponse(root=updated_graph, allocation=allocation_meta)


@router.put("/{course_id}/knowledge-graph", response_model=KnowledgeGraphData, summary="保存课程知识图谱")
def save_knowledge_graph(
    course_id: str,
    payload: KnowledgeGraphData,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    if not mgr.save_knowledge_graph(course_id, payload.root):
        raise HTTPException(status_code=500, detail="保存知识图谱失败")

    return payload
