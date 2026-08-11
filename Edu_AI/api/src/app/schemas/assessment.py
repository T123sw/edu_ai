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
