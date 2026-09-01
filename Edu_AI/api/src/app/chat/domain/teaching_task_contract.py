"""Versioned, UI-authoritative contract for teacher Agent work."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.chat.domain.task_domain import TaskDomain


TaskIntent = Literal[
    "qa", "generate_single", "prepare_bundle", "modify", "confirm", "status", "cancel"
]
SourceMode = Literal["selected_documents", "course_auto", "none"]
Policy = Literal["required", "allowed", "disabled"]
ResourceType = Literal[
    "report", "lesson_plan", "quiz", "blog", "flashcard", "graph", "game", "classroom"
]


class ContractFieldEvidence(BaseModel):
    origin: Literal["user", "ui", "state", "default", "inferred"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    value: Any = None


class ContractAmbiguity(BaseModel):
    field: str
    impact: Literal["low", "medium", "high"]
    reason: str
    candidates: list[str] = Field(default_factory=list)


class ClarificationDecision(BaseModel):
    required: bool = False
    field: str | None = None
    question: str | None = None
    budget: int = Field(default=1, ge=0, le=1)
    reason: str = ""


class TeachingTaskContract(BaseModel):
    """The only model-derived artifact that may influence plan compilation.

    Capability-derived fields are normalized after extraction and cannot be
    weakened by the message or by a model response.
    """

    schema_version: Literal["2026-08-09", "2026-08-09.v2", "2026-08-10.v3"] = "2026-08-10.v3"
    actor_role: Literal["teacher", "student"] = "teacher"
    intent: TaskIntent = "qa"
    task_domain: TaskDomain = "none"
    topic: str = ""
    resource_types: list[ResourceType] = Field(default_factory=list)
    audience: str | None = None
    lesson_duration: int | None = None
    teaching_goals: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    source_mode: SourceMode = "none"
    selected_document_ids: list[str] = Field(default_factory=list)
    web_policy: Policy = "disabled"
    image_policy: Policy = "disabled"
    confirmation_policy: Literal["required", "optional", "none"] = "none"
    conversation_refs: dict = Field(default_factory=dict)
    field_evidence: dict[str, ContractFieldEvidence] = Field(default_factory=dict)
    ambiguities: list[ContractAmbiguity] = Field(default_factory=list)
    clarification: ClarificationDecision = Field(default_factory=ClarificationDecision)

    @model_validator(mode="after")
    def normalize(self):
        self.topic = self.topic.strip()
        self.selected_document_ids = list(dict.fromkeys(
            str(value).strip() for value in self.selected_document_ids if str(value).strip()
        ))
        self.resource_types = list(dict.fromkeys(self.resource_types))
        if self.source_mode == "selected_documents" and not self.selected_document_ids:
            raise ValueError("selected_documents requires selected_document_ids")
        if self.source_mode != "selected_documents":
            self.selected_document_ids = []
        return self

    @property
    def requires_rag(self) -> bool:
        return self.source_mode in {"selected_documents", "course_auto"}

    @property
    def requires_web(self) -> bool:
        return self.web_policy == "required"

    @property
    def requires_images(self) -> bool:
        return self.image_policy == "required"

    @property
    def contract_hash(self) -> str:
        payload = self.model_dump(
            mode="json",
            exclude={"conversation_refs", "field_evidence", "ambiguities"},
        )
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]
