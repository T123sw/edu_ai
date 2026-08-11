"""Teacher-facing assessment authoring contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AssessmentQualityIssueResponse(BaseModel):
    code: str
    assessment_item_id: str | None
    message: str


class AssessmentQualityResponse(BaseModel):
    publishable: bool
    issues: list[AssessmentQualityIssueResponse]


class AssessmentItemResponse(BaseModel):
    assessment_item_id: str
    assessment_version_id: str
    position: int
    item_type: str
    prompt: dict[str, Any]
    scoring_key: dict[str, Any]
    rubric: dict[str, Any]
    max_score: float
    grading_provider: str
    knowledge_point_ids: list[str]
    source_refs: list[dict[str, Any]]
    source_exposure_state: str
    created_origin: str


class AssessmentDraftResponse(BaseModel):
    assessment_version_id: str
    assessment_id: str
    task_id: str
    course_id: str
    version_number: int
    status: str
    source_mode: str
    assessment_mode: str
    pass_threshold: float
    mastery_threshold: float
    max_attempts: int
    score_policy: str
    answer_reveal_policy: str
    shuffle_questions: bool
    shuffle_options: bool
    draft_revision: int
    content_hash: str | None
    published_at: str | None
    published_by: str | None
    created_at: str
    items: list[AssessmentItemResponse]
    quality: AssessmentQualityResponse


class AssessmentDraftUpdateRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    pass_threshold: float
    mastery_threshold: float
    max_attempts: int
    assessment_mode: str
    answer_reveal_policy: str
    shuffle_questions: bool
    shuffle_options: bool
    items: list[AssessmentItemResponse]


class AssessmentGenerateRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    difficulty: str = Field(default="medium", min_length=1, max_length=32)


class AssessmentPublishRequest(BaseModel):
    expected_revision: int = Field(ge=0)


class StudentAssessmentItemResponse(BaseModel):
    assessment_item_id: str
    position: int
    item_type: str
    prompt: dict[str, Any]
    max_score: float
    knowledge_point_ids: list[str]


class StudentAssessmentResponse(BaseModel):
    assessment_version_id: str
    task_id: str
    assessment_mode: str
    max_attempts: int
    items: list[StudentAssessmentItemResponse]


class AssessmentAttemptResponse(BaseModel):
    attempt_id: str
    assessment_version_id: str
    task_id: str
    attempt_number: int
    status: str
    draft_revision: int
    submitted_at: str | None
    auto_score: float | None
    final_score: float | None
    result: str | None


class AssessmentAnswersRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    answers: dict[str, dict[str, Any]]


class AssessmentSubmitRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=300)


class AssessmentFeedbackItemResponse(BaseModel):
    assessment_item_id: str
    position: int
    item_type: str
    prompt: dict[str, Any]
    answer: dict[str, Any] | None
    final_score: float | None
    max_score: float
    review_status: str
    solution: dict[str, Any] | None = None
    rubric: dict[str, Any] | None = None


class AssessmentFeedbackResponse(BaseModel):
    assessment_assignment_id: str
    task_id: str
    attempts_used: int
    max_attempts: int
    best_final_score: float | None
    result: str
    answers_revealed_at: str | None
    items: list[AssessmentFeedbackItemResponse]
