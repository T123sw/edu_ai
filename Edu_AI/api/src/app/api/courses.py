"""Course API routes — HTTP layer only.

Delegates business logic to app.services.course_service and core storage.
"""

from __future__ import annotations

import mimetypes
import json
import re
import copy
from datetime import datetime
from uuid import uuid4
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from app.auth import get_current_user
from app.api.course_dependencies import (
    get_course_membership_store,
    require_course_edit,
    require_course_generate,
    require_course_manage_resources,
    require_course_owner,
    require_course_read,
)
from app.services.course_access import (
    CoursePrincipal,
    can_manage_course_resources,
)
from app.services.generation_source_errors import GenerationSourceError
from app.services.course_code_service import generate_course_code
from app.services.course_enrollment_service import (
    CourseEnrollmentError,
    CourseEnrollmentService,
)

from app.knowledge_graph_hours import (
    KnowledgeGraphHourAllocationError,
    allocate_graph_hours_from_llm,
)
from app.schemas.course import (
    AddRAGDocumentRequest,
    CourseCreateRequest,
    CourseInfo,
    CourseJoinRequest,
    CourseMemberCreateRequest,
    CourseMemberInfo,
    CourseMembersResponse,
    CourseMemberUpdateRequest,
    CourseKnowledgeBuildRequest,
    CourseKnowledgeBuildDraftCreateRequest,
    CourseKnowledgeBuildDraftUpdateRequest,
    CourseKnowledgeGraphConfirmRequest,
    CourseKnowledgeGraphDraftUpdateRequest,
    CourseKnowledgeGraphGenerateRequest,
    CourseKnowledgeTextbookMutationRequest,
    CourseKnowledgeBuildPreviewRequest,
    CourseUpdateRequest,
    GenerateClassroomRequest,
    KnowledgeBaseDocument,
    KnowledgeBaseDocumentContent,
    KnowledgeBaseDocumentUploadResponse,
    KnowledgeBaseRetrievalTestRequest,
    KnowledgeBaseRetrievalTestResponse,
    KnowledgeGraphData,
    KnowledgeGraphHourAllocationRequest,
    KnowledgeGraphHourAllocationResponse,
    MaterialPublicationResponse,
    MaterialContentUpdateRequest,
    PinMaterialRequest,
    RenameMaterialRequest,
)
from app.services import course_service as _svc
from app.services import knowledge_document_service as _knowledge
from app.services.course_knowledge_plan_builder import submit_course_knowledge_plan_build_job
from app.services.course_knowledge_graph_generator import (
    submit_course_knowledge_graph_generation_job,
    validate_graph_draft_for_build,
)
from app.services.course_knowledge_textbook_inputs import (
    CourseKnowledgeTextbookInputError,
    remove_course_knowledge_textbook,
    retry_course_knowledge_textbook,
    stage_course_knowledge_textbook,
    submit_course_knowledge_textbook_parse_job,
)
from app.services.course_knowledge_builder import submit_course_knowledge_build_job
from app.services.classroom_service import submit_classroom_generation_job
from app.services.classroom_video_export import (
    VIDEO_ARTIFACT_MEDIA_TYPES,
    submit_classroom_video_export_job,
)
from app.services.material_publication_service import (
    MaterialPublicationError,
    MaterialPublicationService,
)
from app.services.personal_tool_access import (
    PersonalToolAccessDenied,
    require_personal_tool,
)
from app.persistence.dependencies import get_postgres_knowledge_repository
from app.persistence.postgres_knowledge_repository import (
    KnowledgeBuildRevisionConflict,
)
from core.course_storage import (
    LIBRARY_TYPE_COURSE,
    LIBRARY_TYPE_PERSONAL,
    CourseRevisionConflict,
)
from core.user_storage import user_storage
from modules.rag_v2.api import get_rag_system
from modules.rag_v2.document_resolver import resolve_rag_document

router = APIRouter(prefix="/api/courses", tags=["courses"])


def get_course_enrollment_service() -> CourseEnrollmentService:
    return CourseEnrollmentService(
        manager=_svc._get_manager(),
        memberships=get_course_membership_store(),
        users_provider=user_storage.list_users,
    )


def _enrollment_http_error(error: CourseEnrollmentError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": str(error)},
    )


def _course_response(info: dict[str, Any], role: str) -> CourseInfo:
    payload = {**info, "membership_role": role}
    if role != "owner":
        payload["course_code"] = None
    return CourseInfo(**payload)


def _material_publications() -> MaterialPublicationService:
    return MaterialPublicationService(_svc._get_manager())


