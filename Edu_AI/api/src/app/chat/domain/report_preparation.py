from __future__ import annotations

from pydantic import BaseModel, Field


class ReportContextSummary(BaseModel):
    subject_summary: str = ""
    focus_summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    evidence_points: list[dict] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    source_scope: list[str] = Field(default_factory=list)


class ReportPreparationResult(BaseModel):
    report_intent: str = "unclear"
    report_subject: str | None = None
    report_focus: str | None = None
    preparation_source: str = ""
    preparation_model: str = ""
    report_context_summary: ReportContextSummary = Field(default_factory=ReportContextSummary)
    key_points: list[str] = Field(default_factory=list)
    evidence_points: list[dict] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    source_scope: dict = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)
    missing_critical_fields: list[str] = Field(default_factory=list)
    confidence: str = "low"
    soft_confirm_message: str = ""
    followup_candidates: list[str] = Field(default_factory=list)
