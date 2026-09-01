from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.chat.domain.resource_quality import (
    ArtifactAudit,
    EvidenceAudit,
    ExecutionAudit,
    PersonaAudit,
    RepairDirective,
)


class VerificationReport(BaseModel):
    plan_compliance: bool
    required_tools_satisfied: bool
    forbidden_tools_absent: bool
    tool_order_valid: bool
    duplicate_submission_absent: bool
    grounding_valid: bool
    artifact_contract_valid: bool
    artifact_readable: bool | None = None
    persona_valid: bool = True
    execution_audit: ExecutionAudit | None = None
    evidence_audit: EvidenceAudit | None = None
    artifact_audit: ArtifactAudit | None = None
    persona_audit: PersonaAudit | None = None
    repair_directive: RepairDirective = Field(default_factory=RepairDirective)
    warnings: list[str] = Field(default_factory=list)
    decision: Literal["pass", "partial", "retry", "fail"]