def _material_http_error(
    status_code: int, code: str, message: str
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _publication_http_error(error: MaterialPublicationError) -> HTTPException:
    status_by_code = {
        "MATERIAL_NOT_FOUND": 404,
        "MATERIAL_ARTIFACT_UNSAFE": 422,
        "MATERIAL_PUBLICATION_INVALID": 409,
    }
    return _material_http_error(
        status_by_code.get(error.code, 409), error.code, str(error)
    )


def _mutable_material_or_raise(
    *,
    manager,
    course_id: str,
    material_type: str,
    material_id: str,
    principal: CoursePrincipal,
):
    material = manager.get_generated_material(
        course_id,
        material_type,
        material_id,
        owner_user_id=principal.user_id,
    )
    if material is None:
        raise _material_http_error(404, "MATERIAL_NOT_FOUND", "资源不存在或无权访问")
    if material.get("visibility") == "course" and not can_manage_course_resources(
        principal
    ):
        raise _material_http_error(
            403, "MATERIAL_MANAGE_FORBIDDEN", "无权管理课程共享资源"
        )
    return material


def _knowledge_document_model(
    item: dict, course_id: str
) -> KnowledgeBaseDocument:
    source_url = str(item.get("url") or item.get("source_url") or "").strip()
    doc_type = "web" if source_url or item.get("doc_kind") == "web" else "file"
    return KnowledgeBaseDocument(
        id=str(item.get("id") or f"doc-{datetime.now().timestamp()}"),
        name=item.get("filename", item.get("name", "未命名文档")),
        display_name=(
            str(item.get("source_title") or "").strip()
            or item.get("filename", item.get("name", "未命名文档"))
        ),
        type=doc_type,
        # Filesystem-relative paths are internal implementation details. Public
        # course APIs use the stable document ID for all subsequent actions.
        file_path=None,
        url=source_url if doc_type == "web" else None,
        source_title=item.get("source_title"),
        source_domain=item.get("source_domain"),
        source_site_name=item.get("source_site_name"),
        source_icon_url=item.get("source_icon_url"),
        source_license=item.get("source_license"),
        source_license_url=item.get("source_license_url"),
        source_revision=item.get("source_revision"),
        source_language=item.get("source_language"),
        content_language=item.get("content_language"),
        translation_notice=item.get("translation_notice"),
        usage_restriction=item.get("usage_restriction"),
        authority_tier=item.get("authority_tier"),
        retrieved_at=item.get("retrieved_at"),
        source_type=item.get("source_type"),
        generation_review_score=item.get("generation_review_score"),
        generation_audit=item.get("generation_audit"),
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
def list_courses(
    current_user: dict = Depends(get_current_user),
) -> List[CourseInfo]:
    mgr = _svc._get_manager()
    results: List[CourseInfo] = []

    if not mgr.courses_dir.exists():
        _svc.ensure_default_courses()

    memberships = {
        item.course_id: item
        for item in get_course_membership_store().list_for_user(
            str(current_user.get("username") or "")
        )
    }
    for info in mgr.list_course_infos():
        course_id = str(info.get("id") or info.get("course_id") or "").strip()
        membership = memberships.get(course_id)
        if membership is None:
            continue
        try:
            results.append(_course_response(info, membership.role))
        except Exception:
            continue

    return results


@router.post("/join", response_model=CourseInfo, summary="使用课程码加入课程")
def join_course(
    payload: CourseJoinRequest,
    current_user: dict = Depends(get_current_user),
    service: CourseEnrollmentService = Depends(get_course_enrollment_service),
) -> CourseInfo:
    try:
        info = service.join(
            course_code=payload.course_code,
            user_id=str(current_user.get("username") or ""),
            system_role=str(current_user.get("role") or ""),
        )
    except CourseEnrollmentError as error:
        raise _enrollment_http_error(error) from error
    return _course_response(info, "viewer")


@router.get("/{course_id}", response_model=CourseInfo, summary="获取课程详情")
def get_course(
    course_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
) -> CourseInfo:
    mgr = _svc._get_manager()
    info = mgr.get_course_info(course_id)
    if not info:
        raise HTTPException(status_code=404, detail="课程不存在")
    try:
        return _course_response(info, principal.course_role)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"课程数据格式错误: {exc}") from exc


@router.put("/{course_id}", response_model=CourseInfo, summary="更新课程信息")
def update_course(
    course_id: str,
    payload: CourseUpdateRequest,
    principal: CoursePrincipal = Depends(require_course_edit),
) -> CourseInfo:
    mgr = _svc._get_manager()
    try:
        updated = mgr.update_course_info(
            course_id,
            payload.model_dump(exclude={"expected_revision"}, exclude_unset=True),
            expected_revision=payload.expected_revision,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="课程不存在") from exc
    except CourseRevisionConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "COURSE_REVISION_CONFLICT",
                "expected_revision": exc.expected,
                "actual_revision": exc.actual,
            },
        ) from exc
    return _course_response(updated, principal.course_role)


@router.post("", response_model=CourseInfo, summary="新建课程")
def create_course(
    payload: CourseCreateRequest,
    current_user: dict = Depends(get_current_user),
    enrollment: CourseEnrollmentService = Depends(get_course_enrollment_service),
) -> CourseInfo:
    if str(current_user.get("role") or "").lower() not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="仅教师可以新建课程")
    mgr = _svc._get_manager()
    course_id = payload.id or f"course-{uuid4().hex}"
    if mgr.get_course_info(course_id) is not None:
        raise HTTPException(status_code=400, detail="课程 ID 已存在")

    creator_id = str(current_user.get("username") or "").strip()
    course_code = generate_course_code(enrollment.course_code_exists)
    now = datetime.now().isoformat()
    course_info = {
        **payload.model_dump(exclude={"id"}),
        "id": course_id,
        "course_code": course_code,
        "revision": 0,
        "created_by": creator_id,
        "created_at": now,
        "updated_at": now,
    }
    mgr.create_course_structure(course_id)
    if not mgr.save_course_info(course_id, course_info):
        raise HTTPException(status_code=500, detail="保存课程信息失败")
    store = get_course_membership_store()
    store.upsert(course_id, creator_id, "owner", added_by=creator_id)
    return _course_response(course_info, "owner")


@router.get(
    "/{course_id}/members",
    response_model=CourseMembersResponse,
    summary="获取课程成员",
)
def list_course_members(
    course_id: str,
    _principal: CoursePrincipal = Depends(require_course_owner),
    service: CourseEnrollmentService = Depends(get_course_enrollment_service),
) -> CourseMembersResponse:
    return CourseMembersResponse(items=service.list_members(course_id))


@router.post(
    "/{course_id}/members",
    response_model=CourseMemberInfo,
    summary="添加课程成员",
)
def add_course_member(
    course_id: str,
    payload: CourseMemberCreateRequest,
    principal: CoursePrincipal = Depends(require_course_owner),
    service: CourseEnrollmentService = Depends(get_course_enrollment_service),
) -> CourseMemberInfo:
    try:
        return CourseMemberInfo(
            **service.add_member(
                course_id=course_id,
                user_id=payload.user_id,
                role=payload.role,
                added_by=principal.user_id,
            )
        )
    except CourseEnrollmentError as error:
        raise _enrollment_http_error(error) from error


