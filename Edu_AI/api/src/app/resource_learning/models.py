from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SceneKind = Literal["explanation", "exercise", "demo"]
ManifestMode = Literal["completable", "behavior_only"]


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

