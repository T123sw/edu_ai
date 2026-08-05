"""Dispatch a freshly-created retry job through its original business runner."""

from __future__ import annotations

from typing import Any

from app.services.classroom_service import submit_classroom_generation_job
from app.services.classroom_video_export import submit_classroom_video_export_job
from app.services.knowledge_document_service import submit_index_job
from app.services.job_store import EduJob, JobKind, JobStatus, update_job
from app.services.generation_command import (
    GenerationCommand,
    generation_command_service,
)
from core.course_storage import CourseStorageManager
from modules.rag_v2.api import get_rag_system


async def dispatch_retry_job(
    job: EduJob,
    *,
    auth_token: str,
    current_user: dict[str, Any],
    course_storage_manager: CourseStorageManager,
) -> EduJob:
    owner = str(current_user.get("username") or "").strip()
    summary = job.input_summary
    course_id = str(job.course_id or "").strip()
    if not course_id:
        return _dispatch_failure(job, "重试任务缺少课程信息")

    if job.kind == JobKind.GENERATE_CLASSROOM:
        requirement = str(summary.get("requirement") or "").strip()
        if not requirement:
            return _dispatch_failure(job, "重试任务缺少课堂生成要求")
        return await submit_classroom_generation_job(
            course_id=course_id,
            requirement=requirement,
            owner=owner,
            course_storage_manager=course_storage_manager,
            enable_web_search=bool(summary.get("enable_web_search", False)),
            enable_tts=bool(summary.get("enable_tts", True)),
            scope_type=job.scope_type,
            scope_id=job.scope_id,
            existing_job=job,
        )

    if job.kind == JobKind.RENDER_VIDEO:
        classroom_id = str(summary.get("classroom_id") or "").strip()
        if not classroom_id:
            return _dispatch_failure(job, "重试任务缺少课堂资源信息")
        return await submit_classroom_video_export_job(
            course_id=course_id,
            classroom_id=classroom_id,
            auth_token=auth_token,
            current_user=current_user,
            owner=owner,
            course_storage_manager=course_storage_manager,
            existing_job=job,
        )

    if job.kind == JobKind.RAG_IMPORT:
        document_id = str(summary.get("document_id") or "").strip()
        if not document_id:
            return _dispatch_failure(job, "重试任务缺少知识库文档信息")
        try:
            return submit_index_job(
                manager=course_storage_manager,
                rag_system=get_rag_system(),
                course_id=course_id,
                document_id=document_id,
                owner_user_id=owner,
                force_reindex=bool(summary.get("force_reindex", False)),
                existing_job=job,
            )
        except (KeyError, ValueError) as exc:
            return _dispatch_failure(job, str(exc))

    if job.kind == JobKind.GENERATE_FLASHCARD:
        from types import SimpleNamespace

        from app.chat.application.knowledge_base_direct_flashcard_service_v2 import (
            build_default_knowledge_base_direct_flashcard_service_v2,
        )

        command = _generation_command_from_retry(job, owner=owner)
        service = build_default_knowledge_base_direct_flashcard_service_v2()

        def _run(active_command, job_id, config_snapshot_id):
            return service.generate(
                SimpleNamespace(
                    owner=active_command.owner_user_id,
                    course_id=active_command.course_id,
                    scope_type=active_command.scope_type,
                    scope_id=active_command.scope_id,
                    selected_doc_ids=active_command.selected_doc_ids,
                    flashcard_config=active_command.config,
                ),
                job_id=job_id,
                config_snapshot_id=config_snapshot_id,
            )

        return generation_command_service.submit(
            command,
            _run,
            existing_job=job,
        )

    if job.kind == JobKind.GENERATE_PPT:
        from types import SimpleNamespace

        from app.chat.application.knowledge_base_direct_ppt_service_v2 import (
            build_default_knowledge_base_direct_ppt_service_v2,
        )

        command = _generation_command_from_retry(job, owner=owner)
        draft_id = str(command.config.get("draft_id") or "").strip()
        if not draft_id:
            return _dispatch_failure(job, "重试任务缺少 PPT 草稿信息")
        service = build_default_knowledge_base_direct_ppt_service_v2()

        def _run(active_command, job_id, config_snapshot_id):
            return service.generate(
                SimpleNamespace(
                    owner=active_command.owner_user_id,
                    draft_id=draft_id,
                    confirm=True,
                    outline=None,
                ),
                job_id=job_id,
                config_snapshot_id=config_snapshot_id,
            )

        return generation_command_service.submit(
            command,
            _run,
            existing_job=job,
        )

    return _dispatch_failure(job, "当前任务类型暂不支持自动重试")


def _generation_command_from_retry(job: EduJob, *, owner: str) -> GenerationCommand:
    summary = dict(job.input_summary or {})
    return GenerationCommand(
        resource_type=str(summary.get("resource_type") or ""),
        owner_user_id=owner,
        course_id=str(job.course_id or ""),
        scope_type=job.scope_type,
        scope_id=job.scope_id,
        selected_doc_ids=list(summary.get("selected_doc_ids") or []),
        config=dict(summary.get("config") or {}),
        idempotency_key=job.edu_job_id,
    )


def _dispatch_failure(job: EduJob, message: str) -> EduJob:
    return (
        update_job(
            job.edu_job_id,
            status=JobStatus.FAILED,
            step="retry_dispatch_failed",
            progress=100,
            message=message,
            error_message=message,
            error_code="RETRY_DISPATCH_FAILED",
        )
        or job
    )
