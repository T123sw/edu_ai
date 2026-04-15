from __future__ import annotations

from typing import Any

from app.chat.domain.generation_context import GenerationContext


class LessonPlanAssembler:
    _LOW_SIGNAL = {
        "",
        "create lesson plan",
        "generate lesson plan",
        "make a lesson plan",
        "help me plan a lesson",
        "lesson plan",
        "教案",
        "教学设计",
    }

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _is_low_signal(self, value: Any) -> bool:
        text = self._clean(value).lower()
        return not text or text in self._LOW_SIGNAL

    def _pick_topic(self, context: GenerationContext) -> str:
        for topic in list(context.current_topics or []):
            text = self._clean(topic)
            if text and not self._is_low_signal(text):
                return text

        summary = self._clean(context.summary_text)
        if summary and not self._is_low_signal(summary):
            return summary

        for message in list(context.recent_relevant_messages or []):
            if self._clean((message or {}).get("role")) != "user":
                continue
            text = self._clean((message or {}).get("content"))
            if text and not self._is_low_signal(text):
                return text
        return ""

    def _pick_audience(self, context: GenerationContext) -> str:
        constraints = dict(context.constraints or {})
        for key in ("audience", "target_audience", "class_level"):
            text = self._clean(constraints.get(key))
            if text:
                return text
        return ""

    def _pick_duration(self, context: GenerationContext) -> str:
        constraints = dict(context.constraints or {})
        for key in ("duration", "lesson_duration", "class_duration", "time"):
            text = self._clean(constraints.get(key))
            if text:
                return text
        return ""

    def _pick_objective(self, context: GenerationContext) -> str:
        constraints = dict(context.constraints or {})
        text = self._clean(constraints.get("objective"))
        if text:
            return text
        for goal in list(context.user_goals or []):
            text = self._clean(goal)
            if text and not self._is_low_signal(text):
                return text
        return ""

    def _pick_lesson_type(self, context: GenerationContext) -> str:
        constraints = dict(context.constraints or {})
        for key in ("lesson_type", "lesson_mode", "type"):
            text = self._clean(constraints.get(key))
            if text:
                return text
        return ""

    def _build_slot_hints(self, context: GenerationContext) -> dict[str, str]:
        return {
            "topic": self._pick_topic(context),
            "audience": self._pick_audience(context),
            "duration": self._pick_duration(context),
            "objective": self._pick_objective(context),
            "lesson_type": self._pick_lesson_type(context),
        }

    def from_generation_context(self, context: GenerationContext) -> dict[str, Any]:
        return {
            "summary": context.summary_text,
            "current_topics": list(context.current_topics or []),
            "user_goals": list(context.user_goals or []),
            "confirmed_facts": list(context.confirmed_facts or []),
            "constraints": dict(context.constraints or {}),
            "teaching_issues": list(context.teaching_issues or []),
            "student_signals": list(context.student_signals or []),
            "evidence_points": list(context.evidence_points or []),
            "recent_messages": list(context.recent_relevant_messages or []),
            "source_scope": dict(context.source_scope or {}),
            "slot_hints": self._build_slot_hints(context),
        }