@router.patch(
    "/{course_id}/members/{user_id}",
    response_model=CourseMemberInfo,
    summary="更新课程成员角色",
)
def update_course_member(
    course_id: str,
    user_id: str,
    payload: CourseMemberUpdateRequest,
    principal: CoursePrincipal = Depends(require_course_owner),
    service: CourseEnrollmentService = Depends(get_course_enrollment_service),
) -> CourseMemberInfo:
    try:
        return CourseMemberInfo(
            **service.update_member(
                course_id=course_id,
                user_id=user_id,
                role=payload.role,
                added_by=principal.user_id,
            )
        )
    except CourseEnrollmentError as error:
        raise _enrollment_http_error(error) from error


@router.delete("/{course_id}/members/{user_id}", summary="移除课程成员")
def remove_course_member(
    course_id: str,
    user_id: str,
    _principal: CoursePrincipal = Depends(require_course_owner),
    service: CourseEnrollmentService = Depends(get_course_enrollment_service),
):
    try:
        service.remove_member(course_id=course_id, user_id=user_id)
    except CourseEnrollmentError as error:
        raise _enrollment_http_error(error) from error
    return {"ok": True}


@router.delete("/{course_id}", summary="删除课程")
def delete_course(
    course_id: str,
    principal: CoursePrincipal = Depends(require_course_owner),
):
    mgr = _svc._get_manager()
    if not mgr.delete_course(course_id):
        raise HTTPException(status_code=500, detail="删除课程失败")
    membership_store = get_course_membership_store()
    for membership in membership_store.list_for_course(course_id):
        membership_store.delete(course_id, membership.user_id)
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
    space: Literal["mine", "course", "all"] = "all",
    sort: Literal[
        "updated_desc",
        "updated_asc",
        "name_asc",
        "name_desc",
    ] = "updated_desc",
    principal: CoursePrincipal = Depends(require_course_read),
):
    owner_user_id = principal.user_id
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
        owner_user_id=str(owner_user_id or ""),
        space=space,
        sort=sort,
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


def _validate_mind_map_node(value: Any, *, is_root: bool = False) -> None:
    if not isinstance(value, dict):
        raise ValueError("思维导图节点必须是对象")
    node_id = str(value.get("id") or "").strip()
    title = str(value.get("title") or "").strip()
    if not node_id or not title:
        label = "根节点" if is_root else "节点"
        raise ValueError(f"思维导图{label}必须包含 id 和 title")
    children = value.get("children") or []
    if not isinstance(children, list):
        raise ValueError("思维导图 children 必须是数组")
    sibling_ids: set[str] = set()
    for child in children:
        child_id = str(child.get("id") or "").strip() if isinstance(child, dict) else ""
        if child_id in sibling_ids:
            raise ValueError("思维导图同级节点 id 不能重复")
        sibling_ids.add(child_id)
        _validate_mind_map_node(child)


def _validate_material_content(material_type: str, content: Any) -> dict[str, Any]:
    normalized_type = str(material_type or "").strip()
    if normalized_type in {"report", "blog", "lesson_plan"}:
        if not isinstance(content, str):
            raise ValueError("文本资源内容必须是 Markdown 文本")
        if len(content) > 2_000_000:
            raise ValueError("资源内容过大")
        return {"content": content}

    if normalized_type not in {"quiz", "flashcard", "graph", "game", "classroom"}:
        raise ValueError("该资源暂不支持内容编辑")
    if not isinstance(content, dict):
        raise ValueError("结构化资源内容必须是对象")
    if len(json.dumps(content, ensure_ascii=False, default=str)) > 2_000_000:
        raise ValueError("资源内容过大")

    if normalized_type == "graph":
        root = content.get("root")
        if not isinstance(root, dict):
            raise ValueError("思维导图缺少根节点")
        _validate_mind_map_node(root, is_root=True)
    elif normalized_type == "quiz" and not isinstance(content.get("questions"), list):
        raise ValueError("习题内容必须包含 questions 数组")
    elif normalized_type == "flashcard" and not isinstance(content.get("cards"), list):
        raise ValueError("闪卡内容必须包含 cards 数组")
    elif normalized_type == "classroom" and not isinstance(content.get("scenes"), list):
        raise ValueError("AI 课堂内容必须包含 scenes 数组")
    elif normalized_type == "game":
        blocked = {"html", "html_url", "script", "javascript"}
        if blocked.intersection(content):
            raise ValueError("小游戏编辑不允许写入任意 HTML 或脚本")
    return {"content": content}


@router.delete("/{course_id}/materials/{material_type}/{material_id}", summary="删除课程生成资源")
def delete_course_material(
    course_id: str,
    material_type: str,
    material_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
):
    owner_user_id = principal.user_id
    mgr = _svc._get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    material = _mutable_material_or_raise(
        manager=mgr,
        course_id=course_id,
        material_type=material_type,
        material_id=material_id,
        principal=principal,
    )
    if material.get("published_from_material_id"):
        try:
            _material_publications().withdraw(
                course_id=course_id,
                material_type=material_type,
                published_material_id=material_id,
            )
        except MaterialPublicationError as error:
            raise _publication_http_error(error) from error
        return {"ok": True}
    if not mgr.delete_generated_material(
        course_id,
        material_type,
        material_id,
        owner_user_id=str(owner_user_id or ""),
    ):
        raise HTTPException(status_code=404, detail="资源不存在或删除失败")
    return {"ok": True}


@router.post("/{course_id}/materials/{material_type}/{material_id}/pin", summary="置顶课程生成资源")
def pin_course_material(
    course_id: str,
    material_type: str,
    material_id: str,
    payload: PinMaterialRequest,
    principal: CoursePrincipal = Depends(require_course_read),
):
    owner_user_id = principal.user_id
    mgr = _svc._get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    _mutable_material_or_raise(
        manager=mgr,
        course_id=course_id,
        material_type=material_type,
        material_id=material_id,
        principal=principal,
    )
    if not mgr.pin_generated_material(
        course_id,
        material_type,
        material_id,
        payload.is_pinned,
        owner_user_id=str(owner_user_id or ""),
    ):
        raise HTTPException(status_code=404, detail="资源不存在或置顶失败")

    updated = mgr.get_generated_material(
        course_id,
        material_type,
        material_id,
        owner_user_id=str(owner_user_id or ""),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="资源不存在")

    updated["material_id"] = material_id
    updated["material_type"] = updated.get("material_type") or material_type
    return updated


