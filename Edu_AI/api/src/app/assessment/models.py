"""Immutable domain records for learning-task assessments."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass(frozen=True)
class AssessmentRecord:
    assessment_id: str
    course_id: str
    task_id: str
    created_by: str
    created_at: str = field(default_factory=utc_now)
    current_version_id: str | None = None


@dataclass(frozen=True)
class AssessmentVersionRecord:
    assessment_version_id: str
    assessment_id: str
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
    draft_revision: int = 0
    content_hash: str | None = None
    published_at: str | None = None
    published_by: str | None = None
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class AssessmentItemRecord:
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

    @classmethod
    def new(
        cls,
        *,
        assessment_version_id: str,
        position: int,
        item_type: str,
        prompt: dict[str, Any],
        scoring_key: dict[str, Any],
        rubric: dict[str, Any],
        max_score: float,
        grading_provider: str,
        knowledge_point_ids: list[str],
        source_refs: list[dict[str, Any]],
        created_origin: str,
        source_exposure_state: str = "private",
    ) -> "AssessmentItemRecord":
        return cls(
            assessment_item_id=_id("asi"),
            assessment_version_id=str(assessment_version_id),
            position=int(position),
            item_type=str(item_type),
            prompt=dict(prompt),
            scoring_key=dict(scoring_key),
            rubric=dict(rubric),
            max_score=float(max_score),
            grading_provider=str(grading_provider),
            knowledge_point_ids=list(knowledge_point_ids),
            source_refs=[dict(item) for item in source_refs],
            source_exposure_state=str(source_exposure_state),
            created_origin=str(created_origin),
        )


@dataclass(frozen=True)
class AssessmentAssignmentRecord:
    assessment_assignment_id: str
    task_id: str
    course_id: str
    student_id: str
    assessment_version_id: str
    cycle_number: int
    max_attempts: int
    attempts_used: int = 0
    best_attempt_id: str | None = None
    best_final_score: float | None = None
    result: str = "not_attempted"
    answers_revealed_at: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class AssessmentAttemptRecord:
    attempt_id: str
    assignment_id: str
    assessment_version_id: str
    task_id: str
    course_id: str
    student_id: str
    attempt_number: int
    status: str = "in_progress"
    draft_revision: int = 0
    submitted_at: str | None = None
    auto_score: float | None = None
    final_score: float | None = None
    result: str | None = None
    submission_idempotency_key: str | None = None
    invalidated_at: str | None = None
    invalidated_by: str | None = None
    invalidation_reason: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def new(
        cls,
        *,
        assignment_id: str,
        assessment_version_id: str,
        task_id: str,
        course_id: str,
        student_id: str,
        attempt_number: int,
    ) -> "AssessmentAttemptRecord":
        return cls(
            attempt_id=_id("att"),
            assignment_id=str(assignment_id),
            assessment_version_id=str(assessment_version_id),
            task_id=str(task_id),
            course_id=str(course_id),
            student_id=str(student_id),
            attempt_number=int(attempt_number),
        )


@dataclass(frozen=True)
class AssessmentAnswerRecord:
    answer_id: str
    attempt_id: str
    assessment_item_id: str
    answer: dict[str, Any]
    artifact_refs: list[dict[str, Any]] = field(default_factory=list)
    auto_score: float | None = None
    ai_suggestion: dict[str, Any] | None = None
    final_score: float | None = None
    review_status: str = "ungraded"
    updated_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class AssessmentReviewRecord:
    review_id: str
    attempt_id: str
    assessment_item_id: str | None
    reviewer_id: str
    previous_score: float | None
    new_score: float | None
    reason_code: str
    comment_private: str = ""
    comment_student_visible: str = ""
    created_at: str = field(default_factory=utc_now)
