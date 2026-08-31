"""Dispatch a freshly-created retry job through its original business runner."""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.classroom_service import submit_classroom_generation_job
from app.services.classroom_video_export import submit_classroom_video_export_job
from app.services.knowledge_document_service import submit_index_job
from app.services.job_store import EduJob, JobKind, JobStatus, update_job
from app.services.job_store import retry_job
from app.chat.tasks.task_store import TaskStore
from app.services.generation_command import (
    GenerationCommand,
    generation_command_service,
)
from app.standard_resources.batch_service import (
    MAX_STANDARD_RESOURCE_BATCH_DEADLINE_SECONDS,
    standard_resource_execution_timeout_seconds,
)
from core.course_storage import CourseStorageManager
from modules.rag_v2.api import get_rag_system


def retry_durable_job(
    original: EduJob,
    *,
    owner_user_id: str,
    task_store: TaskStore,
) -> EduJob | None:
    """Copy a persisted command to a new public job and durable task."""
    original_task = task_store.get_durable(original.edu_job_id)
    if original_task is None or original_task.command is None:
        return None
    retried = retry_job(
        original.edu_job_id,
        owner_user_id=owner_user_id,
    )
    try:
        command = dict(original_task.command)
        standard_kind = _standard_resource_kind(command)
        if standard_kind is not None:
            command["deadline_seconds"] = (
                MAX_STANDARD_RESOURCE_BATCH_DEADLINE_SECONDS
            )
            command["execution_timeout_seconds"] = (
                standard_resource_execution_timeout_seconds(standard_kind)
            )
        task_store.enqueue(
            task_id=retried.edu_job_id,
            workflow_type=original_task.workflow_type,
            handler_version=original_task.handler_version,
            owner_user_id=owner_user_id,
            course_id=original_task.course_id,
            scope_type=original_task.scope_type,
            scope_id=original_task.scope_id,
            command=command,
            config_snapshot_id=original_task.config_snapshot_id,
            idempotency_key=retried.edu_job_id,
            max_attempts=original_task.max_attempts,
        )
    except Exception as exc:
        return (
            update_job(
                retried.edu_job_id,
                status=JobStatus.FAILED,
                step="retry_enqueue_failed",
                progress=100,
                message="重试任务入队失败",
                error_code="TASK_ENQUEUE_FAILED",
                error_message=str(exc),
            )
            or retried
        )
    return retried


def _standard_resource_kind(command: dict[str, Any]) -> str | None:
    metadata_candidates = [
        command.get("material_metadata"),
        (command.get("config") or {}).get("standard_resource")
        if isinstance(command.get("config"), dict)
        else None,
    ]
    for metadata in metadata_candidates:
        if (
            isinstance(metadata, dict)
            and (
            metadata.get("origin_type") == "standard"
            or bool(metadata.get("generation_batch_id"))
            )
        ):
            return str(metadata.get("standard_kind") or "study_guide")
    return None


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

    if job.kind == JobKind.INGEST_VIDEO:
        from app.services.video_service import run_video_ingestion_job

        asyncio.create_task(
            asyncio.to_thread(run_video_ingestion_job, job.edu_job_id)
        )
        return job

    if job.kind == JobKind.GENERATE_FLASHCARD:
        command = _generation_command_from_retry(job, owner=owner)
        return generation_command_service.submit(
            command,
            existing_job=job,
        )

    if job.kind == JobKind.GENERATE_PPT:
        command = _generation_command_from_retry(job, owner=owner)
        draft_id = str(command.config.get("draft_id") or "").strip()
        if not draft_id:
            return _dispatch_failure(job, "重试任务缺少 PPT 草稿信息")
        return generation_command_service.submit(
            command,
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
