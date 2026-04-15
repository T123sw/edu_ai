from __future__ import annotations

from app.chat.domain.lesson_plan_preparation import LessonPlanPreparationResult


class LessonPlanReadinessJudge:
    def _has_outline_basis(self, result: LessonPlanPreparationResult) -> bool:
        if str(result.objective or "").strip():
            return True
        if str(result.audience or "").strip() and str(result.duration or "").strip():
            return True
        if len(list(result.knowledge_points or [])) >= 2:
            return True
        if len(list(result.key_points or [])) >= 1:
            return True
        if len(list(result.hard_points or [])) >= 1:
            return True
        if str(result.lesson_plan_context_summary.topic_summary or "").strip():
            return True
        return False

    def judge(self, result: LessonPlanPreparationResult, *, entry_mode: str) -> dict:
        if not str(result.topic or "").strip():
            return {
                "action": "ask_critical_gap",
                "question": "这份教案主要想围绕哪个主题来写？",
                "missing_critical_fields": ["topic"],
            }

        if self._has_outline_basis(result):
            action = "weak_soft_confirm" if str(entry_mode or "").strip().lower() == "button" else "strong_soft_confirm"
            return {
                "action": action,
                "question": "",
                "missing_critical_fields": [],
                "soft_confirm_message": str(result.soft_confirm_message or "").strip(),
            }

        return {
            "action": "ask_objective_or_outline_basis",
            "question": "你希望这份教案更偏向明确教学目标，还是先给我一些大纲或要点？",
            "missing_critical_fields": ["objective_or_outline_basis"],
        }
