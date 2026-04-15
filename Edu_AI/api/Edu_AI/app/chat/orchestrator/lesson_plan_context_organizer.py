from __future__ import annotations

from typing import Any

from app.chat.domain.generation_context import GenerationContext
from app.chat.domain.lesson_plan_preparation import (
    LessonPlanContextSummary,
    LessonPlanPreparationResult,
)
from app.chat.workflows.lesson_plan.assembler import LessonPlanAssembler


class LessonPlanContextOrganizer:
    _LOW_SIGNAL = {
        "",
        "lesson plan",
        "create lesson plan",
        "generate lesson plan",
        "help me plan a lesson",
        "教案",
        "教学设计",
    }

    def __init__(self, *, assembler: LessonPlanAssembler | None = None):
        self.assembler = assembler or LessonPlanAssembler()

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _is_low_signal(self, value: Any) -> bool:
        text = self._clean(value).lower()
        return not text or text in self._LOW_SIGNAL

    def _pick_topic(self, *, context: GenerationContext, request_question: str) -> str:
        hints = self.assembler.from_generation_context(context)["slot_hints"]
        topic = self._clean(hints.get("topic"))
        if topic:
            return topic
        question = self._clean(request_question)
        if question and not self._is_low_signal(question):
            return question
        return self._clean(context.summary_text)

    def _pick_audience(self, context: GenerationContext) -> str:
        hints = self.assembler.from_generation_context(context)["slot_hints"]
        return self._clean(hints.get("audience"))

    def _pick_duration(self, context: GenerationContext) -> str:
        hints = self.assembler.from_generation_context(context)["slot_hints"]
        return self._clean(hints.get("duration"))

    def _pick_lesson_type(self, context: GenerationContext) -> str:
        hints = self.assembler.from_generation_context(context)["slot_hints"]
        return self._clean(hints.get("lesson_type"))

    def _pick_knowledge_points(self, context: GenerationContext) -> list[str]:
        points: list[str] = []
        for item in list(context.confirmed_facts or []):
            text = self._clean(item)
            if text and text not in points:
                points.append(text)
        return points

    def _pick_key_points(self, context: GenerationContext) -> list[str]:
        points: list[str] = []
        for item in list(context.teaching_issues or []):
            text = self._clean(item)
            if text and text not in points:
                points.append(text)
        for item in list(context.student_signals or []):
            text = self._clean(item)
            if text and text not in points:
                points.append(text)
        for item in list(context.evidence_points or []):
            if isinstance(item, dict):
                text = self._clean(item.get("content"))
            else:
                text = self._clean(item)
            if text and text not in points:
                points.append(text)
        return points

    def _pick_hard_points(self, context: GenerationContext) -> list[str]:
        return self._pick_key_points(context)[:1]

    def _pick_class_profile(self, context: GenerationContext, audience: str) -> list[str]:
        profile: list[str] = []
        if audience:
            profile.append(audience)
        for item in list(context.student_signals or []):
            text = self._clean(item)
            if text and text not in profile:
                profile.append(text)
        return profile

    @staticmethod
    def _source_scope_labels(context: GenerationContext) -> list[str]:
        raw_scope = dict(context.source_scope or {})
        labels: list[str] = []
        if bool(raw_scope.get("from_summary")):
            labels.append("conversation_summary")
        if bool(raw_scope.get("from_memory")):
            labels.append("conversation_memory")
        if bool(raw_scope.get("from_recent_messages")):
            labels.append("recent_messages")
        if bool(raw_scope.get("from_docs")):
            labels.append("selected_docs")
        if bool(raw_scope.get("from_artifacts")):
            labels.append("artifact_context")
        if context.current_course_id:
            labels.append("course_context")
        if not labels:
            labels.append("conversation_summary")
        return labels

    def _build_soft_confirm_message(self, *, topic: str, audience: str, key_points: list[str]) -> str:
        if not topic:
            return ""
        if audience:
            return f"我可以先基于 {topic}，面向 {audience}，整理一版教案。"
        if key_points:
            return f"我可以先基于 {topic} 和当前要点整理一版教案。"
        return f"我可以先基于 {topic} 整理一版教案。"

    def _build_intent(self, *, context: GenerationContext, request_question: str) -> str:
        text = " ".join(
            [
                self._clean(request_question),
                self._clean(context.summary_text),
                " ".join(list(context.user_goals or [])),
            ]
        ).lower()
        if any(marker in text for marker in ("lesson plan", "教案", "教学设计", "lesson")):
            return "generate_lesson_plan"
        return "unclear"

    def organize(self, *, context: GenerationContext, request_question: str) -> LessonPlanPreparationResult:
        assembled = self.assembler.from_generation_context(context)
        topic = self._pick_topic(context=context, request_question=request_question)
        audience = self._pick_audience(context)
        duration = self._pick_duration(context)
        lesson_type = self._pick_lesson_type(context)
        knowledge_points = self._pick_knowledge_points(context)
        key_points = self._pick_key_points(context)
        hard_points = self._pick_hard_points(context)
        class_profile = self._pick_class_profile(context, audience)
        source_scope = self._source_scope_labels(context)
        missing_critical_fields = [] if topic else ["topic"]
        confidence = "high" if topic and (len(key_points) >= 2 or len(knowledge_points) >= 2) else "low"

        summary = LessonPlanContextSummary(
            topic_summary=self._clean(context.summary_text or topic),
            learner_summary=self._clean(audience or ""),
            objective_summary=self._clean(assembled["slot_hints"].get("objective")),
            key_points=key_points,
            hard_points=hard_points,
            constraints=dict(context.constraints or {}),
            source_scope=source_scope,
        )

        return LessonPlanPreparationResult(
            lesson_plan_intent=self._build_intent(context=context, request_question=request_question),
            topic=topic or None,
            audience=audience or None,
            objective=self._clean(assembled["slot_hints"].get("objective")) or None,
            duration=duration or None,
            lesson_type=lesson_type or None,
            lesson_plan_context_summary=summary,
            constraints=dict(context.constraints or {}),
            source_scope=source_scope,
            knowledge_points=knowledge_points,
            key_points=key_points,
            hard_points=hard_points,
            teaching_methods=[],
            class_profile=class_profile,
            resource_constraints=[],
            style_constraints=[],
            missing_critical_fields=missing_critical_fields,
            confidence=confidence,
            soft_confirm_message=self._build_soft_confirm_message(
                topic=topic,
                audience=audience,
                key_points=key_points,
            ),
        )
