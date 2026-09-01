"""HTTP contracts for standard learning resources."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StandardResourceSlotResponse(BaseModel):
    standard_kind: Literal["classroom", "study_guide", "practice"]
    material_type: str
    material_id: str
    review_status: str
    current_version: int | None = None
    approved_version: int | None = None
    resource: dict[str, Any] | None = None


class StandardResourceLeafResponse(BaseModel):
    leaf_id: str
    title: str
    chapter_id: str | None = None
    chapter_title: str | None = None
    path_titles: list[str]
    slots: list[StandardResourceSlotResponse]


class StandardResourceCatalogResponse(BaseModel):
    course_id: str
    leaves: list[StandardResourceLeafResponse]


class StandardResourceBatchCreateRequest(BaseModel):
    leaf_ids: list[str] = Field(default_factory=list, max_length=200)


class StandardResourceBatchItemResponse(BaseModel):
    batch_item_id: str
    batch_id: str
    leaf_id: str
    leaf_title: str
    standard_kind: str
    material_type: str
    material_id: str
    status: str
    job_id: str | None = None
    attempt_count: int
    error: dict[str, Any] | None = None
    created_at: str
    updated_at: str
    finished_at: str | None = None


class StandardResourceBatchResponse(BaseModel):
    batch_id: str
    course_id: str
    created_by: str
    status: str
    total_items: int
    queued_items: int
    running_items: int
    succeeded_items: int
    failed_items: int
    created_at: str
    updated_at: str
    finished_at: str | None = None
    items: list[StandardResourceBatchItemResponse]


class StandardResourceReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=2000)


class StandardResourceReviewResponse(BaseModel):
    course_id: str
    material_type: str
    material_id: str
    version: int
    current_review_status: str
    approved_version: int | None = None
    approved_by: str | None = None
    approved_at: str | None = None
