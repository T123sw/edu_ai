"""Public API contracts for course learning tasks and progress."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LearningResourceRef(BaseModel):
    material_type: str = Field(min_length=1, max_length=64)
    material_id: str = Field(min_length=1, max_length=240)
    snapshot_id: str | None = Field(default=None, max_length=240)


class LearningTaskResourceSnapshotResponse(BaseModel):
    snapshot_id: str
    task_id: str
    position: int
    source_material_type: str
    source_material_id: str
    source_version: int
    origin_type: str
    standard_kind: str | None = None
    title: str
    content_payload: dict
    file_refs: list[str]
    created_at: str


class TaskResourceEvidenceResponse(BaseModel):
    resource_id: str
    resource_version: int
    condition_status: Literal["pending", "satisfied"]
    evidence_source: Literal["course_resource_learning"]
    resource_completed_at: str | None = None


class TaskProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    course_id: str
    student_id: str
    status: Literal["not_started", "in_progress", "completed"]
    progress_percent: int = Field(ge=0, le=100)
    completion_basis: Literal[
        "none", "self_reported", "activity_evidenced", "assessment_verified"
    ] = "none"
    evidence_count: int = Field(default=0, ge=0)
    last_activity_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str


class LearningTaskCreateRequest(BaseModel):
    task_type: Literal["reading", "assessed"] = "assessed"
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(default="", max_length=10_000)
    resource_refs: list[LearningResourceRef] = Field(default_factory=list, max_length=100)
    knowledge_point_ids: list[str] = Field(default_factory=list, max_length=200)


class LearningTaskResponse(BaseModel):
    task_id: str
    course_id: str
    title: str
    instructions: str
    created_by: str
    task_type: Literal["reading", "assessed"] = "assessed"
    resource_refs: list[LearningResourceRef]
    resource_snapshots: list[LearningTaskResourceSnapshotResponse] = Field(default_factory=list)
    knowledge_point_ids: list[str]
    status: Literal["draft", "published", "closed"]
    created_at: str
    published_at: str | None = None
    published_by: str | None = None
    my_progress: TaskProgressResponse | None = None
    resource_evidence: list[TaskResourceEvidenceResponse] = Field(default_factory=list)


class LearningEvidencePayload(BaseModel):
    evidence_type: str = Field(min_length=1, max_length=64)
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=160)
    value: float | str | bool | None = None


class LearningEventRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=160)
    event_type: Literal[
        "started", "resource_opened", "progress_updated", "completed",
        "resource_completed",
    ]
    progress_percent: int = Field(ge=0, le=100)
    resource_ref: LearningResourceRef | None = None
    evidence: LearningEvidencePayload | None = None


class LearningEventResponse(BaseModel):
    created: bool
    progress: TaskProgressResponse


class CourseLearningSummaryResponse(BaseModel):
    task: LearningTaskResponse
    enrolled_students: int = Field(ge=0)
    started_students: int = Field(ge=0)
    completed_students: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=1)
    progress: list[TaskProgressResponse]


class LearningOverviewResponse(BaseModel):
    course_id: str
    pending_tasks: int = Field(ge=0)
    in_progress_tasks: int = Field(ge=0)
    self_reported_completed_tasks: int = Field(ge=0)
    activity_evidenced_completed_tasks: int = Field(ge=0)
    assessment_verified_completed_tasks: int = Field(ge=0)
    latest_activity_at: str | None = None
    enrolled_students: int | None = Field(default=None, ge=0)
    self_reported_students: int | None = Field(default=None, ge=0)
    activity_evidenced_students: int | None = Field(default=None, ge=0)
    assessment_verified_students: int | None = Field(default=None, ge=0)
