from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable, Mapping
from typing import Any

from app.chat.tasks.task_store import TaskStore, get_task_store
from app.services.durable_task_handlers import (
    DurableTaskExecutionError,
    DurableExecutionContext,
    DurableTaskHandlerRegistry,
)
from app.services.job_store import EduJob, JobStatus, get_job, update_job
from core.course_storage import CourseStorageManager


def _classroom_requirement(command: Mapping[str, Any]) -> str:
    requirement = str(command.get("requirement") or "").strip()
    settings = {key: command[key] for key in
                ('audience', 'objectives', 'duration_minutes', 'teaching_style', 'scene_count')
                if command.get(key) is not None}
    return (requirement + "\n\n【用户需求】\n" + json.dumps(settings, ensure_ascii=False)).strip()



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
    if workflow_type == 'classroom_generate':
        from app.integrations.hyperframes.generation_policy import generation_limits
        payload = generation_limits(payload)
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
        personal_storage_factory: Callable[[str], CourseStorageManager]
        | None = None,
        generation_source_resolver_factory: Callable[[CourseStorageManager], Any]
        | None = None,
    ) -> None:
        self.course_storage_factory = (
            course_storage_factory or CourseStorageManager
        )
        if personal_storage_factory is None:
            def default_personal_storage_factory(
                owner_user_id: str,
            ) -> CourseStorageManager:
                from app.services.personal_knowledge_service import (
                    PersonalKnowledgeService,
                )

                return PersonalKnowledgeService().manager_for(owner_user_id)

            personal_storage_factory = default_personal_storage_factory
        self.personal_storage_factory = personal_storage_factory
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
        from app.services.hyperframes_classroom import generate_and_persist
        manager = self.course_storage_factory()
        course_id = str(command.get('course_id') or context.course_id or '')
        requirement = _classroom_requirement(command)
        self._require_job(context.task_id)
        resolver = self.generation_source_resolver_factory(manager)
        kwargs = {}
        parameters = inspect.signature(resolver.resolve).parameters
        if 'query_text' in parameters: kwargs['query_text'] = requirement
        if 'owner' in parameters: kwargs['owner'] = context.owner_user_id
        selected = list(command.get('selected_doc_ids') or [])
        source = resolver.resolve(course_id, command.get('source_mode') or ('selected_documents' if selected else 'course_auto'), selected, **kwargs)
        generate_and_persist(command, context, manager, source, requirement)
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

        storage_scope = str(command.get("storage_scope") or "course")
        if storage_scope == "personal":
            manager = self.personal_storage_factory(context.owner_user_id)
        else:
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

    def course_knowledge_plan_build(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        from app.services.course_knowledge_plan_builder import (
            run_course_knowledge_plan_build_job,
        )
        from modules.rag_v2.api import get_rag_system

        manager = self.course_storage_factory()
        run_course_knowledge_plan_build_job(
            job_id=context.task_id,
            manager=manager,
            rag_system=get_rag_system(),
            course_id=str(command.get("course_id") or context.course_id or ""),
            owner_user_id=context.owner_user_id,
            build_id=str(command.get("build_id") or ""),
            progress=context.progress,
            is_cancel_requested=context.is_cancel_requested,
        )
        if context.is_cancel_requested():
            return {"saved": False, "error": "task canceled", "result_ref": {}}
        return self._completed_public_result(context.task_id)

    def course_knowledge_graph_generate(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        from app.services.course_knowledge_graph_generator import (
            run_course_knowledge_graph_generation_job,
        )

        run_course_knowledge_graph_generation_job(
            job_id=context.task_id,
            course_id=str(command.get("course_id") or context.course_id or ""),
            owner_user_id=context.owner_user_id,
            build_id=str(command.get("build_id") or ""),
            expected_revision=int(command.get("expected_revision") or 0),
            target_module_id=str(command.get("target_module_id") or "") or None,
            progress=context.progress,
        )
        return self._completed_public_result(context.task_id)

    def course_knowledge_textbook_parse(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> dict[str, Any]:
        from app.services.course_knowledge_textbook_inputs import (
            run_course_knowledge_textbook_parse_job,
        )

        run_course_knowledge_textbook_parse_job(
            manager=self.course_storage_factory(),
            job_id=context.task_id,
            course_id=str(command.get("course_id") or context.course_id or ""),
            build_id=str(command.get("build_id") or ""),
            textbook_id=str(command.get("textbook_id") or ""),
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
            raise DurableTaskExecutionError(
                str(job.error_code or "TASK_EXECUTION_FAILED"),
                str(job.error_message or job.message or "platform task failed"),
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
    registry.register(
        "course_knowledge_plan_build",
        1,
        active.course_knowledge_plan_build,
    )
    registry.register(
        "course_knowledge_graph_generate",
        1,
        active.course_knowledge_graph_generate,
    )
    registry.register(
        "course_knowledge_textbook_parse",
        1,
        active.course_knowledge_textbook_parse,
    )
    registry.register("video_ingest", 1, active.video_ingest)
    return active
