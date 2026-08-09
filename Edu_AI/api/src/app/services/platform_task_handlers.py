from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable, Mapping
from typing import Any

from app.chat.tasks.task_store import TaskStore, get_task_store
from app.services.durable_task_handlers import (
    DurableExecutionContext,
    DurableTaskHandlerRegistry,
)
from app.services.job_store import EduJob, JobStatus, get_job, update_job
from core.course_storage import CourseStorageManager


def _plan_classroom_visuals(
    command: Mapping[str, Any],
    resolved_source: Any,
    *,
    owner: str,
    pipeline=None,
    llm=None,
) -> dict[str, Any]:
    if not bool(command.get("include_visuals", False)):
        return {}
    if pipeline is None:
        from app.chat.application.knowledge_base_direct_report_service_v2 import (
            _build_default_visual_pipeline,
        )

        pipeline = _build_default_visual_pipeline()
    if llm is None:
        from app.chat.agents.report_generation import get_fallback_llm

        llm = get_fallback_llm()
    topic = str(command.get("topic") or command.get("requirement") or "").strip()
    try:
        brief = pipeline.plan_with_model(
            llm,
            resource_type="classroom",
            topic=topic,
            source_context=str(resolved_source.context_text or ""),
        )
        result = pipeline.run(
            brief,
            course_id=str(command.get("course_id") or ""),
            owner=owner or None,
            selected_document_ids=[
                str(item.document_id)
                for item in list(resolved_source.documents or [])
            ],
        )
        return dict(result.to_snapshot())
    except Exception as exc:
        return {"selected": [], "error": str(exc)}


def _classroom_requirement(command: Mapping[str, Any]) -> str:
    requirement = str(command.get("requirement") or "").strip()
    settings = {
        "audience": str(command.get("audience") or "").strip(),
        "objectives": list(command.get("objectives") or []),
        "scene_count": int(command.get("scene_count") or 6),
        "duration_minutes": int(command.get("duration_minutes") or 25),
        "teaching_style": str(command.get("teaching_style") or "guided"),
    }
    return (
        requirement
        + "\n\n【课堂生成配置，必须实际执行】\n"
        + json.dumps(settings, ensure_ascii=False)
    ).strip()


def enqueue_platform_task(
    *,
    job: EduJob,
    workflow_type: str,
    command: dict[str, Any],
    task_store: TaskStore | None = None,
    runtime_config_snapshot: dict[str, str] | None = None,
) -> EduJob:
    store = task_store or get_task_store()
    payload = dict(command)
    if runtime_config_snapshot:
        payload["runtime_config_snapshot"] = dict(runtime_config_snapshot)
    try:
        store.enqueue(
            task_id=job.edu_job_id,
            workflow_type=workflow_type,
            handler_version=1,
            owner_user_id=job.owner_user_id,
            course_id=job.course_id,
            scope_type=job.scope_type,
            scope_id=job.scope_id,
            command=payload,
            config_snapshot_id=str(
                payload.get("config_snapshot_id") or ""
            ).strip()
            or None,
            idempotency_key=job.edu_job_id,
            max_attempts=3,
        )
    except Exception as exc:
        return (
            update_job(
                job.edu_job_id,
                status=JobStatus.FAILED,
                step="enqueue_failed",
                progress=100,
                message="后台任务入队失败",
                error_code="TASK_ENQUEUE_FAILED",
                error_message=str(exc),
            )
            or job
        )
    return job


