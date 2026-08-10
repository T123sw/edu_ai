"""HTTP routes for the teacher-student course learning loop."""

from __future__ import annotations

import threading
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.course_dependencies import (
    get_course_membership_store,
    require_course_edit,
    require_course_read,
)
from app.learning.models import CourseTaskSummaryRecord, LearningTaskRecord, LearningTaskView
from app.learning.service import LearningRuleError, LearningService
from app.learning.store import LearningStore
from app.schemas.learning import (
    CourseLearningSummaryResponse,
    LearningEventRequest,
    LearningEventResponse,
    LearningTaskCreateRequest,
    LearningTaskResponse,
)
from app.services import course_service
from app.services.course_access import CoursePrincipal
from core import Config


router = APIRouter(prefix="/api/courses/{course_id}/learning", tags=["learning"])

_service_lock = threading.RLock()
_cached_path: Path | None = None
_cached_store: LearningStore | None = None
_cached_service: LearningService | None = None


def get_learning_service() -> LearningService:
    global _cached_path, _cached_store, _cached_service
    path = Path(Config.LEARNING_DB_PATH)
    with _service_lock:
        if _cached_service is None or _cached_path != path:
            if _cached_store is not None:
                _cached_store.close()
            membership_store = get_course_membership_store()
            manager = course_service._get_manager()
            _cached_path = path
            _cached_store = LearningStore(path)
            _cached_service = LearningService(
                store=_cached_store,
                material_lookup=lambda course_id, material_type, material_id, user_id: (
                    manager.get_generated_material(
                        course_id,
                        material_type,
                        material_id,
                        owner_user_id=user_id,
                    )
                ),
                membership_lookup=membership_store.list_for_course,
            )
        return _cached_service


def _http_error(error: LearningRuleError) -> HTTPException:
    status_by_code = {
        "TASK_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "COURSE_RESOURCE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "COURSE_EDIT_REQUIRED": status.HTTP_403_FORBIDDEN,
        "TASK_NOT_PUBLISHED": status.HTTP_409_CONFLICT,
        "TASK_NOT_PUBLISHABLE": status.HTTP_409_CONFLICT,
        "RESOURCE_NOT_ASSIGNED": status.HTTP_409_CONFLICT,
        "INVALID_TASK": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "INVALID_RESOURCE_REF": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "INVALID_PROGRESS": status.HTTP_422_UNPROCESSABLE_ENTITY,
    }
    return HTTPException(
        status_code=status_by_code.get(error.code, status.HTTP_400_BAD_REQUEST),
        detail={"code": error.code, "message": error.message},
    )


def _task_response(
    task_or_view: LearningTaskRecord | LearningTaskView,
) -> LearningTaskResponse:
    if isinstance(task_or_view, LearningTaskView):
        payload = asdict(task_or_view.task)
        payload["my_progress"] = (
            asdict(task_or_view.my_progress) if task_or_view.my_progress else None
        )
    else:
        payload = asdict(task_or_view)
        payload["my_progress"] = None
    return LearningTaskResponse.model_validate(payload)


def _summary_response(summary: CourseTaskSummaryRecord) -> CourseLearningSummaryResponse:
    return CourseLearningSummaryResponse.model_validate(
        {
            "task": _task_response(summary.task).model_dump(),
            "enrolled_students": summary.enrolled_students,
            "started_students": summary.started_students,
            "completed_students": summary.completed_students,
            "completion_rate": summary.completion_rate,
            "progress": [asdict(item) for item in summary.progress],
        }
    )


@router.post("/tasks", response_model=LearningTaskResponse, status_code=status.HTTP_201_CREATED)
def create_learning_task(
    course_id: str,
    payload: LearningTaskCreateRequest,
    principal: CoursePrincipal = Depends(require_course_edit),
    service: LearningService = Depends(get_learning_service),
) -> LearningTaskResponse:
    try:
        task = service.create_task(
            course_id=course_id,
            teacher_id=principal.user_id,
            title=payload.title,
            instructions=payload.instructions,
            resource_refs=[item.model_dump() for item in payload.resource_refs],
            knowledge_point_ids=payload.knowledge_point_ids,
        )
        return _task_response(task)
    except LearningRuleError as error:
        raise _http_error(error) from error


@router.get("/tasks", response_model=list[LearningTaskResponse])
def list_learning_tasks(
    course_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: LearningService = Depends(get_learning_service),
) -> list[LearningTaskResponse]:
    include_unpublished = principal.course_role in {"owner", "editor"}
    return [
        _task_response(item)
        for item in service.list_tasks(
            course_id=course_id,
            user_id=principal.user_id,
            include_unpublished=include_unpublished,
        )
    ]


@router.post("/tasks/{task_id}/publish", response_model=LearningTaskResponse)
def publish_learning_task(
    course_id: str,
    task_id: str,
    principal: CoursePrincipal = Depends(require_course_edit),
    service: LearningService = Depends(get_learning_service),
) -> LearningTaskResponse:
    try:
        return _task_response(
            service.publish_task(
                course_id=course_id,
                task_id=task_id,
                teacher_id=principal.user_id,
            )
        )
    except LearningRuleError as error:
        raise _http_error(error) from error


@router.post("/tasks/{task_id}/events", response_model=LearningEventResponse)
def record_learning_event(
    course_id: str,
    task_id: str,
    payload: LearningEventRequest,
    principal: CoursePrincipal = Depends(require_course_read),
    service: LearningService = Depends(get_learning_service),
) -> LearningEventResponse:
    if principal.system_role.lower() != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STUDENT_ROLE_REQUIRED",
                "message": "Only students can submit learning progress",
            },
        )
    try:
        result = service.record_student_event(
            course_id=course_id,
            task_id=task_id,
            student_id=principal.user_id,
            event_id=payload.event_id,
            event_type=payload.event_type,
            progress_percent=payload.progress_percent,
            resource_ref=payload.resource_ref.model_dump() if payload.resource_ref else None,
        )
        return LearningEventResponse.model_validate(
            {"created": result.created, "progress": asdict(result.progress)}
        )
    except LearningRuleError as error:
        raise _http_error(error) from error


@router.get("/tasks/{task_id}/progress", response_model=CourseLearningSummaryResponse)
def get_learning_progress(
    course_id: str,
    task_id: str,
    principal: CoursePrincipal = Depends(require_course_edit),
    service: LearningService = Depends(get_learning_service),
) -> CourseLearningSummaryResponse:
    try:
        return _summary_response(
            service.get_task_summary(
                course_id=course_id,
                task_id=task_id,
                teacher_id=principal.user_id,
            )
        )
    except LearningRuleError as error:
        raise _http_error(error) from error
