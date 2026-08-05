"""Course API routes — HTTP layer only.

Delegates business logic to app.services.course_service and core storage.
"""

from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.knowledge_graph_hours import (
    KnowledgeGraphHourAllocationError,
    allocate_graph_hours_from_llm,
)
from app.schemas.course import (
    AddRAGDocumentRequest,
    CourseInfo,
    GenerateClassroomRequest,
    KnowledgeBaseDocument,
    KnowledgeBaseDocumentUploadResponse,
    KnowledgeBaseRetrievalTestRequest,
    KnowledgeBaseRetrievalTestResponse,
    KnowledgeGraphData,
    KnowledgeGraphHourAllocationRequest,
    KnowledgeGraphHourAllocationResponse,
    PinMaterialRequest,
)
from app.services import course_service as _svc
from app.services import knowledge_document_service as _knowledge
from app.services.classroom_service import submit_classroom_generation_job
from app.services.classroom_video_export import (
    VIDEO_ARTIFACT_MEDIA_TYPES,
    submit_classroom_video_export_job,
)
from app.textbook_knowledge_graph import (
    TextbookKnowledgeGraphError,
    import_textbook_into_knowledge_graph,
)
from core.auth import auth_manager
from core.course_storage import LIBRARY_TYPE_COURSE, LIBRARY_TYPE_PERSONAL
from modules.rag_v2.api import get_rag_system
from modules.rag_v2.document_resolver import resolve_rag_document

security = HTTPBearer()
router = APIRouter(prefix="/api/courses", tags=["courses"])


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    return auth_manager.get_current_user(token)


def _knowledge_document_model(
    item: dict, course_id: str
) -> KnowledgeBaseDocument:
    doc_type = "web" if item.get("url") else "file"
    return KnowledgeBaseDocument(
        id=str(item.get("id") or f"doc-{datetime.now().timestamp()}"),
        name=item.get("filename", item.get("name", "未命名文档")),
        type=doc_type,
        file_path=item.get("path"),
        url=item.get("url") if doc_type == "web" else None,
        course_id=course_id,
        scope_type=str(item.get("scope_type") or "course"),
        scope_id=str(item.get("scope_id") or "").strip() or None,
        library_type=str(item.get("library_type") or LIBRARY_TYPE_COURSE),
        owner_user_id=str(item.get("owner_user_id") or "").strip() or None,
        promoted_from_document_id=str(
            item.get("promoted_from_document_id") or ""
        ).strip()
        or None,
        created_at=item.get("uploaded_at", datetime.now().isoformat()),
        updated_at=item.get("updated_at"),
        status=str(
            item.get("status")
            or ("ready" if item.get("rag_index_key") else "received")
        ),
        active_index_version=item.get("active_index_version"),
        pending_index_version=item.get("pending_index_version"),
        page_count=int(item.get("page_count") or 0),
        chunk_count=int(item.get("chunk_count") or 0),
        failed_units=int(item.get("failed_units") or 0),
        parser_name=item.get("parser_name"),
        embedding_profile_id=item.get("embedding_profile_id"),
        indexed_at=item.get("indexed_at"),
        last_job_id=item.get("last_job_id"),
        error_code=item.get("error_code"),
        error_message=item.get("error_message"),
    )


# ---------------------------------------------------------------------------
# startup
# ---------------------------------------------------------------------------


@router.on_event("startup")
def _init_default_courses() -> None:
    _svc.ensure_default_courses()


# ---------------------------------------------------------------------------
# course CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=List[CourseInfo], summary="获取课程列表")
def list_courses() -> List[CourseInfo]:
    mgr = _svc._get_manager()
    results: List[CourseInfo] = []

    if not mgr.courses_dir.exists():
        _svc.ensure_default_courses()

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
        _svc.ensure_default_courses()
        results = [CourseInfo(**c) for c in _svc.DEFAULT_COURSES]

    return results


