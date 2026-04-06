from __future__ import annotations

from pydantic import BaseModel, Field


class GenerationContext(BaseModel):
    conversation_id: str
    resource_type: str
    summary_text: str = ""
    current_topics: list[str] = Field(default_factory=list)
    user_goals: list[str] = Field(default_factory=list)
    confirmed_facts: list[str] = Field(default_factory=list)
    user_claims: list[dict] = Field(default_factory=list)
    assistant_hypotheses: list[dict] = Field(default_factory=list)
    external_evidence: list[dict] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    teaching_issues: list[str] = Field(default_factory=list)
    student_signals: list[str] = Field(default_factory=list)
    evidence_points: list[dict] = Field(default_factory=list)
    selected_doc_ids: list[str] = Field(default_factory=list)
    referenced_artifact_ids: list[str] = Field(default_factory=list)
    current_course_id: str | None = None
    active_artifact_id: str | None = None
    active_artifact_type: str | None = None
    recent_relevant_messages: list[dict] = Field(default_factory=list)
    source_scope: dict = Field(default_factory=dict)
