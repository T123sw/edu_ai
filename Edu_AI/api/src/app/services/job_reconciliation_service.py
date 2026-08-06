from __future__ import annotations

import time
from collections.abc import Callable

from app.chat.tasks.task_store import DurableTask, TaskStore
from app.services.job_store import (
    ACTIVE_JOB_STATUSES,
    EduJob,
    JobStatus,
    list_job_page,
    update_job,
)
from core.course_storage import CourseStorageManager


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
        now = float(self.now_provider())
        active_jobs = self._active_jobs()
        self._finish_published_results(active_jobs, now=now)
        self.task_store.recover_expired_leases(now=now)
        self._sync_public_ledger(self._active_jobs())

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
            result_ref = self._published_result_ref(task)
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
    ) -> dict[str, str] | None:
        if task is None or task.status not in {"pending", "leased"}:
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
                # Platform/legacy jobs are migrated in the next rollout step.
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
            elif task.status == "canceled":
                update_job(
                    job.edu_job_id,
                    status=JobStatus.CANCELED,
                    step="canceled",
                    progress=100,
                    message="任务已取消",
                )
