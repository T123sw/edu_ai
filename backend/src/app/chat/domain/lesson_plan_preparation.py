from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LessonPlanContextSummary(BaseModel):
    topic_summary: str = ""
    learner_summary: str = ""
    objective_summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    hard_points: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    source_scope: list[str] = Field(default_factory=list)


class LessonPlanPreparationResult(BaseModel):
    lesson_plan_intent: str = "unclear"
    topic: str | None = None
    audience: str | None = None
    objective: str | None = None
    duration: str | None = None
    lesson_type: str | None = None
    assessment_method: str = ""
    homework_preference: str = ""
    lesson_plan_context_summary: LessonPlanContextSummary = Field(default_factory=LessonPlanContextSummary)
    constraints: dict[str, Any] = Field(default_factory=dict)
    source_scope: list[str] = Field(default_factory=list)
    knowledge_points: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    hard_points: list[str] = Field(default_factory=list)
    teaching_methods: list[str] = Field(default_factory=list)
    class_profile: list[str] = Field(default_factory=list)
    resource_constraints: list[str] = Field(default_factory=list)
    style_constraints: list[str] = Field(default_factory=list)
    missing_critical_fields: list[str] = Field(default_factory=list)
    confidence: str = "low"
    soft_confirm_message: str = ""
