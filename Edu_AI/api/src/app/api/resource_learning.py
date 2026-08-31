"""Role-safe endpoints for course resource learning evidence."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.course_dependencies import require_course_edit, require_course_read
from app.persistence.dependencies import get_resource_learning_repository
from app.resource_learning.service import ResourceLearningRuleError, ResourceLearningService
from app.schemas.resource_learning import (
    ResourceLearningAnalyticsResponse,
    ResourceLearningEventBatchRequest,
    ResourceLearningProgressResponse,
    ResourceLearningSessionResponse,
    ResourceLearningStudentResponse,
    ResourceQuestionSubmissionRequest,
)
from app.services.course_access import CoursePrincipal


router = APIRouter(prefix="/api/courses/{course_id}", tags=["resource-learning"])


def get_resource_learning_service() -> ResourceLearningService:
    return ResourceLearningService(get_resource_learning_repository())


def _http_error(error: ResourceLearningRuleError) -> HTTPException:
    code_map = {
        "MANIFEST_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "PROGRESS_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "SESSION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "SESSION_OWNER_MISMATCH": status.HTTP_403_FORBIDDEN,
        "SESSION_INACTIVE": status.HTTP_409_CONFLICT,
        "SEQUENCE_CONFLICT": status.HTTP_409_CONFLICT,
    }
    return HTTPException(
        status_code=code_map.get(error.code, status.HTTP_422_UNPROCESSABLE_CONTENT),
        detail={"code": error.code, "message": error.message},
    )


def _safe_manifest(service: ResourceLearningService, course_id: str, resource_id: str, version: int) -> dict:
    manifest = service.repository.get_manifest(course_id, resource_id, version)
    if manifest is None:
        raise ResourceLearningRuleError("MANIFEST_NOT_FOUND", "learning manifest was not found")
    return {
        "manifest_id": manifest.manifest_id,
        "resource_version": manifest.resource_version,
        "content_hash": manifest.content_hash,
        "mode": manifest.mode,
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "kind": scene.kind,
                "expected_duration_ms": scene.expected_duration_ms,
                "required_action_ids": list(scene.required_action_ids),
                "required_question_ids": list(scene.required_question_ids),
            }
            for scene in manifest.scenes
        ],
        "required_question_ids": list(manifest.required_question_ids),
    }


def _progress_payload(service: ResourceLearningService, progress, *, include_manifest: bool = True) -> dict:
    payload = asdict(progress)
    if include_manifest:
        payload["manifest"] = _safe_manifest(
            service,
            progress.course_id,
            progress.resource_id,
            progress.resource_version,
        )
    return payload


@router.get("/resource-learning/me", response_model=list[ResourceLearningProgressResponse])
def list_my_course_resource_progress(
    course_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: ResourceLearningService = Depends(get_resource_learning_service),
):
    return [
        ResourceLearningProgressResponse.model_validate(_progress_payload(service, item))
        for item in service.list_my_course_progress(course_id, principal.user_id)
    ]


@router.get(
    "/resources/{resource_id}/versions/{version}/learning/me",
    response_model=ResourceLearningProgressResponse,
)
def get_my_resource_progress(
    course_id: str,
    resource_id: str,
    version: int,
    principal: CoursePrincipal = Depends(require_course_read),
    service: ResourceLearningService = Depends(get_resource_learning_service),
):
    try:
        progress = service.get_my_progress(
            course_id, resource_id, version, principal.user_id
        )
        return ResourceLearningProgressResponse.model_validate(
            _progress_payload(service, progress)
        )
    except ResourceLearningRuleError as error:
        raise _http_error(error) from error


@router.post(
    "/resources/{resource_id}/versions/{version}/learning/sessions",
    response_model=ResourceLearningSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_resource_learning_session(
    course_id: str,
    resource_id: str,
    version: int,
    principal: CoursePrincipal = Depends(require_course_read),
    service: ResourceLearningService = Depends(get_resource_learning_service),
):
    try:
        session = service.start_session(
            course_id, resource_id, version, principal.user_id
        )
        return ResourceLearningSessionResponse.model_validate(asdict(session))
    except ResourceLearningRuleError as error:
        raise _http_error(error) from error


@router.post(
    "/resources/{resource_id}/versions/{version}/learning/sessions/{session_id}/events:batch",
    response_model=ResourceLearningProgressResponse,
)
def record_resource_learning_events(
    course_id: str,
    resource_id: str,
    version: int,
    session_id: str,
    payload: ResourceLearningEventBatchRequest,
    principal: CoursePrincipal = Depends(require_course_read),
    service: ResourceLearningService = Depends(get_resource_learning_service),
):
    try:
        progress = service.record_events(
            session_id,
            principal.user_id,
            [item.model_dump() for item in payload.events],
        )
        if (progress.course_id, progress.resource_id, progress.resource_version) != (
            course_id,
            resource_id,
            version,
        ):
            raise ResourceLearningRuleError(
                "SESSION_RESOURCE_MISMATCH", "session does not match the requested resource"
            )
        return ResourceLearningProgressResponse.model_validate(
            _progress_payload(service, progress)
        )
    except ResourceLearningRuleError as error:
        raise _http_error(error) from error


@router.post(
    "/resources/{resource_id}/versions/{version}/learning/questions:submit",
    response_model=ResourceLearningProgressResponse,
)
def submit_resource_questions(
    course_id: str,
    resource_id: str,
    version: int,
    payload: ResourceQuestionSubmissionRequest,
    principal: CoursePrincipal = Depends(require_course_read),
    service: ResourceLearningService = Depends(get_resource_learning_service),
):
    try:
        progress = service.submit_questions(
            course_id,
            resource_id,
            version,
            principal.user_id,
            payload.answers,
            payload.idempotency_key,
        )
        return ResourceLearningProgressResponse.model_validate(
            _progress_payload(service, progress)
        )
    except ResourceLearningRuleError as error:
        raise _http_error(error) from error


@router.post(
    "/resources/{resource_id}/versions/{version}/learning/sessions/{session_id}/end",
    response_model=ResourceLearningSessionResponse,
)
def end_resource_learning_session(
    course_id: str,
    resource_id: str,
    version: int,
    session_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: ResourceLearningService = Depends(get_resource_learning_service),
):
    try:
        session = service.end_session(session_id, principal.user_id)
        if (session.course_id, session.resource_id, session.resource_version) != (
            course_id,
            resource_id,
            version,
        ):
            raise ResourceLearningRuleError(
                "SESSION_RESOURCE_MISMATCH", "session does not match the requested resource"
            )
        return ResourceLearningSessionResponse.model_validate(asdict(session))
    except ResourceLearningRuleError as error:
        raise _http_error(error) from error


@router.get(
    "/resources/{resource_id}/versions/{version}/learning/analytics",
    response_model=ResourceLearningAnalyticsResponse,
)
def get_resource_learning_analytics(
    course_id: str,
    resource_id: str,
    version: int,
    _principal: CoursePrincipal = Depends(require_course_edit),
    service: ResourceLearningService = Depends(get_resource_learning_service),
):
    return ResourceLearningAnalyticsResponse.model_validate(
        service.get_analytics(course_id, resource_id, version)
    )


@router.get(
    "/resources/{resource_id}/versions/{version}/learning/students",
    response_model=list[ResourceLearningStudentResponse],
)
def list_resource_learning_students(
    course_id: str,
    resource_id: str,
    version: int,
    _principal: CoursePrincipal = Depends(require_course_edit),
    service: ResourceLearningService = Depends(get_resource_learning_service),
):
    return [
        ResourceLearningStudentResponse.model_validate(
            {**_progress_payload(service, progress), "student_id": student_id}
        )
        for student_id, progress in service.list_student_progress(
            course_id, resource_id, version
        )
    ]


@router.get(
    "/resources/{resource_id}/versions/{version}/learning/students/{student_id}",
    response_model=ResourceLearningStudentResponse,
)
def get_resource_learning_student(
    course_id: str,
    resource_id: str,
    version: int,
    student_id: str,
    _principal: CoursePrincipal = Depends(require_course_edit),
    service: ResourceLearningService = Depends(get_resource_learning_service),
):
    try:
        progress = service.get_student_progress(
            course_id, resource_id, version, student_id
        )
        return ResourceLearningStudentResponse.model_validate(
            {**_progress_payload(service, progress), "student_id": student_id}
        )
    except ResourceLearningRuleError as error:
        raise _http_error(error) from error

