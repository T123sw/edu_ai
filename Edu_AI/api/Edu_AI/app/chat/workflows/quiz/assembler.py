from __future__ import annotations

from typing import Any

from app.chat.domain.generation_context import GenerationContext


class QuizAssembler:
    _LOW_SIGNAL_PHRASES = {
        "",
        "quiz",
        "quiz generation",
        "generate quiz",
        "出题",
        "生成测验",
        "帮我出题",
        "帮我出一份测验",
    }

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _is_low_signal(self, value: Any) -> bool:
        text = self._clean(value).lower()
        return not text or text in self._LOW_SIGNAL_PHRASES

    def _pick_topic(self, context: GenerationContext) -> str:
        constraints = dict(context.constraints or {})
        for key in ("topic", "quiz_topic", "subject"):
            text = self._clean(constraints.get(key))
            if text and not self._is_low_signal(text):
                return text
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

    def _normalize_question_types(self, value: Any) -> list[str]:
        text = self._clean(value).lower()
        if not text:
            return []
        normalized: list[str] = []
        type_markers = (
            ("choice", ("choice", "choices", "single choice", "multiple choice", "单选", "多选", "选择")),
            ("blank", ("blank", "fill in the blank", "填空")),
            ("short", ("short", "short answer", "简答")),
        )
        for normalized_type, markers in type_markers:
            if any(marker in text for marker in markers) and normalized_type not in normalized:
                normalized.append(normalized_type)
        return normalized

    def _build_slot_hints(self, context: GenerationContext) -> dict[str, Any]:
        constraints = dict(context.constraints or {})
        return {
            "topic": self._pick_topic(context),
            "question_count": self._clean(constraints.get("question_count") or constraints.get("count")),
            "question_types": self._normalize_question_types(
                constraints.get("question_types") or constraints.get("question_type")
            ),
            "difficulty": self._clean(constraints.get("difficulty") or constraints.get("difficulty_level")),
            "include_answers": constraints.get("include_answers"),
            "include_explanations": constraints.get("include_explanations"),
        }

    def _source_scope_labels(self, context: GenerationContext) -> list[str]:
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

    def _build_context_summary(self, context: GenerationContext) -> dict[str, Any]:
        weak_points: list[str] = []
        for item in list(context.student_signals or []):
            text = self._clean(item)
            if text and text not in weak_points:
                weak_points.append(text)
        knowledge_points: list[str] = []
        for item in list(context.confirmed_facts or []):
            text = self._clean(item)
            if text and text not in knowledge_points:
                knowledge_points.append(text)
        return {
            "topic_summary": self._pick_topic(context) or self._clean(context.summary_text),
            "settings_summary": self._clean(" ".join(list(context.user_goals or []))),
            "weak_points": weak_points,
            "knowledge_points": knowledge_points,
            "constraints": dict(context.constraints or {}),
            "source_scope": self._source_scope_labels(context),
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
            "recent_messages": list(context.recent_relevant_messages or []),
            "source_scope": self._source_scope_labels(context),
            "slot_hints": self._build_slot_hints(context),
            "context_summary": self._build_context_summary(context),
        }
