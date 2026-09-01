from __future__ import annotations

from pydantic import BaseModel, Field


class StatusCardEvidenceDetail(BaseModel):
    content: str
    source_type: str = "assistant_message"
    confidence: str = "low"
    source_message_count: int = 0


class StatusCardViewModel(BaseModel):
    mode: str = "chat"
    status_label: str = "普通对话"
    workflow_label: str | None = None
    topics: list[str] = Field(default_factory=list)
    goal: str | None = None
    issues: list[str] = Field(default_factory=list)
    confirmed_facts: list[str] = Field(default_factory=list)
    student_signals: list[str] = Field(default_factory=list)
    evidence_points: list[str] = Field(default_factory=list)
    evidence_details: list[StatusCardEvidenceDetail] = Field(default_factory=list)
    extra_constraints: list[str] = Field(default_factory=list)
    source_labels: list[str] = Field(default_factory=lambda: ["当前会话"])
    active_artifact_label: str | None = None
    waiting_label: str | None = None
    suggested_actions: list[str] = Field(default_factory=list)
    audience: str | None = None
    tone: str | None = None
    length: str | None = None
    grade_level: str | None = None
    subject: str | None = None
    allow_rag: bool = False
    allow_web: bool = False
    summary_hint: str | None = None
