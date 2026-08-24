"""Domain records for course learning interactions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4


TaskStatus = Literal["draft", "published", "closed"]
TaskType = Literal["reading", "assessed"]
ProgressStatus = Literal["not_started", "in_progress", "completed"]
CompletionBasis = Literal[
    "none",
    "self_reported",
    "activity_evidenced",
    "assessment_verified",
]
LearningEventType = Literal[
    "started",
    "resource_opened",
    "progress_updated",
    "completed",
    "resource_completed",
    "assessment_scored",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LearningTaskResourceSnapshot:
    snapshot_id: str
    task_id: str
    position: int
    source_material_type: str
    source_material_id: str
    source_version: int
    origin_type: str
    standard_kind: str | None
    title: str
    content_payload: dict
    file_refs: list[str]
    created_at: str = field(default_factory=utc_now)

    @classmethod
    def new(
        cls,
        *,
        task_id: str,
        position: int,
        material: dict,
    ) -> "LearningTaskResourceSnapshot":
        return cls(
            snapshot_id=f"lts_{uuid4().hex}",
            task_id=task_id,
            position=position,
            source_material_type=str(material["material_type"]),
            source_material_id=str(material["material_id"]),
            source_version=int(material.get("version") or 1),
            origin_type=str(material.get("origin_type") or "legacy_shared"),
            standard_kind=str(material.get("standard_kind") or "").strip() or None,
            title=str(material.get("title") or material["material_id"]),
            content_payload=dict(material.get("snapshot_content") or {}),
            file_refs=[str(item) for item in material.get("snapshot_file_refs") or []],
        )


@dataclass(frozen=True)
class LearningTaskRecord:
    task_id: str
    course_id: str
    title: str
    instructions: str
    created_by: str
    task_type: TaskType = "assessed"
    resource_refs: list[dict[str, str]] = field(default_factory=list)
    resource_snapshots: list[LearningTaskResourceSnapshot] = field(default_factory=list)
    knowledge_point_ids: list[str] = field(default_factory=list)
    status: TaskStatus = "draft"
    created_at: str = field(default_factory=utc_now)
    published_at: str | None = None
    published_by: str | None = None

    @classmethod
    def new(
        cls,
        *,
        course_id: str,
        title: str,
        instructions: str,
        created_by: str,
        task_type: TaskType = "assessed",
        resource_refs: list[dict[str, str]] | None = None,
        resource_snapshots: list[LearningTaskResourceSnapshot] | None = None,
        knowledge_point_ids: list[str] | None = None,
    ) -> "LearningTaskRecord":
        return cls(
            task_id=f"lt_{uuid4().hex}",
            course_id=str(course_id).strip(),
            title=str(title).strip(),
            instructions=str(instructions or "").strip(),
            created_by=str(created_by).strip(),
            task_type=task_type,
            resource_refs=[dict(item) for item in resource_refs or []],
            resource_snapshots=list(resource_snapshots or []),
            knowledge_point_ids=[str(item).strip() for item in knowledge_point_ids or [] if str(item).strip()],
        )


@dataclass(frozen=True)
class LearningEventRecord:
    event_id: str
    course_id: str
    task_id: str
    student_id: str
    event_type: LearningEventType
    progress_percent: int
    resource_ref: dict[str, str] | None = None
    occurred_at: str = field(default_factory=utc_now)
    evidence: LearningEvidence | None = None

    @classmethod
    def new(
        cls,
        *,
        event_id: str,
        course_id: str,
        task_id: str,
        student_id: str,
        event_type: LearningEventType,
        progress_percent: int,
        resource_ref: dict[str, str] | None = None,
        occurred_at: str | None = None,
        evidence: LearningEvidence | None = None,
    ) -> "LearningEventRecord":
        return cls(
            event_id=str(event_id).strip(),
            course_id=str(course_id).strip(),
            task_id=str(task_id).strip(),
            student_id=str(student_id).strip(),
            event_type=event_type,
            progress_percent=int(progress_percent),
            resource_ref=dict(resource_ref) if resource_ref else None,
            occurred_at=occurred_at or utc_now(),
            evidence=evidence,
        )


@dataclass(frozen=True)
class LearningEvidence:
    evidence_type: str
    source_type: str
    source_id: str
    value: float | str | bool | None
    occurred_at: str


@dataclass(frozen=True)
class TaskProgressRecord:
    task_id: str
    course_id: str
    student_id: str
    status: ProgressStatus
    progress_percent: int
    started_at: str | None
    completed_at: str | None
    updated_at: str
    completion_basis: CompletionBasis = "none"
    evidence_count: int = 0
    last_activity_at: str | None = None


@dataclass(frozen=True)
class EventWriteResult:
    created: bool
    progress: TaskProgressRecord


@dataclass(frozen=True)
class LearningTaskView:
    task: LearningTaskRecord
    my_progress: TaskProgressRecord | None = None


@dataclass(frozen=True)
class CourseTaskSummaryRecord:
    task: LearningTaskRecord
    enrolled_students: int
    started_students: int
    completed_students: int
    completion_rate: float
    progress: list[TaskProgressRecord] = field(default_factory=list)


@dataclass(frozen=True)
class LearningOverviewRecord:
    """Role-scoped, UI and Agent-safe course learning summary."""

    course_id: str
    pending_tasks: int
    in_progress_tasks: int
    self_reported_completed_tasks: int
    activity_evidenced_completed_tasks: int
    assessment_verified_completed_tasks: int
    latest_activity_at: str | None
    enrolled_students: int | None = None
    self_reported_students: int | None = None
    activity_evidenced_students: int | None = None
    assessment_verified_students: int | None = None
