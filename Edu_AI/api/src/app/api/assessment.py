"""Teacher-only assessment authoring endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.course_dependencies import require_course_edit, require_course_read
from app.assessment import get_assessment_service
from app.assessment.service import AssessmentRuleError, AssessmentService
from app.schemas.assessment import (
    AssessmentDraftResponse,
    AssessmentDraftUpdateRequest,
    AssessmentGenerateRequest,
    AssessmentAnswersRequest,
    AssessmentAttemptResponse,
    AssessmentSubmitRequest,
    AssessmentFeedbackResponse,
    AssessmentQualityResponse,
    StudentAssessmentResponse,
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
        "ATTEMPT_REVISION_CONFLICT": status.HTTP_409_CONFLICT,
        "ATTEMPTS_EXHAUSTED": status.HTTP_409_CONFLICT,
        "ANSWERS_REVEALED": status.HTTP_409_CONFLICT,
        "ANSWER_REVEAL_NOT_ALLOWED": status.HTTP_409_CONFLICT,
        "ATTEMPT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "COURSE_READ_REQUIRED": status.HTTP_403_FORBIDDEN,
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


def _require_student(principal: CoursePrincipal) -> None:
    if principal.system_role.lower() != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "STUDENT_ROLE_REQUIRED", "message": "Student role is required"},
        )


@router.get("", response_model=StudentAssessmentResponse)
def get_student_assessment(
    course_id: str,
    task_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: AssessmentService = Depends(get_assessment_service),
) -> StudentAssessmentResponse:
    _require_student(principal)
    try:
        return StudentAssessmentResponse.model_validate(
            service.get_student_assessment(
                course_id=course_id, task_id=task_id, student_id=principal.user_id
            )
        )
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error


@router.post("/attempts", response_model=AssessmentAttemptResponse)
def start_student_attempt(
    course_id: str,
    task_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentAttemptResponse:
    _require_student(principal)
    try:
        return AssessmentAttemptResponse.model_validate(
            service.start_attempt(
                course_id=course_id, task_id=task_id, student_id=principal.user_id
            ),
            from_attributes=True,
        )
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error


@router.get("/attempts", response_model=list[AssessmentAttemptResponse])
def list_student_attempts(
    course_id: str,
    task_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: AssessmentService = Depends(get_assessment_service),
) -> list[AssessmentAttemptResponse]:
    _require_student(principal)
    try:
        return [
            AssessmentAttemptResponse.model_validate(item, from_attributes=True)
            for item in service.list_student_attempts(
                course_id=course_id, task_id=task_id, student_id=principal.user_id
            )
        ]
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error


@router.put("/attempts/{attempt_id}/answers", response_model=AssessmentAttemptResponse)
def save_student_answers(
    course_id: str,
    task_id: str,
    attempt_id: str,
    payload: AssessmentAnswersRequest,
    principal: CoursePrincipal = Depends(require_course_read),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentAttemptResponse:
    _require_student(principal)
    try:
        return AssessmentAttemptResponse.model_validate(
            service.save_answers(
                attempt_id=attempt_id,
                student_id=principal.user_id,
                answers=payload.answers,
                expected_revision=payload.expected_revision,
                course_id=course_id,
                task_id=task_id,
            ),
            from_attributes=True,
        )
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error


@router.post("/attempts/{attempt_id}/submit", response_model=AssessmentAttemptResponse)
def submit_student_attempt(
    course_id: str,
    task_id: str,
    attempt_id: str,
    payload: AssessmentSubmitRequest,
    principal: CoursePrincipal = Depends(require_course_read),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentAttemptResponse:
    _require_student(principal)
    try:
        return AssessmentAttemptResponse.model_validate(
            service.submit_attempt(
                attempt_id=attempt_id,
                student_id=principal.user_id,
                idempotency_key=payload.idempotency_key,
                course_id=course_id,
                task_id=task_id,
            ),
            from_attributes=True,
        )
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error


@router.get(
    "/feedback",
    response_model=AssessmentFeedbackResponse,
    response_model_exclude_none=True,
)
def get_student_feedback(
    course_id: str,
    task_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentFeedbackResponse:
    _require_student(principal)
    try:
        return AssessmentFeedbackResponse.model_validate(
            service.get_student_feedback(
                course_id=course_id, task_id=task_id, student_id=principal.user_id
            )
        )
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error


@router.post(
    "/reveal",
    response_model=AssessmentFeedbackResponse,
    response_model_exclude_none=True,
)
def reveal_student_answers(
    course_id: str,
    task_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentFeedbackResponse:
    _require_student(principal)
    try:
        return AssessmentFeedbackResponse.model_validate(
            service.reveal_answers(
                course_id=course_id, task_id=task_id, student_id=principal.user_id
            )
        )
    except AssessmentRuleError as error:
        raise assessment_http_error(error) from error
