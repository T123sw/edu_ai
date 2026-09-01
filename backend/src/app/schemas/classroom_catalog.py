from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ClassroomCatalogProgressResponse(BaseModel):
    resource_id: str
    resource_version: int
    status: str
    completion_basis: str | None = None
    explanation_coverage_percent: float
    answered_question_count: int
    required_question_count: int
    completed_at: str | None
    last_activity_at: str | None


class ClassroomCatalogResourceResponse(BaseModel):
    standard_kind: str
    material_type: str
    material_id: str
    review_status: str
    current_version: int | None
    approved_version: int | None
    resource: dict[str, Any] | None
    progress: ClassroomCatalogProgressResponse | None = None


class ClassroomCatalogLeafResponse(BaseModel):
    leaf_id: str
    title: str
    chapter_id: str | None
    chapter_title: str | None
    path_titles: list[str]
    resources: list[ClassroomCatalogResourceResponse]
    summary: dict[str, int] | None = None
    learning_summary: dict[str, int] | None = None


class ClassroomCatalogResponse(BaseModel):
    course_id: str
    mode: Literal["manage", "learn"]
    leaves: list[ClassroomCatalogLeafResponse]