@router.get("/{course_id}", response_model=CourseInfo, summary="获取课程详情")
def get_course(course_id: str) -> CourseInfo:
    mgr = _svc._get_manager()
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

    mgr = _svc._get_manager()
    mgr.create_course_structure(course_id)
    if not mgr.save_course_info(course_id, payload.model_dump()):
        raise HTTPException(status_code=500, detail="保存课程信息失败")
    return payload


@router.post("", response_model=CourseInfo, summary="新建课程")
def create_course(payload: CourseInfo) -> CourseInfo:
    mgr = _svc._get_manager()
    if mgr.get_course_info(payload.id) is not None:
        raise HTTPException(status_code=400, detail="课程 ID 已存在")

    mgr.create_course_structure(payload.id)
    if not mgr.save_course_info(payload.id, payload.model_dump()):
        raise HTTPException(status_code=500, detail="保存课程信息失败")
    return payload


@router.delete("/{course_id}", summary="删除课程")
def delete_course(course_id: str):
    mgr = _svc._get_manager()
    if not mgr.delete_course(course_id):
        raise HTTPException(status_code=500, detail="删除课程失败")
    return {"message": "课程已删除"}


# ---------------------------------------------------------------------------
# course materials
# ---------------------------------------------------------------------------


@router.get("/{course_id}/materials", summary="获取课程生成资源列表")
def get_course_materials(
    course_id: str,
    material_type: Optional[str] = None,
    scope_type: str = "course",
    scope_id: Optional[str] = None,
    aggregate: bool = False,
    limit: Optional[int] = None,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    owner_user_id = current_user.get("username") if current_user else None
    mgr = _svc._get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    scope_ids = _svc._resolve_scope_ids_for_course(
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
    mgr = _svc._get_manager()

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
    mgr = _svc._get_manager()

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


# ---------------------------------------------------------------------------
# knowledge base documents
# ---------------------------------------------------------------------------


@router.get(
    "/{course_id}/knowledge-base/documents",
    response_model=List[KnowledgeBaseDocument],
    summary="获取课程知识库文档列表",
)
def get_knowledge_base_documents(
    course_id: str,
    scope_type: str = "course",
    scope_id: Optional[str] = None,
    aggregate: bool = False,
    library_type: str = LIBRARY_TYPE_COURSE,
    include_descendants: bool = True,
    document_status: Optional[str] = None,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    owner_user_id = current_user.get("username") if current_user else None
    mgr = _svc._get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    if scope_type == "knowledge_point" and include_descendants:
        scope_ids = _svc._resolve_scope_ids_for_course(
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
    if document_status:
        index = [
            item
            for item in index
            if str(item.get("status") or "received") == document_status
        ]
    normalized_search = str(search or "").strip().casefold()
    if normalized_search:
        index = [
            item
            for item in index
            if normalized_search
            in str(item.get("filename") or item.get("name") or "").casefold()
        ]
    sorters = {
        "created_desc": lambda item: str(
            item.get("uploaded_at") or item.get("created_at") or ""
        ),
        "created_asc": lambda item: str(
            item.get("uploaded_at") or item.get("created_at") or ""
        ),
        "name_asc": lambda item: str(
            item.get("filename") or item.get("name") or ""
        ).casefold(),
        "name_desc": lambda item: str(
            item.get("filename") or item.get("name") or ""
        ).casefold(),
    }
    if sort is not None and sort not in sorters:
        raise HTTPException(status_code=422, detail="不支持的排序方式")
    if sort is not None:
        index = sorted(
            index,
            key=sorters[sort],
            reverse=sort in {"created_desc", "name_desc"},
        )
    if offset > 0 or limit > 0:
        index = index[max(offset, 0): max(offset, 0) + max(limit, 0)]
    return [_knowledge_document_model(item, course_id) for item in index]


@router.post(
    "/{course_id}/knowledge-base/documents",
    response_model=KnowledgeBaseDocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="上传文档到课程知识库",
)
async def upload_knowledge_base_document(
    course_id: str,
    scope_type: str = Form(default="course"),
    scope_id: Optional[str] = Form(default=None),
    library_type: str = Form(default=LIBRARY_TYPE_COURSE),
    file: UploadFile = File(..., description="文档文件"),
    current_user: dict = Depends(get_current_user),
):
    owner_user_id = current_user.get("username") if current_user else None
    mgr = _svc._get_manager()

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

    latest = None
    for item in reversed(mgr.get_knowledge_base_index(course_id)):
        if item.get("filename") == file.filename:
            latest = item
            break

    if latest is None:
        raise HTTPException(status_code=500, detail="读取上传后的文档信息失败")

    document_id = str(latest.get("id") or "")
    latest = _knowledge.initialize_document(mgr, course_id, document_id)
    job = _knowledge.submit_index_job(
        manager=mgr,
        rag_system=get_rag_system(),
        course_id=course_id,
        document_id=document_id,
        owner_user_id=str(owner_user_id or ""),
        force_reindex=False,
    )
    latest = _knowledge.get_document(
        mgr,
        course_id,
        document_id,
        owner_user_id=str(owner_user_id or ""),
    ) or latest
    return {
        "document": _knowledge_document_model(latest, course_id),
        "job": job.model_dump(mode="json"),
    }


@router.post(
    "/{course_id}/knowledge-graph/textbook-import",
    summary="Import a textbook and regenerate the course knowledge graph",
)
async def import_textbook_knowledge_graph(
    course_id: str,
    file: UploadFile = File(..., description="Textbook file"),
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _svc._get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Textbook file is required")

    try:
        return import_textbook_into_knowledge_graph(
            course_id=course_id,
            filename=file.filename,
            file_bytes=await file.read(),
            manager=mgr,
            rag_system=get_rag_system(),
        )
    except TextbookKnowledgeGraphError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to import textbook: {exc}") from exc


@router.post(
    "/{course_id}/knowledge-base/documents/add-from-rag",
    response_model=KnowledgeBaseDocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="把 RAG 文档加入课程知识库",
)
async def add_rag_document_to_course_kb(
    course_id: str,
    request: AddRAGDocumentRequest,
    current_user: dict = Depends(get_current_user),
):
    mgr = _svc._get_manager()
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

    latest = None
    for item in reversed(mgr.get_knowledge_base_index(course_id)):
        if item.get("filename") == rag_path.name:
            latest = item
            break

    if latest is None:
        raise HTTPException(status_code=500, detail="读取文档信息失败")

    document_id = str(latest.get("id") or "")
    latest = _knowledge.initialize_document(mgr, course_id, document_id)
    job = _knowledge.submit_index_job(
        manager=mgr,
        rag_system=rag_system,
        course_id=course_id,
        document_id=document_id,
        owner_user_id=str(owner or ""),
        force_reindex=False,
    )
    latest = _knowledge.get_document(
        mgr,
        course_id,
        document_id,
        owner_user_id=str(owner or ""),
    ) or latest
    return {
        "document": _knowledge_document_model(latest, course_id),
        "job": job.model_dump(mode="json"),
    }


@router.get(
    "/{course_id}/knowledge-base/documents/{document_id}",
    response_model=KnowledgeBaseDocument,
    summary="获取知识库文档处理详情",
)
def get_knowledge_base_document_detail(
    course_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    owner = str(current_user.get("username") or "")
    document = _knowledge.get_document(
        _svc._get_manager(),
        course_id,
        document_id,
        owner_user_id=owner,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    return _knowledge_document_model(document, course_id)


def _submit_knowledge_document_job(
    *,
    course_id: str,
    document_id: str,
    current_user: dict,
    force_reindex: bool,
):
    owner = str(current_user.get("username") or "")
    try:
        return _knowledge.submit_index_job(
            manager=_svc._get_manager(),
            rag_system=get_rag_system(),
            course_id=course_id,
            document_id=document_id,
            owner_user_id=owner,
            force_reindex=force_reindex,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="文档不存在或无权访问"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/{course_id}/knowledge-base/documents/{document_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="重试失败的知识库文档处理",
)
def retry_knowledge_base_document(
    course_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    document = _knowledge.get_document(
        _svc._get_manager(),
        course_id,
        document_id,
        owner_user_id=str(current_user.get("username") or ""),
    )
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    if document.get("status") != "failed":
        raise HTTPException(status_code=409, detail="仅失败文档可以重试")
    return _submit_knowledge_document_job(
        course_id=course_id,
        document_id=document_id,
        current_user=current_user,
        force_reindex=False,
    )


@router.post(
    "/{course_id}/knowledge-base/documents/{document_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    summary="重建知识库文档索引",
)
def reindex_knowledge_base_document(
    course_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    return _submit_knowledge_document_job(
        course_id=course_id,
        document_id=document_id,
        current_user=current_user,
        force_reindex=True,
    )


@router.post(
    "/{course_id}/knowledge-base/documents/{document_id}/test-retrieval",
    response_model=KnowledgeBaseRetrievalTestResponse,
    summary="在单个知识库文档内测试检索",
)
def test_knowledge_base_document_retrieval(
    course_id: str,
    document_id: str,
    payload: KnowledgeBaseRetrievalTestRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        return _knowledge.test_retrieval(
            manager=_svc._get_manager(),
            rag_system=get_rag_system(),
            course_id=course_id,
            document_id=document_id,
            owner_user_id=str(current_user.get("username") or ""),
            query=payload.query,
            top_k=payload.top_k,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="文档不存在或无权访问"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/{course_id}/knowledge-base/documents/{document_id}",
    summary="删除课程知识库文档",
)
def delete_knowledge_base_document(
    course_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    mgr = _svc._get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    owner = str(current_user.get("username") or "")
    index = mgr.get_knowledge_base_index(course_id)
    doc_to_delete = _knowledge.get_document(
        mgr,
        course_id,
        document_id,
        owner_user_id=owner,
    )
    if not doc_to_delete:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")

    if doc_to_delete.get("path"):
        file_path = mgr.get_file_path(course_id, doc_to_delete["path"])
        try:
            rag_system = get_rag_system()
            rag_system.delete_document(str(file_path), owner=owner)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"删除检索索引失败，原文件已保留：{exc}",
            ) from exc
        if file_path.exists():
            file_path.unlink()

    next_index = [item for item in index if item.get("id") != document_id]
    if not mgr.save_knowledge_base_index(course_id, next_index):
        raise HTTPException(status_code=500, detail="删除文档记录失败")
    return {"message": "文档已删除"}


# ---------------------------------------------------------------------------
# knowledge graph
# ---------------------------------------------------------------------------


@router.get("/{course_id}/knowledge-graph", response_model=KnowledgeGraphData, summary="获取课程知识图谱")
def get_knowledge_graph(
    course_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _svc._get_manager()

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
    mgr = _svc._get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    graph_data = mgr.get_knowledge_graph(course_id)
    if graph_data is None:
        raise HTTPException(status_code=404, detail="课程知识图谱不存在")

    node = _svc._find_kg_node(graph_data, node_id)
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
    mgr = _svc._get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    graph_data = mgr.get_knowledge_graph(course_id)
    if graph_data is None:
        raise HTTPException(status_code=404, detail="课程知识图谱不存在")

    try:
        updated_graph, allocation_meta = allocate_graph_hours_from_llm(
            graph_data,
            payload.total_hours,
            _svc._call_knowledge_graph_hour_llm,
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
    mgr = _svc._get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    if not mgr.save_knowledge_graph(course_id, payload.root):
        raise HTTPException(status_code=500, detail="保存知识图谱失败")

    return payload


@router.post(
    "/{course_id}/classrooms/generate",
    status_code=202,
    summary="提交课件生成任务（P2-5 classroom_service，异步）",
)
async def generate_classroom(
    course_id: str,
    payload: GenerateClassroomRequest,
    current_user: dict = Depends(get_current_user),
):
    """提交即返回（202 + queued 状态的 edu_job），真正的生成/校验/落库在
    后台任务里跑（真实实测一份 9-scene 课件约 20 分钟，不适合同步 await）。
    前端轮询 `GET /api/jobs/{edu_job_id}` 直到 `done`（SPEC-05 §3）。
    """
    mgr = _svc._get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    owner = current_user.get("username") if current_user else None
    job = await submit_classroom_generation_job(
        course_id=course_id,
        requirement=payload.requirement,
        owner=owner,
        course_storage_manager=mgr,
        enable_web_search=payload.enable_web_search,
        enable_tts=payload.enable_tts,
    )
    return job


@router.get("/{course_id}/classrooms/{classroom_id}", summary="读取一份已落库的课件")
def get_classroom(
    course_id: str,
    classroom_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _svc._get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    material = mgr.get_generated_material(course_id, "classroom", classroom_id)
    if material is None:
        raise HTTPException(status_code=404, detail="课件不存在")
    return material


@router.post(
    "/{course_id}/classrooms/{classroom_id}/video/export",
    status_code=202,
    summary="提交 OpenMAIC 课堂 MP4 导出任务",
)
async def export_classroom_video(
    course_id: str,
    classroom_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    current_user = auth_manager.get_current_user(credentials.credentials)
    mgr = _svc._get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    if mgr.get_generated_material(course_id, "classroom", classroom_id) is None:
        raise HTTPException(status_code=404, detail="课件不存在")

    owner = current_user.get("username") if current_user else None
    return await submit_classroom_video_export_job(
        course_id=course_id,
        classroom_id=classroom_id,
        auth_token=credentials.credentials,
        current_user=current_user,
        owner=owner,
        course_storage_manager=mgr,
    )


@router.get("/{course_id}/classrooms", summary="列出课程下已落库的课件")
def list_classrooms(
    course_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _svc._get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    return mgr.list_generated_materials(course_id, "classroom")


@router.get(
    "/{course_id}/classrooms/{classroom_id}/audio/{filename}",
    response_class=FileResponse,
    summary="读取课件配音文件（D1 迁移落盘，见 classroom_media.migrate_classroom_speech_audio）",
)
def get_classroom_audio(
    course_id: str,
    classroom_id: str,
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _svc._get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    audio_root = mgr.get_classroom_audio_dir(course_id, classroom_id).resolve()
    path = (audio_root / filename).resolve()
    try:
        path.relative_to(audio_root)
    except ValueError:
        raise HTTPException(status_code=404, detail="音频文件不存在")
    if not path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")

    media_type, _ = mimetypes.guess_type(path.name)
    return FileResponse(path=path, filename=path.name, media_type=media_type or "application/octet-stream")


@router.get(
    "/{course_id}/classrooms/{classroom_id}/video/{filename}",
    response_class=FileResponse,
    summary="下载课堂 MP4、SRT 或实测时间线",
)
def get_classroom_video_artifact(
    course_id: str,
    classroom_id: str,
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    media_type = VIDEO_ARTIFACT_MEDIA_TYPES.get(filename)
    if media_type is None:
        raise HTTPException(status_code=404, detail="视频导出文件不存在")
    mgr = _svc._get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    video_root = mgr.get_classroom_video_dir(course_id, classroom_id).resolve()
    path = (video_root / filename).resolve()
    try:
        path.relative_to(video_root)
    except ValueError:
        raise HTTPException(status_code=404, detail="视频导出文件不存在")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="视频导出文件不存在")
    return FileResponse(path=path, filename=filename, media_type=media_type)
