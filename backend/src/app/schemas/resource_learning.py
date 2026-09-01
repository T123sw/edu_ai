from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResourceLearningEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=200)
    sequence_number: int = Field(ge=1)
    event_type: Literal[
        "scene_entered",
        "timeline_heartbeat",
        "playback_paused",
        "scene_completed",
        "demo_entered",
        "demo_interacted",
        "demo_completed",
    ]
    scene_id: str = Field(min_length=1, max_length=240)
    timeline_from_ms: int | None = Field(default=None, ge=0)
    timeline_to_ms: int | None = Field(default=None, ge=0)
    action_id: str | None = Field(default=None, max_length=240)
    occurred_at: datetime


class ResourceLearningEventBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[ResourceLearningEventRequest] = Field(min_length=1, max_length=100)


class ResourceQuestionSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=200)
    answers: dict[str, str | list[str]]


class ResourceLearningActivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=200)
    action: Literal["opened", "completed"]
    occurred_at: datetime


class ResourceLearningSessionResponse(BaseModel):
    session_id: str
    course_id: str
    resource_id: str
    resource_version: int
    status: str
    started_at: str
    last_heartbeat_at: str | None
    ended_at: str | None


class LearningManifestSceneResponse(BaseModel):
    scene_id: str
    kind: str
    expected_duration_ms: int
    required_action_ids: list[str]
    required_question_ids: list[str]


class SafeLearningManifestResponse(BaseModel):
    manifest_id: str
    resource_version: int
    content_hash: str
    mode: str
    scenes: list[LearningManifestSceneResponse]
    required_question_ids: list[str]


class ResourceLearningProgressResponse(BaseModel):
    course_id: str
    resource_id: str
    resource_version: int
    status: str
    completion_basis: Literal[
        "classroom_requirements",
        "required_questions_submitted",
        "explicit_read",
    ] | None = None
    explanation_covered_ms: int
    explanation_total_ms: int
    explanation_coverage_percent: float
    required_question_count: int
    answered_question_count: int
    question_completion_percent: float
    correct_count_first: int
    correct_count_latest: int
    demo_view_count: int
    demo_interaction_count: int
    started_at: str | None
    completed_at: str | None
    last_activity_at: str | None
    updated_at: str
    manifest: SafeLearningManifestResponse | None = None


class ResourceLearningStudentResponse(ResourceLearningProgressResponse):
    student_id: str


class ResourceLearningAnalyticsResponse(BaseModel):
    course_id: str
    resource_id: str
    resource_version: int
    enrolled_student_count: int
    tracked_student_count: int
    started_student_count: int
    completed_student_count: int
    in_progress_student_count: int
    not_started_student_count: int
    average_explanation_coverage_percent: float
    average_question_completion_percent: float
    completion_rate: float
    completion_rate_ratio: dict[str, int | float]
    all_questions_answered_student_count: int
    demo_view_student_count: int
    demo_interaction_student_count: int
    demo_view_count: int
    demo_interaction_count: int
    queues: dict[str, int]
    question_analytics: list[dict]
    knowledge_point_errors: list[dict]
