from __future__ import annotations

from pydantic import BaseModel, Field


class QuizContextSummary(BaseModel):
    topic_summary: str = ""
    settings_summary: str = ""
    weak_points: list[str] = Field(default_factory=list)
    knowledge_points: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    source_scope: list[str] = Field(default_factory=list)


class QuizPreparationResult(BaseModel):
    quiz_intent: str = "unclear"
    topic: str | None = None
    question_count: int | None = None
    question_types: list[str] = Field(default_factory=list)
    difficulty: str | None = None
    include_answers: bool = True
    include_explanations: bool = True
    quiz_context_summary: QuizContextSummary = Field(default_factory=QuizContextSummary)
    constraints: dict = Field(default_factory=dict)
    source_scope: list[str] = Field(default_factory=list)
    knowledge_points: list[str] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)
    missing_critical_fields: list[str] = Field(default_factory=list)
    confidence: str = "low"
    soft_confirm_message: str = ""
