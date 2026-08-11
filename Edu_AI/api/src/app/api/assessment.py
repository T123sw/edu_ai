"""Teacher-only assessment authoring endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.course_dependencies import require_course_edit
from app.assessment import get_assessment_service
from app.assessment.service import AssessmentRuleError, AssessmentService
from app.schemas.assessment import (
    AssessmentDraftResponse,
    AssessmentDraftUpdateRequest,
    AssessmentGenerateRequest,
    AssessmentQualityResponse,
)
from app.services.course_access import CoursePrincipal


router = APIRouter(
    prefix="/api/courses/{course_id}/learning/tasks/{task_id}/assessment",
    tags=["assessment-authoring"],
)


def assessment_http_error(error: AssessmentRuleError) -> HTTPException:
    status_by_code = {
        "COURSE_EDIT_REQUIRED": status.HTTP_403_FORBIDDEN,
        "TASK_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "ASSESSMENT_REQUIRED": status.HTTP_409_CONFLICT,
        "ASSESSMENT_INVALID": status.HTTP_409_CONFLICT,
        "ASSESSMENT_VERSION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "DRAFT_REVISION_CONFLICT": status.HTTP_409_CONFLICT,
    }
    return HTTPException(
        status_code=status_by_code.get(error.code, status.HTTP_422_UNPROCESSABLE_CONTENT),
        detail={"code": error.code, "message": error.message},
    )


@router.post("/detect", response_model=AssessmentDraftResponse)
def detect_assessment(
    course_id: str,
    task_id: str,
    principal: CoursePrincipal = Depends(require_course_edit),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentDraftResponse:
    try:
        return AssessmentDraftResponse.model_validate(
            service.detect_or_create_draft(
                course_id=course_id, task_id=task_id, teacher_id=principal.user_id
            )
        )
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error


@router.get("/draft", response_model=AssessmentDraftResponse)
def get_assessment_draft(
    course_id: str,
    task_id: str,
    principal: CoursePrincipal = Depends(require_course_edit),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentDraftResponse:
    try:
        return AssessmentDraftResponse.model_validate(
            service.get_task_draft(
                course_id=course_id, task_id=task_id, teacher_id=principal.user_id
            )
        )
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error


@router.put("/draft", response_model=AssessmentDraftResponse)
def update_assessment_draft(
    course_id: str,
    task_id: str,
    payload: AssessmentDraftUpdateRequest,
    principal: CoursePrincipal = Depends(require_course_edit),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentDraftResponse:
    try:
        values = payload.model_dump()
        return AssessmentDraftResponse.model_validate(
            service.update_task_draft(
                course_id=course_id,
                task_id=task_id,
                teacher_id=principal.user_id,
                expected_revision=payload.expected_revision,
                settings=values,
                raw_items=values["items"],
            )
        )
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error


@router.post("/validate", response_model=AssessmentQualityResponse)
def validate_assessment(
    course_id: str,
    task_id: str,
    principal: CoursePrincipal = Depends(require_course_edit),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentQualityResponse:
    try:
        report = service.validate_task_assessment(
            course_id=course_id, task_id=task_id, teacher_id=principal.user_id
        )
        return AssessmentQualityResponse.model_validate(
            {"publishable": report.publishable, "issues": [asdict(i) for i in report.issues]}
        )
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error


@router.post("/generate", response_model=AssessmentDraftResponse)
def generate_assessment_items(
    course_id: str,
    task_id: str,
    payload: AssessmentGenerateRequest,
    principal: CoursePrincipal = Depends(require_course_edit),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentDraftResponse:
    try:
        return AssessmentDraftResponse.model_validate(
            service.generate_missing_items(
                course_id=course_id,
                task_id=task_id,
                teacher_id=principal.user_id,
                expected_revision=payload.expected_revision,
                difficulty=payload.difficulty,
            )
        )
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error
