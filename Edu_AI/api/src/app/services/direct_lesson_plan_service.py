"""Durable direct lesson-plan generation adapter."""

from __future__ import annotations

from typing import Any

from app.services.generation_task_handlers import GenerationExecutionContext


class DirectLessonPlanService:
    def __init__(self, *, engine=None) -> None:
        if engine is None:
            from app.chat.application.lesson_plan_service_v2 import (
                build_default_lesson_plan_engine,
            )

            engine = build_default_lesson_plan_engine()
        self.engine = engine

    def generate(
        self,
        payload,
        *,
        job_id: str,
        config_snapshot_id: str,
        execution_context: GenerationExecutionContext,
    ) -> dict[str, Any]:
        topic = str(getattr(payload, "topic", "") or "").strip()
        audience = str(getattr(payload, "audience", "") or "").strip()
        duration = max(
            1, int(getattr(payload, "duration_minutes", 45) or 45)
        )
        objectives = [
            str(item).strip()
            for item in list(getattr(payload, "objectives", []) or [])
            if str(item).strip()
        ]
        lesson_type = str(
            getattr(payload, "lesson_type", "knowledge_building")
            or "knowledge_building"
        ).strip()
        source_context = execution_context.source.context_text
        state = {
            "generation_ready": True,
            "conversation_id": job_id,
            "lesson_plan_slots": {
                "topic": topic,
                "audience": audience,
                "duration": f"{duration} minutes",
                "objective": "\n".join(objectives),
                "lesson_type": lesson_type,
            },
            "lesson_plan_preparation_result": {
                "topic": topic,
                "audience": audience,
                "duration": f"{duration} minutes",
                "objectives": objectives,
                "lesson_type": lesson_type,
                "special_requirements": str(
                    getattr(payload, "special_requirements", "") or ""
                ).strip(),
                "source_context": source_context,
            },
            "gathered_context": {
                "source_context": source_context,
                "source_snapshot": execution_context.source.to_snapshot(),
            },
            "lesson_plan_outline": None,
        }
        outline_result = dict(self.engine.invoke(state))
        outline = outline_result.get("lesson_plan_outline")
        if not isinstance(outline, dict):
            return {
                "status": "failed",
                "artifacts": [],
                "error": "lesson plan engine returned no outline",
            }
        content_result = dict(
            self.engine.invoke(
                {
                    **state,
                    "lesson_plan_outline": outline,
                    "human_feedback": "confirm",
                }
            )
        )
        return {
            "status": content_result.get("status", "completed"),
            "artifacts": list(content_result.get("artifacts") or []),
        }


def build_default_direct_lesson_plan_service() -> DirectLessonPlanService:
    return DirectLessonPlanService()
