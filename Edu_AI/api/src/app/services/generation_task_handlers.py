from __future__ import annotations

from collections.abc import Callable, Mapping
from types import SimpleNamespace
from typing import Any

from app.services.durable_task_handlers import (
    DurableExecutionContext,
    DurableTaskHandlerRegistry,
)
from core.course_storage import CourseStorageManager


class _AgentReportGenerationAdapter:
    def generate(
        self,
        payload,
        *,
        job_id: str,
        config_snapshot_id: str,
    ) -> dict[str, Any]:
        from app.chat.agents.report_generation import build_report_markdown
        from app.chat.runtime.agent_tools.handlers.outline_parser import (
            parse_report_outline,
        )
        from app.chat.skill_manager import SkillManager
        from app.chat.workflows.report.image_downloader import (
            resolve_async_localization,
            start_async_localization,
        )
        from app.chat.workflows.report.image_injector import (
            inject_images_into_report,
            inject_report_images_from_rag,
        )

        subject = str(getattr(payload, "subject", "") or "").strip()
        images = list(getattr(payload, "accumulated_images", []) or [])
        already_localized = bool(images) and all(
            item.get("_localized") for item in images
        )
        localization_future = None
        if images and not already_localized:
            localization_future = start_async_localization(
                images,
                owner=getattr(payload, "owner", None),
                course_id=getattr(payload, "course_id", None),
            )
        body, checkpoint = build_report_markdown(
            skill_manager=SkillManager(),
            slots={
                "core_topic": subject,
                "focus_area": str(
                    getattr(payload, "focus", "") or ""
                ).strip(),
                "length_requirement": str(
                    getattr(payload, "length_hint", "") or ""
                ).strip(),
            },
            outline=parse_report_outline(
                str(getattr(payload, "confirmed_outline", "") or "")
            ),
            mode="fast",
        )
        if already_localized:
            assets = images
        elif localization_future is not None:
            assets = resolve_async_localization(
                localization_future,
                images,
                extra_timeout_s=5.0,
            )
        else:
            assets = []
        if body and assets:
            body = inject_images_into_report(
                body,
                assets,
                max_images=min(len(assets), 6),
            )
        elif (
            body
            and bool(getattr(payload, "allow_rag", False))
            and list(getattr(payload, "selected_doc_ids", []) or [])
        ):
            body = inject_report_images_from_rag(
                body,
                allow_rag=True,
                selected_doc_ids=list(payload.selected_doc_ids),
                owner=getattr(payload, "owner", None),
                query_text=subject,
            )
        localized_count = sum(
            1
            for item in assets
            if str(item.get("url") or "").startswith("/api/images/")
        )
        return {
            "status": "completed",
            "artifacts": [
                {
                    "artifact_type": "report",
                    "title": subject,
                    "content": body,
                    "generation_state": checkpoint,
                    "visual_assets_count": len(images),
                    "visual_assets_localized": localized_count,
                }
            ],
        }


class _AgentQuizGenerationAdapter:
    def generate(
        self,
        payload,
        *,
        job_id: str,
        config_snapshot_id: str,
    ) -> dict[str, Any]:
        from app.chat.agents.report_generation import get_fallback_llm
        from app.chat.workflows.quiz.generator import QuizGenerator

        selected_doc_ids = list(
            getattr(payload, "selected_doc_ids", []) or []
        )
        generator = QuizGenerator(llm=get_fallback_llm())
        artifact = generator.generate(
            preparation={
                "topic": str(getattr(payload, "subject", "") or ""),
                "question_count": int(
                    getattr(payload, "question_count", 10) or 10
                ),
                "question_types": list(
                    getattr(payload, "question_types", []) or []
                ),
                "difficulty": str(
                    getattr(payload, "difficulty", "medium") or "medium"
                ),
                "knowledge_points": [],
                "weak_points": [],
                "source_scope": selected_doc_ids,
            },
            context_summary="",
            conversation_id=str(
                getattr(payload, "conversation_id", "") or job_id
            ),
            owner=getattr(payload, "owner", None),
            allow_rag=bool(getattr(payload, "allow_rag", False)),
            selected_doc_ids=selected_doc_ids,
        )
        return {"status": "completed", "artifacts": [artifact]}


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
        agent_service_factories: Mapping[
            str, Callable[[], Any]
        ] | None = None,
    ) -> None:
        self.course_storage_manager = (
            course_storage_manager or CourseStorageManager()
        )
        self.service_factories = dict(
            service_factories or _default_service_factories()
        )
        self.agent_service_factories = dict(
            agent_service_factories
            or {
                "report": _AgentReportGenerationAdapter,
                "quiz": _AgentQuizGenerationAdapter,
                "lesson_plan": _LessonPlanGenerationAdapter,
            }
        )

    def __call__(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        resource_type = str(command.get("resource_type") or "").strip()
        config = dict(command.get("config") or {})
        is_agent_entrypoint = config.get("entrypoint") == "agent"
        factory = (
            self.agent_service_factories.get(resource_type)
            if is_agent_entrypoint
            else self.service_factories.get(resource_type)
        )
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
        if config.get("entrypoint") == "agent":
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
