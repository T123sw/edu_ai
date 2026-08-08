"""Durable direct lesson-plan generation adapter."""

from __future__ import annotations

from typing import Any

from app.services.generation_task_handlers import GenerationExecutionContext


class DirectLessonPlanService:
    def __init__(self, *, engine=None, visual_pipeline=None, llm=None) -> None:
        if engine is None:
            from app.chat.application.lesson_plan_service_v2 import (
                build_default_lesson_plan_engine,
            )

            engine = build_default_lesson_plan_engine()
        self.engine = engine
        self.visual_pipeline = visual_pipeline
        self.llm = llm

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
        teaching_process = str(
            getattr(payload, "teaching_process", "") or ""
        ).strip()
        special_requirements = str(
            getattr(payload, "special_requirements", "") or ""
        ).strip()
        source_context = execution_context.source.context_text
        visual_snapshot: dict[str, Any] = {}
        if bool(getattr(payload, "include_visuals", False)):
            pipeline = self.visual_pipeline
            llm = self.llm
            if pipeline is None:
                from app.chat.application.knowledge_base_direct_report_service_v2 import (
                    _build_default_visual_pipeline,
                )

                pipeline = _build_default_visual_pipeline()
            if llm is None:
                from app.chat.agents.report_generation import get_fallback_llm

                llm = get_fallback_llm()
            try:
                brief = pipeline.plan_with_model(
                    llm,
                    resource_type="lesson_plan",
                    topic=topic,
                    source_context=source_context,
                )
                visual_result = pipeline.run(
                    brief,
                    course_id=execution_context.course_id,
                    owner=execution_context.user_id or None,
                    selected_document_ids=list(
                        getattr(payload, "selected_doc_ids", []) or []
                    ),
                )
                visual_snapshot = dict(visual_result.to_snapshot())
            except Exception as exc:
                visual_snapshot = {"error": str(exc), "selected": []}
        state = {
            "generation_ready": True,
            "conversation_id": job_id,
            "lesson_plan_slots": {
                "topic": topic,
                "audience": audience,
                "duration": f"{duration} minutes",
                "objective": "\n".join(objectives),
                "lesson_type": lesson_type,
                "teaching_process": teaching_process,
                "special_requirements": special_requirements,
                "visual_plan": visual_snapshot,
            },
            "lesson_plan_preparation_result": {
                "topic": topic,
                "audience": audience,
                "duration": f"{duration} minutes",
                "objectives": objectives,
                "lesson_type": lesson_type,
                "teaching_process": teaching_process,
                "special_requirements": special_requirements,
                "visual_plan": visual_snapshot,
                "source_context": source_context,
            },
            "gathered_context": {
                "source_context": source_context,
                "source_snapshot": execution_context.source.to_snapshot(),
                "teaching_process": teaching_process,
                "special_requirements": special_requirements,
                "visual_plan": visual_snapshot,
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
        artifacts: list[dict[str, Any]] = []
        for raw in list(content_result.get("artifacts") or []):
            artifact = dict(raw)
            content = artifact.get("content")
            selected_visuals = list(visual_snapshot.get("selected") or [])
            if isinstance(content, dict) and selected_visuals:
                artifact["content"] = {**content, "visuals": selected_visuals}
            artifact["generation_state"] = {
                **dict(artifact.get("generation_state") or {}),
                "visuals": visual_snapshot,
            }
            artifacts.append(artifact)
        return {
            "status": content_result.get("status", "completed"),
            "artifacts": artifacts,
        }


def build_default_direct_lesson_plan_service() -> DirectLessonPlanService:
    return DirectLessonPlanService()
