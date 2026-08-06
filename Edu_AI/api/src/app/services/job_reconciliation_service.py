from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone

from app.chat.tasks.task_store import DurableTask, TaskStore
from app.services.job_store import (
    ACTIVE_JOB_STATUSES,
    EduJob,
    JobKind,
    JobStatus,
    list_job_page,
    reconcile_succeeded_job,
    update_job,
)
from core.course_storage import CourseStorageManager


_DURABLE_JOB_KINDS = {
    JobKind.GENERATE_CLASSROOM,
    JobKind.RENDER_VIDEO,
    JobKind.GENERATE_REPORT,
    JobKind.GENERATE_LESSON_PLAN,
    JobKind.GENERATE_BLOG,
    JobKind.GENERATE_QUIZ,
    JobKind.GENERATE_PPT,
    JobKind.GENERATE_FLASHCARD,
    JobKind.GENERATE_GRAPH,
    JobKind.GENERATE_GAME,
    JobKind.INGEST_VIDEO,
    JobKind.RAG_IMPORT,
}


class JobReconciliationService:
    """Repair the durable queue and public job ledger before workers start."""

    def __init__(
        self,
        *,
        task_store: TaskStore,
        course_storage_manager: CourseStorageManager | None = None,
        now_provider: Callable[[], float] | None = None,
    ) -> None:
        self.task_store = task_store
        self.course_storage_manager = (
            course_storage_manager or CourseStorageManager()
        )
        self.now_provider = now_provider or time.time

    def reconcile_startup(self) -> None:
        self.run()

    def run(self, *, now: float | datetime | None = None) -> None:
        active_now = self._timestamp(
            self.now_provider() if now is None else now
        )
        active_jobs = self._active_jobs()
        self._finish_published_results(active_jobs, now=active_now)
        self.task_store.recover_expired_leases(now=active_now)
        self._sync_public_ledger(self._active_jobs())
        self._audit_succeeded_results()

    @staticmethod
    def _timestamp(value: float | datetime) -> float:
        if isinstance(value, datetime):
            active = value
            if active.tzinfo is None:
                active = active.replace(tzinfo=timezone.utc)
            return active.timestamp()
        return float(value)

    @staticmethod
    def _active_jobs() -> list[EduJob]:
        jobs: list[EduJob] = []
        cursor: str | None = None
        while True:
            page = list_job_page(
                statuses=ACTIVE_JOB_STATUSES,
                limit=200,
                cursor=cursor,
            )
            jobs.extend(page.items)
            cursor = page.next_cursor
            if cursor is None:
                return jobs

    def _finish_published_results(
        self,
        jobs: list[EduJob],
        *,
        now: float,
    ) -> None:
        for job in jobs:
            task = self.task_store.get_durable(job.edu_job_id)
            result_ref = self._published_result_ref(task, now=now)
            if task is None or result_ref is None:
                continue
            result = {
                "saved": True,
                "reconciled": True,
                "result_ref": result_ref,
            }
            if not self.task_store.mark_reconciled_succeeded(
                task.task_id,
                result=result,
                result_ref=result_ref,
                now=now,
            ):
                continue
            update_job(
                job.edu_job_id,
                status=JobStatus.SUCCEEDED,
                step="reconciled",
                progress=100,
                message="已恢复生成结果",
                result_ref=result_ref,
                error_code=None,
                error_message=None,
            )

    def _published_result_ref(
        self,
        task: DurableTask | None,
        *,
        now: float,
    ) -> dict[str, str] | None:
        if task is None or task.status not in {"pending", "leased"}:
            return None
        if task.cancel_requested:
            return None
        if task.deadline_at is not None and task.deadline_at <= now:
            return None
        command = dict(task.command or {})
        resource_type = str(command.get("resource_type") or "").strip()
        course_id = str(command.get("course_id") or task.course_id or "").strip()
        material_id = str(command.get("material_id") or "").strip()
        if not resource_type or not course_id:
            return None
        if not material_id:
            matches = [
                item
                for item in self.course_storage_manager.list_generated_materials(
                    course_id,
                    resource_type,
                    owner_user_id=task.owner_user_id,
                )
                if str(item.get("source_job_id") or "").strip()
                == task.task_id
                and str(item.get("created_by") or "").strip()
                == str(task.owner_user_id or "").strip()
            ]
            if len(matches) != 1:
                return None
            material_id = str(matches[0].get("material_id") or "").strip()
            if not material_id:
                return None
        material = self.course_storage_manager.get_generated_material(
            course_id,
            resource_type,
            material_id,
            owner_user_id=task.owner_user_id,
        )
        if material is None:
            return None
        if str(material.get("source_job_id") or "").strip() != task.task_id:
            return None
        if str(material.get("created_by") or "").strip() != str(
            task.owner_user_id or ""
        ).strip():
            return None
        return {
            "resource_type": "course_material",
            "course_id": course_id,
            "material_type": resource_type,
            "material_id": material_id,
        }

    def _sync_public_ledger(self, jobs: list[EduJob]) -> None:
        for job in jobs:
            task = self.task_store.get_durable(job.edu_job_id)
            if task is None:
                if job.kind in _DURABLE_JOB_KINDS:
                    update_job(
                        job.edu_job_id,
                        status=JobStatus.FAILED,
                        step="legacy_unrecoverable",
                        progress=100,
                        message="旧任务缺少可恢复命令，请重新提交",
                        error_code="LEGACY_TASK_NOT_RECOVERABLE",
                        error_message="任务由旧版临时执行器创建，重启后无法恢复",
                    )
                continue
            if task.status == "pending" and task.error_code == "LEASE_EXPIRED":
                update_job(
                    job.edu_job_id,
                    status=JobStatus.QUEUED,
                    step="recovered",
                    progress=0,
                    message="后台任务已恢复，正在重新排队",
                    error_code=None,
                    error_message=None,
                )
            elif task.status == "failed":
                update_job(
                    job.edu_job_id,
                    status=JobStatus.FAILED,
                    step="failed",
                    progress=100,
                    message="后台工作器中断，任务无法继续",
                    error_code=task.error_code or "WORKER_LOST",
                    error_message=task.error or "后台工作器租约已失效",
                )
            elif task.status == "succeeded":
                update_job(
                    job.edu_job_id,
                    status=JobStatus.SUCCEEDED,
                    step="reconciled",
                    progress=100,
                    message="已恢复任务完成状态",
                    result_ref=task.result_ref,
                    error_code=None,
                    error_message=None,
                )
            elif task.status == "partially_succeeded":
                update_job(
                    job.edu_job_id,
                    status=JobStatus.PARTIALLY_SUCCEEDED,
                    step="resource_verification_failed",
                    progress=100,
                    message="内容已生成，但结果资源无法确认",
                    result_ref=task.result_ref,
                    error_code=task.error_code,
                    error_message=task.error,
                )
            elif task.status == "canceled":
                update_job(
                    job.edu_job_id,
                    status=JobStatus.CANCELED,
                    step="canceled",
                    progress=100,
                    message="任务已取消",
                    error_code="GENERATION_CANCELLED",
                    error_message=task.error or "Generation was canceled",
                )

    def _audit_succeeded_results(self) -> None:
        jobs: list[EduJob] = []
        cursor: str | None = None
        while True:
            page = list_job_page(
                statuses=[JobStatus.SUCCEEDED],
                limit=200,
                cursor=cursor,
            )
            jobs.extend(page.items)
            cursor = page.next_cursor
            if cursor is None:
                break
        for job in jobs:
            task = self.task_store.get_durable(job.edu_job_id)
            if task is None or task.status != "succeeded":
                continue
            result_ref = dict(task.result_ref or job.result_ref or {})
            if result_ref.get("resource_type") != "course_material":
                continue
            course_id = str(
                result_ref.get("course_id") or job.course_id or ""
            ).strip()
            material_type = str(
                result_ref.get("material_type") or ""
            ).strip()
            material_id = str(
                result_ref.get("material_id") or ""
            ).strip()
            material = (
                self.course_storage_manager.get_generated_material(
                    course_id,
                    material_type,
                    material_id,
                    owner_user_id=job.owner_user_id,
                )
                if course_id and material_type and material_id
                else None
            )
            if material is None:
                reconcile_succeeded_job(
                    job.edu_job_id,
                    error_code="RESOURCE_READBACK_FAILED",
                    error_message="结果资源不存在或当前用户无权读取",
                )
            elif (
                str(material.get("source_job_id") or "").strip()
                != job.edu_job_id
                or str(material.get("created_by") or "").strip()
                != str(job.owner_user_id or "").strip()
            ):
                reconcile_succeeded_job(
                    job.edu_job_id,
                    error_code="RESOURCE_PROVENANCE_MISMATCH",
                    error_message="结果资源来源任务与当前任务不一致",
                )
