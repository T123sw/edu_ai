from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SceneKind = Literal["explanation", "exercise", "demo"]
ManifestMode = Literal["completable", "behavior_only"]
CompletionRule = Literal["classroom", "questions_only"]
SessionStatus = Literal["active", "ended", "invalidated"]
ProgressStatus = Literal["not_started", "in_progress", "completed"]


@dataclass(frozen=True)
class ManifestScene:
    scene_id: str
    kind: SceneKind
    expected_duration_ms: int
    required_action_ids: tuple[str, ...]
    required_question_ids: tuple[str, ...]


@dataclass(frozen=True)
class ManifestQuestion:
    question_id: str
    scene_id: str
    question_type: str
    required: bool
    scoring_values: tuple[str, ...]
    knowledge_point_ids: tuple[str, ...]


@dataclass(frozen=True)
class ResourceLearningManifestRecord:
    manifest_id: str
    course_id: str
    resource_id: str
    resource_version: int
    content_hash: str
    mode: ManifestMode
    scenes: tuple[ManifestScene, ...]
    questions: tuple[ManifestQuestion, ...]
    created_at: str
    completion_rule: CompletionRule = "classroom"

    @property
    def required_question_ids(self) -> tuple[str, ...]:
        return tuple(question.question_id for question in self.questions if question.required)

    @property
    def explanation_total_ms(self) -> int:
        return sum(
            scene.expected_duration_ms
            for scene in self.scenes
            if scene.kind == "explanation"
        )


@dataclass(frozen=True)
class ResourceLearningSessionRecord:
    session_id: str
    course_id: str
    resource_id: str
    resource_version: int
    status: SessionStatus
    started_at: str
    last_heartbeat_at: str | None
    ended_at: str | None


@dataclass(frozen=True)
class ResourceLearningProgressRecord:
    course_id: str
    resource_id: str
    resource_version: int
    status: ProgressStatus
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
    completion_basis: str | None = None
