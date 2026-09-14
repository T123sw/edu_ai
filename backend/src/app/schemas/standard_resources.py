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
    standard_kinds: list[Literal["classroom", "study_guide", "practice"]] = Field(
        default_factory=lambda: ["classroom", "study_guide", "practice"]
    )
    mode: Literal["fill_missing", "repair_rejected", "regenerate_all"] = "fill_missing"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=160)
    graph_version: str | None = Field(default=None, max_length=128)


class StandardResourceBatchPreviewRequest(BaseModel):
    leaf_ids: list[str] = Field(default_factory=list, max_length=200)
    standard_kinds: list[Literal["classroom", "study_guide", "practice"]] = Field(
        default_factory=lambda: ["classroom", "study_guide", "practice"]
    )
    mode: Literal["fill_missing", "repair_rejected", "regenerate_all"] = "fill_missing"


class StandardResourcePlanItemResponse(BaseModel):
    leaf_id: str
    leaf_title: str
    standard_kind: str
    material_type: str
    material_id: str
    action: str
    reason: str
    current_version: int | None = None
    approved_version: int | None = None
    content_hash: str | None = None


class StandardResourceBatchPreviewResponse(BaseModel):
    course_id: str
    graph_version: str
    mode: str
    standard_kinds: list[str]
    generate_items: int
    repair_items: int
    regenerate_items: int
    kept_items: int
    blocked_items: int
    actionable_items: int
    items: list[StandardResourcePlanItemResponse]


class StandardResourceBatchItemResponse(BaseModel):
    batch_item_id: str
    batch_id: str
    leaf_id: str
    leaf_title: str
    standard_kind: str
    material_type: str
    material_id: str
    action: str = "generate"
    base_version: int | None = None
    material_version: int | None = None
    content_hash: str | None = None
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
    idempotency_key: str
    graph_version: str
    generation_mode: str
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
    expected_version: int = Field(ge=1)
    expected_content_hash: str = Field(min_length=1, max_length=128)
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
