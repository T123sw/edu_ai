from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResourceQualityAssessment(BaseModel):
    """Rule-first quality result for one persisted teaching resource."""

    resource_type: str
    valid: bool
    score: float = Field(ge=0.0, le=1.0)
    satisfied_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class RepairDirective(BaseModel):
    """A bounded repair instruction. It never grants broader tool authority."""

    action: Literal[
        "none",
        "await_artifact",
        "readback",
        "retry_step",
        "supplement_evidence",
        "stop",
    ] = "none"
    reason: str = ""
    failed_audit: Literal[
        "none", "execution", "evidence", "artifact", "persona"
    ] = "none"
    target_step_index: int | None = None
    target_tool: str | None = None
    max_attempts: int = Field(default=0, ge=0, le=1)
    preserve_successful_task_ids: list[str] = Field(default_factory=list)
    requires_user_confirmation: bool = False


class ExecutionAudit(BaseModel):
    valid: bool
    required_tools_satisfied: bool
    forbidden_tools_absent: bool
    tool_order_valid: bool
    duplicate_submission_absent: bool
    failed_tools: list[str] = Field(default_factory=list)


class EvidenceAudit(BaseModel):
    valid: bool
    grounding_valid: bool
    evidence_count: int = 0
    missing_aspects: list[str] = Field(default_factory=list)


class ArtifactAudit(BaseModel):
    valid: bool | None = None
    readable: bool | None = None
    assessments: list[ResourceQualityAssessment] = Field(default_factory=list)


class PersonaAudit(BaseModel):
    valid: bool
    issues: list[str] = Field(default_factory=list)
