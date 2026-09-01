"""Authenticated owner-only HTTP API for the global personal knowledge base."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.api.course_dependencies import (
    get_course_access_service,
    require_course_capability,
)
from app.auth import get_current_user
from app.services.course_access import CourseAccessService
from app.services.personal_knowledge_service import (
    PersonalKnowledgeError,
    PersonalKnowledgeNotFound,
    PersonalKnowledgeService,
    PersonalKnowledgeValidationError,
)
from modules.rag_v2.api import get_rag_system


router = APIRouter(prefix="/api/personal-knowledge", tags=["personal-knowledge"])


class PersonalKnowledgeRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


def get_personal_knowledge_service() -> PersonalKnowledgeService:
    return PersonalKnowledgeService()


def _owner(current_user: dict) -> str:
    owner = str(current_user.get("username") or "").strip()
    if not owner:
        raise HTTPException(status_code=401, detail="未登录")
    return owner


def _public_document(record: dict) -> dict:
    return {
        "id": str(record.get("id") or ""),
        "name": str(
            record.get("display_name")
            or record.get("filename")
            or "未命名文档"
        ),
        "display_name": str(
            record.get("display_name")
            or record.get("filename")
            or "未命名文档"
        ),
        "type": "file",
        "course_context_id": (
            str(record.get("course_context_id") or "").strip() or None
        ),
        "library_type": "personal",
        "created_at": str(
            record.get("uploaded_at")
            or datetime.now(timezone.utc).isoformat()
        ),
        "updated_at": record.get("updated_at"),
        "status": str(record.get("status") or "received"),
        "active_index_version": record.get("active_index_version"),
        "pending_index_version": record.get("pending_index_version"),
        "page_count": int(record.get("page_count") or 0),
        "chunk_count": int(record.get("chunk_count") or 0),
        "failed_units": int(record.get("failed_units") or 0),
        "parser_name": record.get("parser_name"),
        "embedding_profile_id": record.get("embedding_profile_id"),
        "indexed_at": record.get("indexed_at"),
        "last_job_id": record.get("last_job_id"),
        "error_code": record.get("error_code"),
        "error_message": record.get("error_message"),
    }


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PersonalKnowledgeNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, PersonalKnowledgeValidationError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail="个人知识库操作失败")


@router.get("/documents")
def list_personal_documents(
    document_status: str | None = None,
    search: str | None = None,
    sort: Literal["created_desc", "created_asc", "name_asc", "name_desc"] = "created_desc",
    limit: int = 200,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    service: PersonalKnowledgeService = Depends(get_personal_knowledge_service),
):
    owner = _owner(current_user)
    records = service.list_documents(owner_user_id=owner)
    if document_status:
        records = [
            item
            for item in records
            if str(item.get("status") or "received") == document_status
        ]
    query = str(search or "").strip().casefold()
    if query:
        records = [
            item
            for item in records
            if query
            in str(
                item.get("display_name") or item.get("filename") or ""
            ).casefold()
        ]
    if sort in {"name_asc", "name_desc"}:
        records = sorted(
            records,
            key=lambda item: str(
                item.get("display_name") or item.get("filename") or ""
            ).casefold(),
            reverse=sort == "name_desc",
        )
    elif sort == "created_asc":
        records = list(reversed(records))
    start = max(0, offset)
    end = start + max(0, min(limit, 500))
    return [_public_document(item) for item in records[start:end]]


@router.post(
    "/documents",
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_personal_document(
    file: UploadFile = File(...),
    course_context_id: str | None = Form(default=None),
    current_user: dict = Depends(get_current_user),
    access_service: CourseAccessService = Depends(get_course_access_service),
    service: PersonalKnowledgeService = Depends(get_personal_knowledge_service),
):
    owner = _owner(current_user)
    context_id = str(course_context_id or "").strip() or None
    if context_id:
        require_course_capability(
            context_id,
            current_user,
            "read",
            access_service,
        )
    try:
        document = service.create_document(
            owner_user_id=owner,
            filename=str(file.filename or ""),
            file_data=await file.read(),
            course_context_id=context_id,
        )
        job = service.submit_index(
            owner_user_id=owner,
            document_id=str(document.get("id") or ""),
            rag_system=get_rag_system(),
        )
    except PersonalKnowledgeError as exc:
        raise _http_error(exc) from exc
    return {"document": _public_document(document), "job": job}


@router.get("/documents/{document_id}")
def get_personal_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    service: PersonalKnowledgeService = Depends(get_personal_knowledge_service),
):
    try:
        return _public_document(
            service.get_document(
                owner_user_id=_owner(current_user),
                document_id=document_id,
            )
        )
    except PersonalKnowledgeError as exc:
        raise _http_error(exc) from exc


@router.get("/documents/{document_id}/content")
def get_personal_document_content(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    service: PersonalKnowledgeService = Depends(get_personal_knowledge_service),
):
    try:
        return service.read_content(
            owner_user_id=_owner(current_user),
            document_id=document_id,
        )
    except PersonalKnowledgeError as exc:
        raise _http_error(exc) from exc


@router.patch("/documents/{document_id}")
def rename_personal_document(
    document_id: str,
    payload: PersonalKnowledgeRenameRequest,
    current_user: dict = Depends(get_current_user),
    service: PersonalKnowledgeService = Depends(get_personal_knowledge_service),
):
    try:
        return _public_document(
            service.rename_document(
                owner_user_id=_owner(current_user),
                document_id=document_id,
                name=payload.name,
            )
        )
    except PersonalKnowledgeError as exc:
        raise _http_error(exc) from exc


@router.delete("/documents/{document_id}")
def delete_personal_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    service: PersonalKnowledgeService = Depends(get_personal_knowledge_service),
):
    owner = _owner(current_user)
    try:
        document = service.get_document(
            owner_user_id=owner,
            document_id=document_id,
        )
        service.delete_document(
            owner_user_id=owner,
            document_id=document_id,
            rag_system=(get_rag_system() if document.get("rag_index_key") else None),
        )
    except PersonalKnowledgeError as exc:
        raise _http_error(exc) from exc
    return {"message": "文档已删除"}


@router.post(
    "/documents/{document_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_personal_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    service: PersonalKnowledgeService = Depends(get_personal_knowledge_service),
):
    owner = _owner(current_user)
    try:
        document = service.get_document(
            owner_user_id=owner,
            document_id=document_id,
        )
        if document.get("status") != "failed":
            raise HTTPException(status_code=409, detail="仅失败文档可以重试")
        return service.submit_index(
            owner_user_id=owner,
            document_id=document_id,
            rag_system=get_rag_system(),
        )
    except HTTPException:
        raise
    except PersonalKnowledgeError as exc:
        raise _http_error(exc) from exc

