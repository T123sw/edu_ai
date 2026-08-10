"""Domain records for course learning interactions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4


TaskStatus = Literal["draft", "published", "closed"]
ProgressStatus = Literal["not_started", "in_progress", "completed"]
LearningEventType = Literal[
    "started",
    "resource_opened",
    "progress_updated",
    "completed",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LearningTaskRecord:
    task_id: str
    course_id: str
    title: str
    instructions: str
    created_by: str
    resource_refs: list[dict[str, str]] = field(default_factory=list)
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
        resource_refs: list[dict[str, str]] | None = None,
        knowledge_point_ids: list[str] | None = None,
    ) -> "LearningTaskRecord":
        return cls(
            task_id=f"lt_{uuid4().hex}",
            course_id=str(course_id).strip(),
            title=str(title).strip(),
            instructions=str(instructions or "").strip(),
            created_by=str(created_by).strip(),
            resource_refs=[dict(item) for item in resource_refs or []],
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
        )


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


@dataclass(frozen=True)
class EventWriteResult:
    created: bool
    progress: TaskProgressRecord

