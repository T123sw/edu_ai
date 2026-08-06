from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.chat.tasks.task_store import DurableTask, TaskStore
from app.services.job_store import JobStatus, update_job
from core.course_storage import CourseStorageManager


class JobCompletionService:
    def __init__(
        self,
        *,
        task_store: TaskStore,
        course_storage_manager: CourseStorageManager | None = None,
    ) -> None:
        self.task_store = task_store
        self.course_storage_manager = (
            course_storage_manager or CourseStorageManager()
        )

    def finish(
        self,
        task: DurableTask,
        *,
        lease_owner: str,
        generated_result: Mapping[str, Any],
    ) -> bool:
        result = dict(generated_result)
        result_ref = dict(result.get("result_ref") or {})
        if not bool(result.get("saved", True)):
            return self._finish_partial(
                task,
                lease_owner=lease_owner,
                result=result,
                result_ref=result_ref,
                error_code="RESOURCE_SAVE_FAILED",
                error=str(result.get("error") or "结果资源保存失败"),
            )

        error_code, error = self._verify_result(task, result_ref)
        if error_code:
            return self._finish_partial(
                task,
                lease_owner=lease_owner,
                result=result,
                result_ref=result_ref,
                error_code=error_code,
                error=error,
            )

        persisted = self.task_store.mark_succeeded(
            task.task_id,
            lease_owner=lease_owner,
            result=result,
            result_ref=result_ref,
        )
        if not persisted:
            return False
        update_job(
            task.task_id,
            status=JobStatus.SUCCEEDED,
            step="completed",
            progress=100,
            message="生成完成，结果已保存到课程资源",
            result_ref=result_ref,
            error_code=None,
            error_message=None,
        )
        return True

    def fail(
        self,
        task: DurableTask,
        *,
        lease_owner: str,
        error_code: str,
        error: str,
    ) -> bool:
        persisted = self.task_store.mark_failed(
            task.task_id,
            error,
            lease_owner=lease_owner,
            error_code=error_code,
        )
        if not persisted:
            return False
        update_job(
            task.task_id,
            status=JobStatus.FAILED,
            step="failed",
            progress=100,
            message="任务执行失败",
            error_code=error_code,
            error_message=error,
        )
        return True

    def cancel(self, task: DurableTask, *, lease_owner: str) -> bool:
        persisted = self.task_store.mark_canceled(
            task.task_id,
            lease_owner=lease_owner,
        )
        if not persisted:
            return False
        update_job(
            task.task_id,
            status=JobStatus.CANCELED,
            step="canceled",
            progress=100,
            message="任务已取消",
            result_ref=None,
        )
        return True

    def _finish_partial(
        self,
        task: DurableTask,
        *,
        lease_owner: str,
        result: dict[str, Any],
        result_ref: dict[str, Any],
        error_code: str,
        error: str,
    ) -> bool:
        persisted = self.task_store.mark_partially_succeeded(
            task.task_id,
            lease_owner=lease_owner,
            result=result,
            result_ref=result_ref,
            error_code=error_code,
            error=error,
        )
        if not persisted:
            return False
        update_job(
            task.task_id,
            status=JobStatus.PARTIALLY_SUCCEEDED,
            step="resource_verification_failed",
            progress=100,
            message="内容已生成，但结果资源无法确认",
            result_ref=result_ref or None,
            error_code=error_code,
            error_message=error,
        )
        return True

    def _verify_result(
        self,
        task: DurableTask,
        result_ref: dict[str, Any],
    ) -> tuple[str | None, str]:
        if not result_ref:
            return "RESOURCE_READBACK_FAILED", "任务没有返回可读取的结果引用"
        if result_ref.get("resource_type") != "course_material":
            return None, ""

        course_id = str(
            result_ref.get("course_id") or task.course_id or ""
        ).strip()
        material_type = str(result_ref.get("material_type") or "").strip()
        material_id = str(result_ref.get("material_id") or "").strip()
        if not course_id or not material_type or not material_id:
            return (
                "RESOURCE_READBACK_FAILED",
                "课程资源结果引用缺少 course/type/id",
            )
        material = self.course_storage_manager.get_generated_material(
            course_id,
            material_type,
            material_id,
            owner_user_id=task.owner_user_id,
        )
        if material is None:
            return (
                "RESOURCE_READBACK_FAILED",
                "结果资源不存在或当前用户无权读取",
            )
        if str(material.get("course_id") or "").strip() != course_id:
            return "RESOURCE_IDENTITY_MISMATCH", "结果资源课程标识不一致"
        if str(material.get("material_type") or "").strip() != material_type:
            return "RESOURCE_IDENTITY_MISMATCH", "结果资源类型不一致"
        if str(material.get("material_id") or "").strip() != material_id:
            return "RESOURCE_IDENTITY_MISMATCH", "结果资源 ID 不一致"
        if str(material.get("source_job_id") or "").strip() != task.task_id:
            return (
                "RESOURCE_PROVENANCE_MISMATCH",
                "结果资源来源任务与当前任务不一致",
            )
        if str(material.get("created_by") or "").strip() != str(
            task.owner_user_id or ""
        ).strip():
            return (
                "RESOURCE_PROVENANCE_MISMATCH",
                "结果资源创建者与当前任务所有者不一致",
            )
        return None, ""