@router.get(
    "/{course_id}/materials/{material_type}/{material_id}",
    summary="获取课程生成资源详情",
)
def get_course_material(
    course_id: str,
    material_type: str,
    material_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
):
    material = _svc._get_manager().get_generated_material(
        course_id,
        material_type,
        material_id,
        owner_user_id=principal.user_id,
    )
    if material is None:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return material


@router.patch(
    "/{course_id}/materials/{material_type}/{material_id}",
    summary="重命名课程生成资源",
)
def rename_course_material(
    course_id: str,
    material_type: str,
    material_id: str,
    payload: RenameMaterialRequest,
    principal: CoursePrincipal = Depends(require_course_read),
):
    manager = _svc._get_manager()
    owner = principal.user_id
    _mutable_material_or_raise(
        manager=manager,
        course_id=course_id,
        material_type=material_type,
        material_id=material_id,
        principal=principal,
    )
    if not manager.rename_generated_material(
        course_id,
        material_type,
        material_id,
        payload.title,
        owner_user_id=owner,
    ):
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return manager.get_generated_material(
        course_id,
        material_type,
        material_id,
        owner_user_id=owner,
    )


@router.patch(
    "/{course_id}/materials/{material_type}/{material_id}/content",
    summary="保存课程生成资源内容",
)
def update_course_material_content(
    course_id: str,
    material_type: str,
    material_id: str,
    payload: MaterialContentUpdateRequest,
    principal: CoursePrincipal = Depends(require_course_read),
):
    manager = _svc._get_manager()
    owner = principal.user_id
    _mutable_material_or_raise(
        manager=manager,
        course_id=course_id,
        material_type=material_type,
        material_id=material_id,
        principal=principal,
    )
    try:
        updates = _validate_material_content(material_type, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    content = updates["content"]
    if material_type == "quiz":
        updates["questions"] = list(content.get("questions") or [])
    elif material_type == "flashcard":
        updates["flashcards"] = list(content.get("cards") or [])
    elif material_type == "classroom":
        updates["scenes"] = list(content.get("scenes") or [])
        updates["scenes_count"] = len(updates["scenes"])
    updated = manager.update_generated_material_metadata(
        course_id,
        material_type,
        material_id,
        updates,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return manager.get_generated_material(
        course_id,
        material_type,
        material_id,
        owner_user_id=owner,
    ) or updated


@router.post(
    "/{course_id}/materials/{material_type}/{material_id}/publish",
    response_model=MaterialPublicationResponse,
    summary="发布个人资源到课程",
)
def publish_course_material(
    course_id: str,
    material_type: str,
    material_id: str,
    principal: CoursePrincipal = Depends(require_course_manage_resources),
) -> MaterialPublicationResponse:
    if not can_manage_course_resources(principal):
        raise _material_http_error(
            403, "MATERIAL_PUBLISH_FORBIDDEN", "无权发布课程资源"
        )
    try:
        result = _material_publications().publish(
            course_id=course_id,
            material_type=material_type,
            material_id=material_id,
            owner_user_id=principal.user_id,
        )
    except MaterialPublicationError as error:
        raise _publication_http_error(error) from error
    return MaterialPublicationResponse(
        action=result.action,
        source_material_id=result.source_material_id,
        material=result.material,
    )


@router.delete(
    "/{course_id}/materials/{material_type}/{material_id}/publication",
    summary="撤回课程共享资源",
)
def withdraw_course_material(
    course_id: str,
    material_type: str,
    material_id: str,
    principal: CoursePrincipal = Depends(require_course_manage_resources),
):
    manager = _svc._get_manager()
    _mutable_material_or_raise(
        manager=manager,
        course_id=course_id,
        material_type=material_type,
        material_id=material_id,
        principal=principal,
    )
    try:
        _material_publications().withdraw(
            course_id=course_id,
            material_type=material_type,
            published_material_id=material_id,
        )
    except MaterialPublicationError as error:
        raise _publication_http_error(error) from error
    return {"ok": True}


@router.get(
    "/{course_id}/materials/{material_type}/{material_id}/integrity",
    summary="检查课程生成资源完整性",
)
def check_course_material_integrity(
    course_id: str,
    material_type: str,
    material_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
):
    result = _svc._get_manager().check_generated_material_integrity(
        course_id,
        material_type,
        material_id,
        owner_user_id=principal.user_id,
    )
    if result.get("missing") == ["manifest"]:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return result


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
    principal: CoursePrincipal = Depends(require_course_read),
):
    owner_user_id = principal.user_id
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
    index = [item for item in index if item.get("display_in_library") is not False]
    # A viewer must only observe the atomically published knowledge-base
    # version. Owners/editors may inspect staged or failed records for
    # diagnostics, while students never see a blocked build leaking through
    # the document list before its graph version is published.
    if principal.course_role == "viewer" and library_type == LIBRARY_TYPE_COURSE:
        index = [
            item
            for item in index
            if str(item.get("status") or "received") == "ready"
        ]
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
    "/{course_id}/knowledge-builds",
    status_code=status.HTTP_201_CREATED,
    summary="创建课程知识库构建草案",
)
def create_knowledge_base_build_draft(
    course_id: str,
    payload: CourseKnowledgeBuildDraftCreateRequest,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    mgr = _svc._get_manager()
    course = mgr.get_course_info(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    course_snapshot = dict(course)
    course_snapshot["id"] = course_id
    plan = {
        "course_id": course_id,
        "course_snapshot": course_snapshot,
        "config": payload.config.model_dump(mode="json"),
        "textbooks": [],
        "graph_draft": None,
        "topics": [],
        "source_candidates": [],
        "warnings": [],
    }
    try:
        return get_postgres_knowledge_repository().create_build_draft(
            course_id=course_id,
            triggered_by=principal.user_id,
            plan=plan,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"知识库构建草案暂时无法保存：{exc}",
        ) from exc


def _get_course_knowledge_build_or_404(course_id: str, build_id: str):
    result = get_postgres_knowledge_repository().get_build(build_id)
    if result is None or str(result.get("library_id") or "") != course_id:
        raise HTTPException(status_code=404, detail="知识库构建记录不存在")
    return result


def _raise_build_revision_conflict(exc: KnowledgeBuildRevisionConflict) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "KNOWLEDGE_BUILD_REVISION_CONFLICT",
            "message": str(exc),
        },
    ) from exc


