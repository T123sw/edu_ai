from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType, SimpleNamespace
from typing import Any

from app.services.durable_task_handlers import (
    DurableExecutionContext,
    DurableTaskHandlerRegistry,
)
from core.course_storage import CourseStorageManager
from app.services.generation_source_resolver import (
    GenerationSourceResolver,
    ResolvedGenerationSource,
    SourceDocumentRecord,
)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class GenerationExecutionContext:
    job_id: str
    course_id: str
    user_id: str
    source: ResolvedGenerationSource
    config: Mapping[str, object]


class _CourseDocumentCatalog:
    def __init__(self, manager: CourseStorageManager) -> None:
        self._manager = manager

    @staticmethod
    def _record(course_id: str, item: Mapping[str, Any]) -> SourceDocumentRecord:
        return SourceDocumentRecord(
            course_id=course_id,
            document_id=str(item.get("id") or ""),
            name=str(item.get("filename") or item.get("name") or ""),
            status=str(item.get("status") or ""),
            rag_index_key=str(item.get("rag_index_key") or ""),
            chunk_count=int(item.get("chunk_count") or 0),
        )

    def list_for_course(self, course_id: str) -> list[SourceDocumentRecord]:
        return [
            self._record(course_id, item)
            for item in self._manager.get_knowledge_base_index(course_id)
            if str(item.get("id") or "").strip()
        ]

    def get_by_public_id(self, document_id: str) -> SourceDocumentRecord | None:
        normalized = str(document_id or "").strip()
        for course_dir in self._manager.courses_dir.iterdir():
            if not course_dir.is_dir():
                continue
            course_id = course_dir.name
            for item in self._manager.get_knowledge_base_index(course_id):
                if str(item.get("id") or "").strip() == normalized:
                    return self._record(course_id, item)
        return None

    def get_personal_by_public_id(
        self,
        document_id: str,
        *,
        course_id: str,
        owner: str,
    ) -> SourceDocumentRecord | None:
        """Resolve a teacher-owned legacy/personal RAG document safely.

        The source panel intentionally combines scoped course documents with
        the teacher's personal RAG catalog. Generation must accept the same
        identifiers as chat, while owner-aware resolution prevents another
        user's personal document from being selected by path or index key.
        """
        from modules.rag_v2.api import get_rag_system
        from modules.rag_v2.document_resolver import resolve_rag_document

        rag_system = get_rag_system()
        resolved = resolve_rag_document(
            rag_system,
            document_id,
            owner=owner,
        )
        if resolved is None:
            return None

        record = dict(resolved.record or {})
        listed = dict(resolved.listed_document or {})
        if (
            str(record.get("library_type") or listed.get("library_type") or "")
            .strip()
            .lower()
            == "course"
            or str(record.get("course_id") or listed.get("course_id") or "").strip()
        ):
            return None

        chunk_count = int(
            listed.get("chunk_count")
            or record.get("chunk_count")
            or 0
        )
        if chunk_count <= 0:
            chunks = rag_system.vector_store.get_documents_by_source(
                resolved.source_key
            )
            chunk_count = len(list(chunks or []))

        return SourceDocumentRecord(
            course_id=course_id,
            document_id=str(document_id).strip(),
            name=str(
                listed.get("file_name")
                or record.get("file_name")
                or resolved.file_name
            ),
            status="ready" if chunk_count > 0 else "received",
            rag_index_key=resolved.index_key,
            chunk_count=chunk_count,
        )


class _ResolvedDocumentContentReader:
    def read_many(self, rag_index_keys: Sequence[str]) -> str:
        from app.chat.application.knowledge_base_document_content_provider import (
            KnowledgeBaseDocumentContentProvider,
        )

        result = KnowledgeBaseDocumentContentProvider().get_resolved_document_contents(
            rag_index_keys=list(rag_index_keys)
        )
        return "\n\n".join(
            f"## {item.get('title') or 'Document'}\n{item.get('content') or ''}"
            for item in list(result.get("documents") or [])
            if str(item.get("content") or "").strip()
        )

    def search_many(
        self,
        rag_index_keys: Sequence[str],
        query_text: str,
        top_k: int = 12,
    ) -> str:
        from modules.rag_v2.api import get_rag_system

        normalized_query = str(query_text or "").strip()
        allowed_sources = [str(item).strip() for item in rag_index_keys if str(item).strip()]
        if not normalized_query or not allowed_sources:
            return ""
        rag_system = get_rag_system()
        query_embedding = rag_system.embedding_client.embed_query(normalized_query)
        chunks = rag_system.vector_store.hybrid_search(
            query=normalized_query,
            query_embedding=query_embedding,
            top_k=max(1, int(top_k)),
            allowed_sources=allowed_sources,
        )
        blocks: list[str] = []
        for chunk in list(chunks or []):
            metadata = dict(chunk.get("metadata") or {})
            source = metadata.get("source") or metadata.get("file_name") or "课程知识库"
            content = str(chunk.get("document") or chunk.get("content") or "").strip()
            if content:
                blocks.append(f"[来源: {source}]\n{content}")
        return "\n\n---\n\n".join(blocks)


