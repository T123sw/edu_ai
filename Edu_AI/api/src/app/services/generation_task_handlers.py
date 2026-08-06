from __future__ import annotations

from collections.abc import Callable, Mapping
from types import SimpleNamespace
from typing import Any

from app.services.durable_task_handlers import (
    DurableExecutionContext,
    DurableTaskHandlerRegistry,
)
from core.course_storage import CourseStorageManager


def _default_service_factories() -> dict[str, Callable[[], Any]]:
    from app.chat.application.blog_generation_adapter_v2 import (
        BlogGenerationAdapterV2,
    )
    from app.chat.application.knowledge_base_direct_flashcard_service_v2 import (
        build_default_knowledge_base_direct_flashcard_service_v2,
    )
    from app.chat.application.knowledge_base_direct_game_service_v2 import (
        build_default_knowledge_base_direct_game_service_v2,
    )
    from app.chat.application.knowledge_base_direct_graph_service_v2 import (
        build_default_knowledge_base_direct_graph_service_v2,
    )
    from app.chat.application.knowledge_base_direct_ppt_service_v2 import (
        build_default_knowledge_base_direct_ppt_service_v2,
    )
    from app.chat.application.knowledge_base_direct_quiz_service_v2 import (
        build_default_knowledge_base_direct_quiz_service_v2,
    )
    from app.chat.application.knowledge_base_direct_report_service_v2 import (
        build_default_knowledge_base_direct_report_service_v2,
    )

    return {
        "report": build_default_knowledge_base_direct_report_service_v2,
        "blog": BlogGenerationAdapterV2,
        "quiz": build_default_knowledge_base_direct_quiz_service_v2,
        "ppt": build_default_knowledge_base_direct_ppt_service_v2,
        "flashcard": build_default_knowledge_base_direct_flashcard_service_v2,
        "graph": build_default_knowledge_base_direct_graph_service_v2,
        "game": build_default_knowledge_base_direct_game_service_v2,
        "lesson_plan": _LessonPlanGenerationAdapter,
    }


class _LessonPlanGenerationAdapter:
    def generate(
        self,
        payload,
        *,
        job_id: str,
        config_snapshot_id: str,
    ) -> dict[str, Any]:
        from app.chat.agents.report_generation import get_fallback_llm
        from app.chat.application.lesson_plan_service_v2 import (
            LessonPlanGenerationEngine,
        )

        engine = LessonPlanGenerationEngine(llm=get_fallback_llm())
        subject = str(getattr(payload, "subject", "") or "").strip()
        duration = int(getattr(payload, "duration_minutes", 45) or 45)
        state = {
            "lesson_plan_slots": {
                "topic": subject,
                "audience": str(getattr(payload, "grade", "") or ""),
                "duration": f"{duration}分钟",
                "lesson_type": "知识讲解",
            },
            "lesson_plan_preparation_result": {},
            "lesson_plan_outline": {
                "topic": subject,
                "outline_markdown": str(
                    getattr(payload, "confirmed_outline", "") or ""
                ),
            },
            "conversation_id": str(
                getattr(payload, "conversation_id", "") or job_id
            ),
        }
        result = engine._generate_content(state=state)
        return {
            "status": result.get("status", "completed"),
            "artifacts": result.get("artifacts", []),
        }