def _raise_textbook_input_error(exc: CourseKnowledgeTextbookInputError) -> None:
    status_code = (
        status.HTTP_409_CONFLICT
        if exc.code == "TEXTBOOK_DUPLICATE"
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    raise HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


@router.patch(
    "/{course_id}/knowledge-builds/{build_id}",
    summary="更新课程知识库构建配置",
)
def update_knowledge_base_build_draft(
    course_id: str,
    build_id: str,
    payload: CourseKnowledgeBuildDraftUpdateRequest,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    del principal
    _get_course_knowledge_build_or_404(course_id, build_id)
    try:
        return get_postgres_knowledge_repository().update_build_draft(
            build_id,
            expected_revision=payload.expected_revision,
            changes={"config": payload.config.model_dump(mode="json")},
            phase="draft_config",
        )
    except KnowledgeBuildRevisionConflict as exc:
        _raise_build_revision_conflict(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{course_id}/knowledge-builds/{build_id}/textbooks",
    status_code=status.HTTP_202_ACCEPTED,
    summary="上传并暂存课程知识库构建教材",
)
async def upload_knowledge_base_build_textbook(
    course_id: str,
    build_id: str,
    expected_revision: int = Form(..., ge=1),
    file: UploadFile = File(..., description="PDF、DOCX、TXT 或 Markdown 教材"),
    principal: CoursePrincipal = Depends(require_course_generate),
):
    _get_course_knowledge_build_or_404(course_id, build_id)
    if not file.filename:
        raise HTTPException(status_code=422, detail="教材文件名不能为空")
    try:
        updated, textbook = stage_course_knowledge_textbook(
            manager=_svc._get_manager(),
            course_id=course_id,
            build_id=build_id,
            owner_user_id=principal.user_id,
            expected_revision=expected_revision,
            filename=file.filename,
            file_bytes=await file.read(),
        )
        job = submit_course_knowledge_textbook_parse_job(
            course_id=course_id,
            owner_user_id=principal.user_id,
            build_id=build_id,
            textbook_id=textbook["textbook_id"],
        )
    except KnowledgeBuildRevisionConflict as exc:
        _raise_build_revision_conflict(exc)
    except CourseKnowledgeTextbookInputError as exc:
        _raise_textbook_input_error(exc)
    return {
        "build": updated,
        "textbook": textbook,
        "job": job.model_dump(mode="json"),
    }


@router.post(
    "/{course_id}/knowledge-builds/{build_id}/textbooks/{textbook_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="重试解析知识库构建教材",
)
def retry_knowledge_base_build_textbook(
    course_id: str,
    build_id: str,
    textbook_id: str,
    payload: CourseKnowledgeTextbookMutationRequest,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    _get_course_knowledge_build_or_404(course_id, build_id)
    try:
        updated = retry_course_knowledge_textbook(
            course_id=course_id,
            build_id=build_id,
            textbook_id=textbook_id,
            expected_revision=payload.expected_revision,
        )
        job = submit_course_knowledge_textbook_parse_job(
            course_id=course_id,
            owner_user_id=principal.user_id,
            build_id=build_id,
            textbook_id=textbook_id,
        )
    except KnowledgeBuildRevisionConflict as exc:
        _raise_build_revision_conflict(exc)
    except CourseKnowledgeTextbookInputError as exc:
        _raise_textbook_input_error(exc)
    return {"build": updated, "job": job.model_dump(mode="json")}


@router.delete(
    "/{course_id}/knowledge-builds/{build_id}/textbooks/{textbook_id}",
    summary="从构建草案移除教材输入",
)
def delete_knowledge_base_build_textbook(
    course_id: str,
    build_id: str,
    textbook_id: str,
    payload: CourseKnowledgeTextbookMutationRequest,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    del principal
    _get_course_knowledge_build_or_404(course_id, build_id)
    try:
        return remove_course_knowledge_textbook(
            course_id=course_id,
            build_id=build_id,
            textbook_id=textbook_id,
            expected_revision=payload.expected_revision,
        )
    except KnowledgeBuildRevisionConflict as exc:
        _raise_build_revision_conflict(exc)
    except CourseKnowledgeTextbookInputError as exc:
        _raise_textbook_input_error(exc)


@router.put(
    "/{course_id}/knowledge-builds/{build_id}/graph",
    summary="保存待确认的课程知识图谱",
)
def update_knowledge_base_graph_draft(
    course_id: str,
    build_id: str,
    payload: CourseKnowledgeGraphDraftUpdateRequest,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    build = _get_course_knowledge_build_or_404(course_id, build_id)
    graph = copy.deepcopy(payload.root)
    issues, metrics = validate_graph_draft_for_build(build, graph)
    if issues:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "GRAPH_SCHEMA_INVALID",
                "message": "知识图谱草案未通过结构校验",
                "issues": issues,
            },
        )
    graph.setdefault("data", {}).update(
        {
            "validation": {"status": "passed", **metrics},
            "edited_at": datetime.now().astimezone().isoformat(),
            "edited_by": principal.user_id,
        }
    )
    try:
        return get_postgres_knowledge_repository().update_build_draft(
            build_id,
            expected_revision=payload.expected_revision,
            changes={"graph_draft": graph},
            phase="graph_review",
        )
    except KnowledgeBuildRevisionConflict as exc:
        _raise_build_revision_conflict(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{course_id}/knowledge-builds/{build_id}/graph/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="调用模型生成课程知识图谱草案",
)
def generate_knowledge_base_graph_draft(
    course_id: str,
    build_id: str,
    payload: CourseKnowledgeGraphGenerateRequest,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    _get_course_knowledge_build_or_404(course_id, build_id)
    try:
        job = submit_course_knowledge_graph_generation_job(
            course_id=course_id,
            owner_user_id=principal.user_id,
            build_id=build_id,
            expected_revision=payload.expected_revision,
            target_module_id=payload.target_module_id,
        )
    except KnowledgeBuildRevisionConflict as exc:
        _raise_build_revision_conflict(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return job.model_dump(mode="json")


@router.post(
    "/{course_id}/knowledge-builds/{build_id}/graph/confirm",
    summary="确认课程知识图谱并解锁正式构建",
)
def confirm_knowledge_base_graph_draft(
    course_id: str,
    build_id: str,
    payload: CourseKnowledgeGraphConfirmRequest,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    build = _get_course_knowledge_build_or_404(course_id, build_id)
    graph = build.get("graph_draft") or {}
    issues, _metrics = validate_graph_draft_for_build(build, graph)
    if issues:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "GRAPH_SCHEMA_INVALID",
                "message": "知识图谱草案未通过结构校验，不能确认",
                "issues": issues,
            },
        )
    try:
        return get_postgres_knowledge_repository().confirm_build_graph(
            build_id,
            expected_revision=payload.expected_revision,
            confirmed_by=principal.user_id,
        )
    except KnowledgeBuildRevisionConflict as exc:
        _raise_build_revision_conflict(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{course_id}/knowledge-builds/preview",
    status_code=status.HTTP_201_CREATED,
    summary="根据课程元数据生成并保存知识库构建计划",
)
def preview_knowledge_base_build(
    course_id: str,
    payload: CourseKnowledgeBuildPreviewRequest,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    del payload
    result = create_knowledge_base_build_draft(
        course_id,
        CourseKnowledgeBuildDraftCreateRequest(),
        principal,
    )
    return {
        **result,
        "deprecation": {
            "deprecated": True,
            "replacement": f"/api/courses/{course_id}/knowledge-builds",
            "message": "旧预览入口已改为只创建草案，不再搜索或自动启动构建",
        },
    }


@router.get(
    "/{course_id}/knowledge-builds/{build_id}",
    summary="读取知识库构建计划和状态",
)
def get_knowledge_base_build(
    course_id: str,
    build_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
):
    del principal
    return _get_course_knowledge_build_or_404(course_id, build_id)


@router.post(
    "/{course_id}/knowledge-builds/{build_id}/start",
    status_code=status.HTTP_202_ACCEPTED,
    summary="确认审核来源并启动课程知识库构建",
)
def start_knowledge_base_build(
    course_id: str,
    build_id: str,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    build = _get_course_knowledge_build_or_404(course_id, build_id)
    revision = int(build.get("revision") or 0)
    if (
        not build.get("graph_confirmed_at")
        or int(build.get("confirmed_graph_revision") or 0) != revision
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "GRAPH_CONFIRMATION_REQUIRED",
                "message": "请先确认当前版本的知识图谱，再启动正式构建",
            },
        )
    try:
        job = submit_course_knowledge_plan_build_job(
            course_id=course_id,
            owner_user_id=principal.user_id,
            build_id=build_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return job.model_dump(mode="json")


@router.post(
    "/{course_id}/knowledge-builds/{build_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="从稳定检查点重试失败或阻塞的课程知识库构建",
)
def retry_knowledge_base_build(
    course_id: str,
    build_id: str,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    build = _get_course_knowledge_build_or_404(course_id, build_id)
    if build.get("status") not in {"blocked", "failed"}:
        raise HTTPException(status_code=422, detail="只有失败或阻塞的构建可以重试")
    try:
        job = submit_course_knowledge_plan_build_job(
            course_id=course_id,
            owner_user_id=principal.user_id,
            build_id=build_id,
            retry=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return job.model_dump(mode="json")


@router.get(
    "/{course_id}/knowledge-base/versions",
    summary="列出已发布的课程知识图谱版本",
)
def list_knowledge_base_versions(
    course_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
):
    del principal
    return get_postgres_knowledge_repository().list_graph_versions(course_id)


@router.post(
    "/{course_id}/knowledge-base/versions/{version}/rollback",
    summary="将课程知识图谱回滚为指定版本",
)
def rollback_knowledge_base_version(
    course_id: str,
    version: int,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    del principal
    try:
        return get_postgres_knowledge_repository().rollback_graph(course_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="知识图谱版本不存在") from exc


@router.post(
    "/{course_id}/knowledge-base/build-from-open-textbook",
    status_code=status.HTTP_202_ACCEPTED,
    summary="从已审核开放教材构建中文课程知识库",
)
def build_knowledge_base_from_open_textbook(
    course_id: str,
    payload: CourseKnowledgeBuildRequest,
    principal: CoursePrincipal = Depends(require_course_generate),
):
    mgr = _svc._get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    try:
        job = submit_course_knowledge_build_job(
            course_id=course_id,
            owner_user_id=principal.user_id,
            source_id=payload.source_id,
            max_pages=payload.max_pages,
            clean_placeholders=payload.clean_placeholders,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return job.model_dump(mode="json")


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
    principal: CoursePrincipal = Depends(require_course_edit),
):
    owner_user_id = principal.user_id
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
    principal: CoursePrincipal = Depends(require_course_generate),
):
    del file, principal
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "LEGACY_TEXTBOOK_IMPORT_RETIRED",
            "message": "旧教材导入会直接覆盖图谱，现已停用；请在知识库构建方案中上传教材",
            "replacement": f"/api/courses/{course_id}/knowledge-builds/{{build_id}}/textbooks",
        },
    )


@router.post(
    "/{course_id}/knowledge-base/documents/add-from-rag",
    response_model=KnowledgeBaseDocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="把 RAG 文档加入课程知识库",
)
async def add_rag_document_to_course_kb(
    course_id: str,
    request: AddRAGDocumentRequest,
    principal: CoursePrincipal = Depends(require_course_edit),
):
    mgr = _svc._get_manager()
    rag_system = get_rag_system()
    owner = principal.user_id

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
    principal: CoursePrincipal = Depends(require_course_read),
):
    owner = principal.user_id
    document = _knowledge.get_document(
        _svc._get_manager(),
        course_id,
        document_id,
        owner_user_id=owner,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    return _knowledge_document_model(document, course_id)


def _knowledge_document_collection_root(course_dir: Path, file_path: Path) -> Path:
    """Return the versioned document collection containing a knowledge file."""
    knowledge_base_root = (course_dir / "knowledge_base").resolve()
    try:
        relative_file = file_path.relative_to(knowledge_base_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="文档路径不合法") from exc
    if not relative_file.parts or not re.fullmatch(
        r"documents(?:-[A-Za-z0-9._-]+)?",
        relative_file.parts[0],
    ):
        raise HTTPException(status_code=400, detail="文档路径不合法")
    return (knowledge_base_root / relative_file.parts[0]).resolve()


@router.get(
    "/{course_id}/knowledge-base/documents/{document_id}/content",
    response_model=KnowledgeBaseDocumentContent,
    summary="读取课程知识库文档正文",
)
def get_knowledge_base_document_content(
    course_id: str,
    document_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
):
    mgr = _svc._get_manager()
    document = _knowledge.get_document(
        mgr,
        course_id,
        document_id,
        owner_user_id=principal.user_id,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")

    relative_path = str(document.get("path") or "").replace("\\", "/").strip()
    if not relative_path:
        raise HTTPException(status_code=404, detail="文档没有可读取的正文文件")
    course_dir = mgr.get_course_dir(course_id).resolve()
    file_path = (course_dir / relative_path).resolve()
    documents_root = _knowledge_document_collection_root(course_dir, file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="文档正文文件不存在")

    if file_path.suffix.casefold() not in {
        ".md", ".markdown", ".txt", ".html", ".htm", ".json", ".csv", ".py",
    }:
        raise HTTPException(status_code=415, detail="该文件类型暂不支持直接预览正文")
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = file_path.read_text(encoding="utf-8", errors="replace")

    def media_url(raw_source: str) -> str:
        source = raw_source.strip().strip("<>")
        if not source or re.match(r"^(?:https?:|data:|blob:|/api/)", source, re.I):
            return raw_source
        clean_source = source.split("#", 1)[0].split("?", 1)[0]
        candidate = (file_path.parent / clean_source).resolve()
        try:
            relative_asset = candidate.relative_to(documents_root)
        except ValueError:
            return raw_source
        if not candidate.is_file():
            return raw_source
        encoded = quote(relative_asset.as_posix(), safe="")
        return (
            f"/api/courses/{course_id}/knowledge-base/documents/"
            f"{document_id}/media?path={encoded}"
        )

    content = re.sub(
        r"(!\[[^\]]*\]\()(?P<src><[^>]+>|[^)\s]+)",
        lambda match: f"{match.group(1)}{media_url(match.group('src'))}",
        content,
    )
    content = re.sub(
        r"(?P<prefix><img\b[^>]*?\bsrc=[\"'])(?P<src>[^\"']+)",
        lambda match: f"{match.group('prefix')}{media_url(match.group('src'))}",
        content,
        flags=re.I,
    )

    chunk = {
        "id": 0,
        "content": content,
        "page": 1,
        "metadata": {
            "document_id": document_id,
            "scope_id": document.get("scope_id"),
            "source_url": document.get("source_url") or document.get("url"),
        },
    }
    return KnowledgeBaseDocumentContent(
        document_id=document_id,
        file_path=document_id,
        file_name=str(document.get("source_title") or document.get("filename") or file_path.name),
        content=content,
        chunks=[chunk] if content.strip() else [],
        total_chunks=1 if content.strip() else 0,
    )


@router.get(
    "/{course_id}/knowledge-base/documents/{document_id}/media",
    response_class=FileResponse,
    summary="读取课程知识库文档内的图片或视频",
)
def get_knowledge_base_document_media(
    course_id: str,
    document_id: str,
    path: str,
    principal: CoursePrincipal = Depends(require_course_read),
):
    mgr = _svc._get_manager()
    document = _knowledge.get_document(
        mgr,
        course_id,
        document_id,
        owner_user_id=principal.user_id,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")

    relative_path = str(document.get("path") or "").replace("\\", "/").strip()
    if not relative_path:
        raise HTTPException(status_code=404, detail="文档没有可读取的正文文件")
    course_dir = mgr.get_course_dir(course_id).resolve()
    document_file = (course_dir / relative_path).resolve()
    documents_root = _knowledge_document_collection_root(course_dir, document_file)
    media_path = (documents_root / path.replace("\\", "/")).resolve()
    try:
        media_path.relative_to(documents_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="媒体路径不合法") from exc
    if not media_path.is_file():
        raise HTTPException(status_code=404, detail="媒体文件不存在")

    media_type, _ = mimetypes.guess_type(media_path.name)
    if not media_type or not (
        media_type.startswith("image/") or media_type.startswith("video/")
    ):
        raise HTTPException(status_code=415, detail="不支持的媒体类型")
    if media_type == "image/svg+xml":
        raise HTTPException(status_code=415, detail="SVG 请在入库时转换为安全的位图格式")

    return FileResponse(
        path=media_path,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


def _submit_knowledge_document_job(
    *,
    course_id: str,
    document_id: str,
    principal: CoursePrincipal,
    force_reindex: bool,
):
    owner = principal.user_id
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
    principal: CoursePrincipal = Depends(require_course_generate),
):
    document = _knowledge.get_document(
        _svc._get_manager(),
        course_id,
        document_id,
        owner_user_id=principal.user_id,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    if document.get("status") != "failed":
        raise HTTPException(status_code=409, detail="仅失败文档可以重试")
    return _submit_knowledge_document_job(
        course_id=course_id,
        document_id=document_id,
        principal=principal,
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
    principal: CoursePrincipal = Depends(require_course_generate),
):
    return _submit_knowledge_document_job(
        course_id=course_id,
        document_id=document_id,
        principal=principal,
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
    principal: CoursePrincipal = Depends(require_course_read),
):
    try:
        return _knowledge.test_retrieval(
            manager=_svc._get_manager(),
            rag_system=get_rag_system(),
            course_id=course_id,
            document_id=document_id,
            owner_user_id=principal.user_id,
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
    principal: CoursePrincipal = Depends(require_course_edit),
):
    mgr = _svc._get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    owner = principal.user_id
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
    principal: CoursePrincipal = Depends(require_course_read),
):
    _ = principal
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
    principal: CoursePrincipal = Depends(require_course_read),
):
    _ = principal
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
    principal: CoursePrincipal = Depends(require_course_generate),
):
    _ = principal
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
    principal: CoursePrincipal = Depends(require_course_edit),
):
    _ = principal
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
    principal: CoursePrincipal = Depends(require_course_read),
):
    """提交即返回（202 + queued 状态的 edu_job），真正的生成/校验/落库在
    后台任务里跑（真实实测一份 9-scene 课件约 20 分钟，不适合同步 await）。
    前端轮询 `GET /api/jobs/{edu_job_id}` 直到 `done`（SPEC-05 §3）。
    """
    mgr = _svc._get_manager()
    try:
        require_personal_tool(principal.system_role, "classroom")
    except PersonalToolAccessDenied as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PERSONAL_TOOL_ACCESS_DENIED",
                "tool_id": exc.tool_id,
            },
        ) from exc
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    from app.services.generation_task_handlers import (
        build_default_generation_source_resolver,
    )

    try:
        build_default_generation_source_resolver(mgr).validate(
            course_id,
            payload.source_mode,
            payload.selected_doc_ids,
            owner=principal.user_id,
        )
    except GenerationSourceError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    owner = principal.user_id
    job = await submit_classroom_generation_job(
        course_id=course_id,
        requirement=payload.requirement,
        owner=owner,
        course_storage_manager=mgr,
        enable_web_search=payload.enable_web_search,
        enable_tts=payload.enable_tts,
        source_mode=payload.source_mode,
        selected_doc_ids=payload.selected_doc_ids,
        topic=payload.topic,
        audience=payload.audience,
        scene_count=payload.scene_count,
        objectives=payload.objectives,
        duration_minutes=payload.duration_minutes,
        teaching_style=payload.teaching_style,
        voice=payload.voice,
        include_visuals=payload.include_visuals,
    )
    return job


@router.get("/{course_id}/classrooms/{classroom_id}", summary="读取一份已落库的课件")
def get_classroom(
    course_id: str,
    classroom_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
):
    mgr = _svc._get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    material = mgr.get_generated_material(
        course_id,
        "classroom",
        classroom_id,
        owner_user_id=principal.user_id,
    )
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
    principal: CoursePrincipal = Depends(require_course_read),
):
    mgr = _svc._get_manager()
    try:
        require_personal_tool(principal.system_role, "classroom")
    except PersonalToolAccessDenied as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PERSONAL_TOOL_ACCESS_DENIED",
                "tool_id": exc.tool_id,
            },
        ) from exc
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    if mgr.get_generated_material(
        course_id,
        "classroom",
        classroom_id,
        owner_user_id=principal.user_id,
    ) is None:
        raise HTTPException(status_code=404, detail="课件不存在")

    return await submit_classroom_video_export_job(
        course_id=course_id,
        classroom_id=classroom_id,
        auth_token="",
        current_user={
            "username": principal.user_id,
            "role": principal.system_role,
        },
        owner=principal.user_id,
        course_storage_manager=mgr,
    )