def _generation_query(config: Mapping[str, Any], resource_type: str) -> str:
    candidates: list[Any] = [
        config.get("topic"),
        config.get("title"),
        config.get("question"),
        config.get("final_user_prompt"),
        config.get("description"),
        config.get("requirement"),
        config.get("subject"),
    ]
    for nested_key in (
        "report_config",
        "quiz_config",
        "flashcard_config",
        "graph_config",
        "classroom_config",
    ):
        nested = config.get(nested_key)
        if isinstance(nested, Mapping):
            candidates.extend(
                nested.get(key)
                for key in ("topic", "title", "question", "description")
            )
    query = next(
        (str(item).strip() for item in candidates if str(item or "").strip()),
        "",
    )
    return query or resource_type


def build_default_generation_source_resolver(
    manager: CourseStorageManager,
) -> GenerationSourceResolver:
    return GenerationSourceResolver(
        _CourseDocumentCatalog(manager),
        _ResolvedDocumentContentReader(),
    )


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
        source_context = str(
            getattr(payload, "source_context", "") or ""
        ).strip()
        research_context = str(
            getattr(payload, "research_context", "") or ""
        ).strip()
        evidence_context = "\n\n".join(
            part
            for part in (
                (
                    f"[知识库解析内容]\n{source_context[:24000]}"
                    if source_context
                    else ""
                ),
                research_context[:16000],
            )
            if part
        )
        research_sources = [
            dict(item)
            for item in list(
                getattr(payload, "research_sources", []) or []
            )
            if isinstance(item, Mapping)
        ][:20]
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
                "evidence_context": evidence_context,
            },
            outline=parse_report_outline(
                str(getattr(payload, "confirmed_outline", "") or "")
            ),
            mode="fast",
        )
        checkpoint = dict(checkpoint or {})
        checkpoint["grounding"] = {
            "knowledge_base_context_used": bool(source_context),
            "retrieval_context_used": bool(research_context),
            "research_source_count": len(research_sources),
        }
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
    from app.services.direct_lesson_plan_service import (
        build_default_direct_lesson_plan_service,
    )

    return {
        "report": build_default_knowledge_base_direct_report_service_v2,
        "blog": BlogGenerationAdapterV2,
        "quiz": build_default_knowledge_base_direct_quiz_service_v2,
        "ppt": build_default_knowledge_base_direct_ppt_service_v2,
        "flashcard": build_default_knowledge_base_direct_flashcard_service_v2,
        "graph": build_default_knowledge_base_direct_graph_service_v2,
        "game": build_default_knowledge_base_direct_game_service_v2,
        "lesson_plan": build_default_direct_lesson_plan_service,
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
        source_resolver: Any | None = None,
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
        self.source_resolver = (
            source_resolver
            or build_default_generation_source_resolver(
                self.course_storage_manager
            )
        )

    def __call__(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        return self.handle(command, context)

    def handle(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        resource_type = str(command.get("resource_type") or "").strip()
        config = dict(command.get("config") or {})
        is_agent_entrypoint = config.get("entrypoint") == "agent"
        factory = (
            self.agent_service_factories.get(resource_type)
            or self.service_factories.get(resource_type)
            if is_agent_entrypoint
            else self.service_factories.get(resource_type)
        )
        if factory is None:
            raise ValueError(f"unsupported generation resource {resource_type}")
        selected_doc_ids = list(command.get("selected_doc_ids") or [])
        source_mode = str(
            command.get("source_mode")
            or ("selected_documents" if selected_doc_ids else "course_auto")
        )
        course_id = str(command.get("course_id") or context.course_id or "").strip()
        resolve_signature = inspect.signature(self.source_resolver.resolve)
        resolve_kwargs = (
            {"query_text": _generation_query(config, resource_type)}
            if "query_text" in resolve_signature.parameters
            else {}
        )
        if "owner" in resolve_signature.parameters:
            resolve_kwargs["owner"] = context.owner_user_id
        source = self.source_resolver.resolve(
            course_id,
            source_mode,
            selected_doc_ids,
            **resolve_kwargs,
        )
        execution_context = GenerationExecutionContext(
            job_id=context.task_id,
            course_id=course_id,
            user_id=context.owner_user_id,
            source=source,
            config=_freeze(deepcopy(config)),
        )
        if context.is_cancel_requested():
            return {
                "saved": False,
                "canceled": True,
                "result_ref": {},
            }
        payload = self._build_payload(command, context, execution_context)
        context.progress(5, "generating", "正在根据课程资料生成内容")
        generator = factory()
        generate_kwargs: dict[str, Any] = {
            "job_id": context.task_id,
            "config_snapshot_id": context.config_snapshot_id or "",
        }
        signature = inspect.signature(generator.generate)
        if (
            "execution_context" in signature.parameters
            or any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
        ):
            generate_kwargs["execution_context"] = execution_context
        result = dict(generator.generate(payload, **generate_kwargs))
        if context.is_cancel_requested():
            return {
                "saved": False,
                "canceled": True,
                "result_ref": {},
            }
        if result.get("result_ref"):
            self._persist_existing_result_provenance(
                command=command,
                context=context,
                result=result,
                execution_context=execution_context,
            )
            return result
        return self._publish_artifact(
            command=command,
            context=context,
            resource_type=resource_type,
            result=result,
            execution_context=execution_context,
        )

    @staticmethod
    def _build_payload(
        command: Mapping[str, Any],
        context: DurableExecutionContext,
        execution_context: GenerationExecutionContext | None = None,
    ) -> SimpleNamespace:
        resource_type = str(command.get("resource_type") or "").strip()
        config = dict(command.get("config") or {})
        if execution_context is None:
            course_id = str(command.get("course_id") or context.course_id or "")
            source_mode = str(command.get("source_mode") or "none")
            requested_document_ids = tuple(
                str(item) for item in list(command.get("selected_doc_ids") or [])
            )
            execution_context = GenerationExecutionContext(
                job_id=context.task_id,
                course_id=course_id,
                user_id=context.owner_user_id,
                source=ResolvedGenerationSource(
                    course_id=course_id,
                    mode=source_mode if source_mode in {
                        "none",
                        "course_auto",
                        "selected_documents",
                    } else "none",
                    requested_document_ids=requested_document_ids,
                    documents=(),
                    context_text="",
                    resolved_at="",
                ),
                config=_freeze(deepcopy(config)),
            )
        base: dict[str, Any] = {
            "owner": context.owner_user_id,
            "course_id": str(command.get("course_id") or context.course_id or ""),
            "scope_type": str(command.get("scope_type") or "course"),
            "scope_id": command.get("scope_id"),
            "selected_doc_ids": [
                item.rag_index_key for item in execution_context.source.documents
            ],
            "source_context": execution_context.source.context_text,
            "source_snapshot": execution_context.source.to_snapshot(),
            "source_mode": execution_context.source.mode,
            "allow_rag": bool(execution_context.source.documents),
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
            base.update(
                {
                    "game_type": config.get("game_type"),
                    "topic": config.get("topic") or config.get("title"),
                    "card_count": config.get("card_count"),
                    "difficulty": config.get("difficulty"),
                    "duration_minutes": config.get("duration_minutes"),
                }
            )
        elif resource_type == "flashcard":
            base["flashcard_config"] = dict(
                config.get("flashcard_config") or config
            )
        elif resource_type == "graph":
            base["graph_config"] = {
                "title": config.get("title"),
                "description": config.get("description"),
                "max_depth": config.get("max_depth"),
            }
        elif resource_type == "blog":
            base.update(config)
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
        base.update(
            {
                "selected_doc_ids": [
                    item.rag_index_key
                    for item in execution_context.source.documents
                ],
                "source_context": execution_context.source.context_text,
                "source_snapshot": execution_context.source.to_snapshot(),
                "source_mode": execution_context.source.mode,
                "allow_rag": bool(execution_context.source.documents),
            }
        )
        return SimpleNamespace(**base)

    def _persist_existing_result_provenance(
        self,
        *,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
        result: Mapping[str, Any],
        execution_context: GenerationExecutionContext,
    ) -> None:
        result_ref = dict(result.get("result_ref") or {})
        if result_ref.get("resource_type") != "course_material":
            return
        course_id = str(result_ref.get("course_id") or "").strip()
        material_type = str(result_ref.get("material_type") or "").strip()
        material_id = str(result_ref.get("material_id") or "").strip()
        if not all((course_id, material_type, material_id)):
            return
        existing = self.course_storage_manager.get_generated_material(
            course_id,
            material_type,
            material_id,
            owner_user_id=context.owner_user_id,
        )
        if existing is None:
            return
        self.course_storage_manager.save_generated_material(
            course_id=course_id,
            material_type=material_type,
            material_id=material_id,
            material_data={},
            scope_type=str(existing.get("scope_type") or "course"),
            scope_id=existing.get("scope_id"),
            owner_user_id=context.owner_user_id,
            source_job_id=context.task_id,
            config_snapshot_id=context.config_snapshot_id,
            source_snapshot=execution_context.source.to_snapshot(),
            config_snapshot=deepcopy(dict(command.get("config") or {})),
        )

    def _publish_artifact(
        self,
        *,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
        resource_type: str,
        result: dict[str, Any],
        execution_context: GenerationExecutionContext,
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
                source_snapshot=execution_context.source.to_snapshot(),
                config_snapshot=deepcopy(dict(command.get("config") or {})),
                material_data={
                    "title": str(artifact.get("title") or resource_type),
                    "content": artifact.get("content"),
                    "generation_state": dict(
                        artifact.get("generation_state") or {}
                    ),
                    "source": {
                        "selected_doc_ids": list(
                            execution_context.source.requested_document_ids
                        ),
                        "rag_index_keys": [
                            item.rag_index_key
                            for item in execution_context.source.documents
                        ],
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
