"""Authorized API boundary for full-resource study guide and practice Q&A."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.course_dependencies import require_course_read
from app.schemas.resource_qa import (
    ResourceQaSessionResponse,
    ResourceQaTurnRequest,
    ResourceQaTurnSubmissionResponse,
)
from app.services.classroom_qa_store import resource_session_id
from app.services.course_access import CoursePrincipal
from app.services.resource_qa_service import ResourceQaError, ResourceQaService


ResourceKind = Literal["study_guide", "practice"]

router = APIRouter(prefix="/api/courses", tags=["resource-qa"])
_service: ResourceQaService | None = None


def get_resource_qa_service() -> ResourceQaService:
    global _service
    if _service is None:
        _service = ResourceQaService()
    return _service


@router.get(
    "/{course_id}/resources/{resource_kind}/{resource_id}/qa/session",
    response_model=ResourceQaSessionResponse,
)
async def get_resource_qa_session(
    course_id: str,
    resource_kind: ResourceKind,
    resource_id: str,
    resource_version: int = Query(ge=1),
    principal: CoursePrincipal = Depends(require_course_read),
    service: ResourceQaService = Depends(get_resource_qa_service),
):
    try:
        return await service.get_session(
            course_id=course_id,
            resource_kind=resource_kind,
            resource_id=resource_id,
            resource_version=resource_version,
            owner_user_id=principal.user_id,
            course_role=principal.course_role,
        )
    except ResourceQaError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/{course_id}/resources/{resource_kind}/{resource_id}/qa/turns",
    response_model=ResourceQaTurnSubmissionResponse,
)
async def submit_resource_qa_turn(
    course_id: str,
    resource_kind: ResourceKind,
    resource_id: str,
    request: ResourceQaTurnRequest,
    principal: CoursePrincipal = Depends(require_course_read),
    service: ResourceQaService = Depends(get_resource_qa_service),
):
    try:
        return await service.submit_turn(
            course_id=course_id,
            resource_kind=resource_kind,
            resource_id=resource_id,
            resource_version=request.resource_version,
            owner_user_id=principal.user_id,
            course_role=principal.course_role,
            request=request,
        )
    except ResourceQaError as exc:
        raise _http_error(exc) from exc


@router.get(
    "/{course_id}/resources/{resource_kind}/{resource_id}/qa/"
    "sessions/{session_id}/audio/{filename}"
)
async def get_resource_qa_audio(
    course_id: str,
    resource_kind: ResourceKind,
    resource_id: str,
    session_id: str,
    filename: str,
    resource_version: int = Query(ge=1),
    principal: CoursePrincipal = Depends(require_course_read),
    service: ResourceQaService = Depends(get_resource_qa_service),
):
    not_found = HTTPException(status_code=404, detail="Not found")
    try:
        public_session = await service.get_session(
            course_id=course_id,
            resource_kind=resource_kind,
            resource_id=resource_id,
            resource_version=resource_version,
            owner_user_id=principal.user_id,
            course_role=principal.course_role,
        )
    except ResourceQaError as exc:
        if exc.status_code == 404:
            raise not_found from exc
        raise _http_error(exc) from exc
    if public_session.get("session_id") != session_id:
        raise not_found

    internal_id = resource_session_id(
        resource_kind=resource_kind,
        resource_id=resource_id,
        resource_version=resource_version,
    )
    session = service.store.load_or_empty(
        course_id=course_id,
        classroom_id=internal_id,
        owner_user_id=principal.user_id,
    )
    registered = next(
        (
            turn
            for turn in session.get("turns") or []
            if turn.get("tts_status") == "ready" and turn.get("audio_filename") == filename
        ),
        None,
    )
    if registered is None or Path(filename).name != filename:
        raise not_found

    audio_root = service.store.session_dir(
        course_id=course_id,
        classroom_id=internal_id,
        owner_user_id=principal.user_id,
    ) / "audio"
    try:
        resolved_root = audio_root.resolve()
        candidate = (audio_root / filename).resolve()
        candidate.relative_to(resolved_root)
    except (OSError, ValueError):
        raise not_found
    if not candidate.is_file():
        raise not_found
    return FileResponse(
        candidate,
        media_type=str(registered.get("audio_mime_type") or "application/octet-stream"),
        filename=filename,
    )


def _http_error(exc: ResourceQaError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.public_message, "retryable": exc.retryable},
    )