class PlatformTaskHandlers:
    def __init__(
        self,
        *,
        course_storage_factory: Callable[[], CourseStorageManager] | None = None,
        generation_source_resolver_factory: Callable[[CourseStorageManager], Any]
        | None = None,
    ) -> None:
        self.course_storage_factory = (
            course_storage_factory or CourseStorageManager
        )
        if generation_source_resolver_factory is None:
            from app.services.generation_task_handlers import (
                build_default_generation_source_resolver,
            )

            generation_source_resolver_factory = (
                build_default_generation_source_resolver
            )
        self.generation_source_resolver_factory = (
            generation_source_resolver_factory
        )

    def classroom_generate(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        from app.integrations.openmaic import get_openmaic_client
        from app.services.classroom_job_service import (
            run_generate_classroom_job,
        )
        from app.services.classroom_service import (
            _build_research_context,
            _make_on_sidecar_succeeded,
        )

        manager = self.course_storage_factory()
        course_id = str(command.get("course_id") or context.course_id or "")
        requirement = _classroom_requirement(command)
        client = get_openmaic_client(owner_user_id=context.owner_user_id)
        job = self._require_job(context.task_id)
        selected_doc_ids = list(command.get("selected_doc_ids") or [])
        source_mode = str(
            command.get("source_mode")
            or ("selected_documents" if selected_doc_ids else "course_auto")
        )
        source_resolver = self.generation_source_resolver_factory(manager)
        resolve_signature = inspect.signature(source_resolver.resolve)
        resolve_kwargs = (
            {"query_text": requirement}
            if "query_text" in resolve_signature.parameters
            else {}
        )
        if "owner" in resolve_signature.parameters:
            resolve_kwargs["owner"] = context.owner_user_id
        resolved_source = source_resolver.resolve(
            course_id,
            source_mode,
            selected_doc_ids,
            **resolve_kwargs,
        )
        visual_snapshot = _plan_classroom_visuals(
            command,
            resolved_source,
            owner=context.owner_user_id,
        )

        async def run() -> None:
            research_context = await _build_research_context(
                course_storage_manager=manager,
                course_id=course_id,
                requirement=requirement,
                web_research_context=command.get("web_research_context"),
                rag_top_k=int(command.get("rag_top_k") or 5),
                rag_system=None,
                resolved_source=resolved_source,
            )
            selected_visuals = list(visual_snapshot.get("selected") or [])
            if selected_visuals:
                visual_context = (
                    "【已锁定课堂配图】\n"
                    + json.dumps(selected_visuals, ensure_ascii=False)
                    + "\n请围绕这些真实图片组织相应课堂场景，不得伪造其他图片 URL。"
                )
                research_context = "\n\n".join(
                    item
                    for item in (research_context, visual_context)
                    if item
                )
            source_snapshot = resolved_source.to_snapshot()
            if visual_snapshot:
                source_snapshot["visuals"] = visual_snapshot
            callback = _make_on_sidecar_succeeded(
                active_client=client,
                course_storage_manager=manager,
                course_id=course_id,
                owner=context.owner_user_id,
                scope_type=str(command.get("scope_type") or "course"),
                scope_id=command.get("scope_id"),
                source_snapshot=source_snapshot,
                source_job_id=context.task_id,
            )
            await run_generate_classroom_job(
                job,
                requirement=requirement,
                research_context=research_context,
                pdf_content=command.get("pdf_content"),
                enable_web_search=bool(
                    command.get("enable_web_search", False)
                ),
                enable_tts=bool(command.get("enable_tts", True)),
                client=client,
                on_sidecar_succeeded=callback,
            )

        context.progress(3, "research", "正在准备课程资料")
        asyncio.run(run())
        return self._completed_public_result(context.task_id)

    def classroom_video_export(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        from app.services.classroom_video_export import (
            run_classroom_video_export_job,
        )
        from core.auth import auth_manager

        manager = self.course_storage_factory()
        job = self._require_job(context.task_id)
        course_id = str(command.get("course_id") or context.course_id or "")
        classroom_id = str(command.get("classroom_id") or "").strip()
        role = str(command.get("owner_role") or "teacher").strip() or "teacher"
        server_token = auth_manager.create_token(context.owner_user_id, role)
        current_user = {
            "username": context.owner_user_id,
            "role": role,
        }
        context.progress(2, "preparing", "正在准备课堂视频导出")
        asyncio.run(
            run_classroom_video_export_job(
                job,
                course_id=course_id,
                classroom_id=classroom_id,
                auth_token=server_token,
                current_user=current_user,
                course_storage_manager=manager,
            )
        )
        return self._completed_public_result(context.task_id)

    def rag_document_index(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        from app.services.knowledge_document_service import run_index_job
        from modules.rag_v2.api import get_rag_system

        manager = self.course_storage_factory()
        context.progress(2, "parsing", "正在读取文档内容")
        run_index_job(
            manager=manager,
            rag_system=get_rag_system(),
            course_id=str(command.get("course_id") or context.course_id or ""),
            document_id=str(command.get("document_id") or ""),
            owner_user_id=context.owner_user_id,
            force_reindex=bool(command.get("force_reindex", False)),
            pending_version=str(command.get("pending_version") or ""),
            job_id=context.task_id,
        )
        return self._completed_public_result(context.task_id)

    def course_knowledge_build(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        from app.services.course_knowledge_builder import (
            run_course_knowledge_build_job,
        )
        from modules.rag_v2.api import get_rag_system

        manager = self.course_storage_factory()
        run_course_knowledge_build_job(
            job_id=context.task_id,
            manager=manager,
            rag_system=get_rag_system(),
            course_id=str(command.get("course_id") or context.course_id or ""),
            owner_user_id=context.owner_user_id,
            source_id=str(command.get("source_id") or "auto"),
            max_pages=int(command.get("max_pages") or 48),
            clean_placeholders=bool(command.get("clean_placeholders", True)),
            progress=context.progress,
        )
        return self._completed_public_result(context.task_id)

    def video_ingest(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        from app.services.video_service import run_video_ingestion_job

        context.progress(2, "ingesting", "正在准备视频入库")
        run_video_ingestion_job(context.task_id)
        return self._completed_public_result(context.task_id)

    @staticmethod
    def _require_job(task_id: str) -> EduJob:
        job = get_job(task_id)
        if job is None:
            raise RuntimeError("public job record is missing")
        return job

    @classmethod
    def _completed_public_result(cls, task_id: str) -> dict[str, Any]:
        job = cls._require_job(task_id)
        if job.status == JobStatus.CANCELED:
            return {"saved": False, "error": "task canceled", "result_ref": {}}
        if job.status != JobStatus.SUCCEEDED or not job.result_ref:
            raise RuntimeError(
                job.error_message or job.message or "platform task failed"
            )
        return {
            "saved": True,
            "result_ref": dict(job.result_ref),
        }


def register_platform_task_handlers(
    registry: DurableTaskHandlerRegistry,
    *,
    handlers: PlatformTaskHandlers | None = None,
) -> PlatformTaskHandlers:
    active = handlers or PlatformTaskHandlers()
    registry.register("classroom_generate", 1, active.classroom_generate)
    registry.register(
        "classroom_video_export",
        1,
        active.classroom_video_export,
    )
    registry.register("rag_document_index", 1, active.rag_document_index)
    registry.register("course_knowledge_build", 1, active.course_knowledge_build)
    registry.register("video_ingest", 1, active.video_ingest)
    return active
