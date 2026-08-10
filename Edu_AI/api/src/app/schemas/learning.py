"""Public API contracts for course learning tasks and progress."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LearningResourceRef(BaseModel):
    material_type: str = Field(min_length=1, max_length=64)
    material_id: str = Field(min_length=1, max_length=160)


class TaskProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    course_id: str
    student_id: str
    status: Literal["not_started", "in_progress", "completed"]
    progress_percent: int = Field(ge=0, le=100)
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str


class LearningTaskCreateRequest(BaseModel):
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
    resource_refs: list[LearningResourceRef]
    knowledge_point_ids: list[str]
    status: Literal["draft", "published", "closed"]
    created_at: str
    published_at: str | None = None
    published_by: str | None = None
    my_progress: TaskProgressResponse | None = None


class LearningEventRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=160)
    event_type: Literal["started", "resource_opened", "progress_updated", "completed"]
    progress_percent: int = Field(ge=0, le=100)
    resource_ref: LearningResourceRef | None = None


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