@router.get("/{course_id}/classrooms", summary="列出课程下已落库的课件")
def list_classrooms(
    course_id: str,
    space: Literal["mine", "course"] = "mine",
    principal: CoursePrincipal = Depends(require_course_read),
):
    mgr = _svc._get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    return mgr.list_generated_materials(
        course_id,
        "classroom",
        owner_user_id=principal.user_id,
        space=space,
    )


@router.get(
    "/{course_id}/classrooms/{classroom_id}/audio/{filename}",
    response_class=FileResponse,
    summary="读取课件配音文件（D1 迁移落盘，见 classroom_media.migrate_classroom_speech_audio）",
)
def get_classroom_audio(
    course_id: str,
    classroom_id: str,
    filename: str,
    principal: CoursePrincipal = Depends(require_course_read),
):
    mgr = _svc._get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    if mgr.get_generated_material(
        course_id,
        "classroom",
        classroom_id,
        owner_user_id=principal.user_id,
    ) is None:
        raise HTTPException(status_code=404, detail="课件不存在或无权访问")

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
    principal: CoursePrincipal = Depends(require_course_read),
):
    media_type = VIDEO_ARTIFACT_MEDIA_TYPES.get(filename)
    if media_type is None:
        raise HTTPException(status_code=404, detail="视频导出文件不存在")
    mgr = _svc._get_manager()
    if mgr.get_generated_material(
        course_id,
        "classroom",
        classroom_id,
        owner_user_id=principal.user_id,
    ) is None:
        raise HTTPException(status_code=404, detail="课件不存在或无权访问")
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
