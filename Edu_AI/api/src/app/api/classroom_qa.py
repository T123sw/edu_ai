"""Authorized API boundary for student Q&A during AI classroom playback."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.course_dependencies import require_course_read
from app.schemas.classroom_qa import (
    ClassroomQaSessionResponse,
    ClassroomQaTurnRequest,
    ClassroomQaTurnSubmissionResponse,
)
from app.services.classroom_qa_service import ClassroomQaError, ClassroomQaService
from app.services.course_access import CoursePrincipal


router = APIRouter(prefix="/api/courses", tags=["classroom-qa"])
_service = ClassroomQaService()


def get_classroom_qa_service() -> ClassroomQaService:
    return _service


@router.get(
    "/{course_id}/classrooms/{classroom_id}/qa/session",
    response_model=ClassroomQaSessionResponse,
)
async def get_classroom_qa_session(
    course_id: str,
    classroom_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: ClassroomQaService = Depends(get_classroom_qa_service),
):
    try:
        return await service.get_session(
            course_id=course_id,
            classroom_id=classroom_id,
            owner_user_id=principal.user_id,
        )
    except ClassroomQaError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/{course_id}/classrooms/{classroom_id}/qa/turns",
    response_model=ClassroomQaTurnSubmissionResponse,
)
async def submit_classroom_qa_turn(
    course_id: str,
    classroom_id: str,
    request: ClassroomQaTurnRequest,
    principal: CoursePrincipal = Depends(require_course_read),
    service: ClassroomQaService = Depends(get_classroom_qa_service),
):
    try:
        return await service.submit_turn(
            course_id=course_id,
            classroom_id=classroom_id,
            owner_user_id=principal.user_id,
            request=request,
        )
    except ClassroomQaError as exc:
        raise _http_error(exc) from exc


@router.get(
    "/{course_id}/classrooms/{classroom_id}/qa/"
    "sessions/{session_id}/audio/{filename}"
)
async def get_classroom_qa_audio(
    course_id: str,
    classroom_id: str,
    session_id: str,
    filename: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: ClassroomQaService = Depends(get_classroom_qa_service),
):
    not_found = HTTPException(status_code=404, detail="Not found")
    try:
        public_session = await service.get_session(
            course_id=course_id,
            classroom_id=classroom_id,
            owner_user_id=principal.user_id,
        )
    except ClassroomQaError as exc:
        if exc.status_code == 404:
            raise not_found from exc
        raise _http_error(exc) from exc
    if public_session.get("session_id") != session_id:
        raise not_found

    session = service.store.load_or_empty(
        course_id=course_id,
        classroom_id=classroom_id,
        owner_user_id=principal.user_id,
    )
    registered = next(
        (
            turn
            for turn in session.get("turns") or []
            if turn.get("tts_status") == "ready"
            and turn.get("audio_filename") == filename
        ),
        None,
    )
    if registered is None or Path(filename).name != filename:
        raise not_found

    audio_root = service.store.session_dir(
        course_id=course_id,
        classroom_id=classroom_id,
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


def _http_error(exc: ClassroomQaError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "code": exc.code,
            "message": exc.public_message,
            "retryable": exc.retryable,
        },
    )