class GenerationTaskHandler:
    def __init__(
        self,
        *,
        course_storage_manager: CourseStorageManager | None = None,
        service_factories: Mapping[str, Callable[[], Any]] | None = None,
    ) -> None:
        self.course_storage_manager = (
            course_storage_manager or CourseStorageManager()
        )
        self.service_factories = dict(
            service_factories or _default_service_factories()
        )

    def __call__(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        resource_type = str(command.get("resource_type") or "").strip()
        factory = self.service_factories.get(resource_type)
        if factory is None:
            raise ValueError(f"unsupported generation resource {resource_type}")
        payload = self._build_payload(command, context)
        context.progress(5, "generating", "正在根据课程资料生成内容")
        result = dict(
            factory().generate(
                payload,
                job_id=context.task_id,
                config_snapshot_id=context.config_snapshot_id or "",
            )
        )
        if result.get("result_ref"):
            return result
        return self._publish_artifact(
            command=command,
            context=context,
            resource_type=resource_type,
            result=result,
        )

    @staticmethod
    def _build_payload(
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> SimpleNamespace:
        resource_type = str(command.get("resource_type") or "").strip()
        config = dict(command.get("config") or {})
        base: dict[str, Any] = {
            "owner": context.owner_user_id,
            "course_id": str(command.get("course_id") or context.course_id or ""),
            "scope_type": str(command.get("scope_type") or "course"),
            "scope_id": command.get("scope_id"),
            "selected_doc_ids": list(command.get("selected_doc_ids") or []),
            "material_id": str(command.get("material_id") or ""),
        }
        if resource_type == "report":
            base.update(config)
        elif resource_type == "quiz":
            base.update(
                {
                    "quiz_config": dict(
                        config.get("quiz_config") or config
                    ),
                    "prompt_draft": config.get("prompt_draft"),
                    "final_user_prompt": config.get("final_user_prompt"),
                }
            )
        elif resource_type == "game":
            base["game_type"] = config.get("game_type")
        elif resource_type == "flashcard":
            base["flashcard_config"] = dict(
                config.get("flashcard_config") or config
            )
        elif resource_type == "graph":
            base["graph_config"] = {
                "title": config.get("title"),
                "max_depth": config.get("max_depth"),
            }
        elif resource_type == "blog":
            base["topic"] = config.get("topic") or config.get("title")
        elif resource_type == "ppt":
            base.update(
                {
                    "draft_id": config.get("draft_id"),
                    "confirm": bool(config.get("confirm", True)),
                    "outline": config.get("outline"),
                }
            )
        elif resource_type == "lesson_plan":
            base.update(config)
        return SimpleNamespace(**base)

    def _publish_artifact(
        self,
        *,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
        resource_type: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        artifacts = [
            item
            for item in list(result.get("artifacts") or [])
            if isinstance(item, dict)
            and str(item.get("artifact_type") or "").strip() == resource_type
        ]
        if not artifacts:
            return {
                **result,
                "saved": False,
                "error": "generator returned no publishable artifact",
                "result_ref": {},
            }
        artifact = dict(artifacts[0])
        material_id = str(command.get("material_id") or "").strip()
        course_id = str(command.get("course_id") or context.course_id or "").strip()
        saved = bool(
            self.course_storage_manager.save_generated_material(
                course_id=course_id,
                material_type=resource_type,
                material_id=material_id,
                scope_type=str(command.get("scope_type") or "course"),
                scope_id=str(command.get("scope_id") or "").strip() or None,
                owner_user_id=context.owner_user_id,
                source_job_id=context.task_id,
                config_snapshot_id=context.config_snapshot_id,
                material_data={
                    "title": str(artifact.get("title") or resource_type),
                    "content": artifact.get("content"),
                    "generation_state": dict(
                        artifact.get("generation_state") or {}
                    ),
                    "source": {
                        "selected_doc_ids": list(
                            command.get("selected_doc_ids") or []
                        )
                    },
                },
            )
        )
        return {
            **result,
            "saved": saved,
            "error": None if saved else "course material manifest write failed",
            "result_ref": {
                "resource_type": (
                    "course_material" if saved else "generated_artifact"
                ),
                "course_id": course_id,
                "material_type": resource_type,
                "material_id": material_id,
            },
        }


def register_generation_task_handlers(
    registry: DurableTaskHandlerRegistry,
    *,
    handler: GenerationTaskHandler | None = None,
) -> GenerationTaskHandler:
    active_handler = handler or GenerationTaskHandler()
    for resource_type in (
        "report",
        "lesson_plan",
        "blog",
        "quiz",
        "ppt",
        "flashcard",
        "graph",
        "game",
    ):
        registry.register(f"{resource_type}_direct", 1, active_handler)
    return active_handler
