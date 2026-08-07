from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.chat.tasks.task_store import DurableTask, LeaseRecoverySummary, TaskStore
from app.services.durable_task_handlers import (
    DurableExecutionContext,
    DurableTaskHandlerRegistry,
    UnsupportedTaskHandler,
)
from app.services.job_completion_service import JobCompletionService
from app.services.job_store import JobStatus, update_job
from app.services.runtime_config_resolver import (
    reset_runtime_config_context,
    set_runtime_config_context,
)
from core.course_storage import (
    reset_generation_persistence_context,
    set_generation_persistence_context,
)


log = logging.getLogger(__name__)


class RetryableTaskError(RuntimeError):
    def __init__(self, message: str, *, code: str = "RETRYABLE_TASK_ERROR"):
        super().__init__(message)
        self.code = code


class DurableTaskExecutor:
    def __init__(
        self,
        *,
        task_store: TaskStore,
        handler_registry: DurableTaskHandlerRegistry,
        completion_service: JobCompletionService,
        worker_id: str | None = None,
        lease_seconds: float = 45,
        heartbeat_interval: float = 10,
        poll_interval: float = 0.5,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if heartbeat_interval <= 0 or heartbeat_interval >= lease_seconds:
            raise ValueError(
                "heartbeat_interval must be positive and shorter than lease"
            )
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self.task_store = task_store
        self.handler_registry = handler_registry
        self.completion_service = completion_service
        self.worker_id = str(
            worker_id or f"worker-{uuid.uuid4().hex[:12]}"
        )
        self.lease_seconds = float(lease_seconds)
        self.heartbeat_interval = float(heartbeat_interval)
        self.poll_interval = float(poll_interval)
        self.recovery_interval = max(
            self.poll_interval,
            min(self.lease_seconds / 2, 5.0),
        )
        self._next_recovery_at = 0.0
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._lifecycle_lock = threading.RLock()

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._worker_thread and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self.run_forever,
                daemon=True,
                name=self.worker_id,
            )
            self._worker_thread.start()

    def request_stop(self) -> None:
        self._stop_event.set()

    def join(self, *, timeout_seconds: float = 10) -> bool:
        worker = self._worker_thread
        if worker and worker.is_alive():
            worker.join(timeout=max(0, float(timeout_seconds)))
        return worker is None or not worker.is_alive()

    @property
    def is_running(self) -> bool:
        worker = self._worker_thread
        return bool(worker and worker.is_alive())

    def stop(self, *, grace_seconds: float = 10) -> None:
        self.request_stop()
        self.join(timeout_seconds=grace_seconds)

    def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                processed = self.run_once()
            except Exception:
                log.exception(
                    "Durable worker %s failed during its polling loop",
                    self.worker_id,
                )
                processed = False
            if not processed:
                self._stop_event.wait(self.poll_interval)

    def run_once(self, *, now: float | datetime | None = None) -> bool:
        active_now = self._timestamp(now)
        if active_now >= self._next_recovery_at:
            recovery = self.task_store.recover_expired_leases(now=active_now)
            self._publish_recovery(recovery)
            self._next_recovery_at = active_now + self.recovery_interval
        task = self.task_store.claim_next(
            lease_owner=self.worker_id,
            lease_seconds=self.lease_seconds,
            now=active_now,
        )
        if task is None:
            return False
        self._execute(task, fixed_now=active_now if now is not None else None)
        return True

    def _publish_recovery(self, recovery: LeaseRecoverySummary) -> None:
        for task_id in recovery.requeued_task_ids:
            update_job(
                task_id,
                status=JobStatus.QUEUED,
                step="recovered",
                progress=0,
                message="后台任务已恢复，正在重新排队",
                error_code=None,
                error_message=None,
            )
        for task_id in recovery.failed_task_ids:
            task = self.task_store.get_durable(task_id)
            update_job(
                task_id,
                status=JobStatus.FAILED,
                step="failed",
                progress=100,
                message="任务未能在规定时间内完成",
                error_code=(task.error_code if task else None) or "WORKER_LOST",
                error_message=(task.error if task else None)
                or "后台任务已停止，请重新提交",
            )
        for task_id in recovery.canceled_task_ids:
            update_job(
                task_id,
                status=JobStatus.CANCELED,
                step="canceled",
                progress=100,
                message="任务已取消",
                error_code="GENERATION_CANCELLED",
                error_message="任务已取消",
            )

    def _execute(
        self,
        task: DurableTask,
        *,
        fixed_now: float | None = None,
    ) -> None:
        if self.task_store.is_cancel_requested(task.task_id):
            self.completion_service.cancel(
                task,
                lease_owner=self.worker_id,
                now=fixed_now,
            )
            return
        if self._deadline_exceeded(task, now=fixed_now):
            self._fail_deadline(task, now=fixed_now)
            return
        update_job(
            task.task_id,
            status=JobStatus.RUNNING,
            step="running",
            progress=1,
            message="任务已由后台工作器接管",
        )
        try:
            handler = self.handler_registry.resolve(
                task.workflow_type,
                task.handler_version,
            )
        except UnsupportedTaskHandler as exc:
            self.completion_service.fail(
                task,
                lease_owner=self.worker_id,
                error_code="UNSUPPORTED_HANDLER_VERSION",
                error=str(exc),
            )
            return

        heartbeat_stop = threading.Event()
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(task.task_id, heartbeat_stop),
            daemon=True,
            name=f"{self.worker_id}-heartbeat",
        )
        heartbeat_thread.start()
        try:
            context = DurableExecutionContext(
                task_id=task.task_id,
                owner_user_id=task.owner_user_id,
                course_id=task.course_id,
                config_snapshot_id=task.config_snapshot_id,
                progress=lambda progress, step, message: self._publish_progress(
                    task.task_id,
                    progress,
                    step,
                    message,
                ),
                is_cancel_requested=lambda: self.task_store.is_cancel_requested(
                    task.task_id
                ),
            )
            command = dict(task.command or {})
            snapshot = command.get("runtime_config_snapshot")
            runtime_tokens = set_runtime_config_context(
                owner_user_id=task.owner_user_id,
                snapshot=dict(snapshot) if isinstance(snapshot, Mapping) else {},
            )
            persistence_token = set_generation_persistence_context(
                owner_user_id=task.owner_user_id,
                source_job_id=task.task_id,
                config_snapshot_id=task.config_snapshot_id,
            )
            try:
                generated_result = dict(handler(command, context))
            finally:
                reset_generation_persistence_context(persistence_token)
                reset_runtime_config_context(runtime_tokens)

            if self.task_store.is_cancel_requested(task.task_id):
                self.completion_service.cancel(
                    task,
                    lease_owner=self.worker_id,
                    now=fixed_now,
                )
                return
            if self._deadline_exceeded(task, now=fixed_now):
                self._fail_deadline(task, now=fixed_now)
                return
            finished = self.completion_service.finish(
                task,
                lease_owner=self.worker_id,
                generated_result=generated_result,
                now=fixed_now,
            )
            if not finished:
                self._converge_terminal_request(task, now=fixed_now)
        except RetryableTaskError as exc:
            self._requeue_retryable(task, exc)
        except Exception as exc:
            self.completion_service.fail(
                task,
                lease_owner=self.worker_id,
                error_code="TASK_EXECUTION_FAILED",
                error=str(exc),
            )
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=self.heartbeat_interval + 0.5)

    def _converge_terminal_request(
        self,
        task: DurableTask,
        *,
        now: float | None,
    ) -> None:
        if self.task_store.is_cancel_requested(task.task_id):
            self.completion_service.cancel(
                task,
                lease_owner=self.worker_id,
                now=now,
            )
        elif self._deadline_exceeded(task, now=now):
            self._fail_deadline(task, now=now)

    def _fail_deadline(
        self,
        task: DurableTask,
        *,
        now: float | None = None,
    ) -> bool:
        return self.completion_service.fail(
            task,
            lease_owner=self.worker_id,
            error_code="GENERATION_DEADLINE_EXCEEDED",
            error="Generation deadline exceeded",
            now=now,
        )

    @staticmethod
    def _deadline_exceeded(
        task: DurableTask,
        *,
        now: float | None,
    ) -> bool:
        if task.deadline_at is None:
            return False
        active_now = float(now if now is not None else time.time())
        return task.deadline_at <= active_now

    @staticmethod
    def _timestamp(value: float | datetime | None) -> float:
        if value is None:
            return time.time()
        if isinstance(value, datetime):
            active = value
            if active.tzinfo is None:
                active = active.replace(tzinfo=timezone.utc)
            return active.timestamp()
        return float(value)

    def _heartbeat_loop(
        self,
        task_id: str,
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.wait(self.heartbeat_interval):
            renewed = self.task_store.heartbeat(
                task_id,
                lease_owner=self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            if not renewed:
                return

    def _publish_progress(
        self,
        task_id: str,
        progress: int,
        step: str,
        message: str,
    ) -> None:
        normalized_progress = max(0, min(99, int(progress)))
        payload = {
            "progress": normalized_progress,
            "step": str(step or "running"),
            "message": str(message or ""),
        }
        self.task_store.update_progress(task_id, payload)
        update_job(
            task_id,
            status=JobStatus.RUNNING,
            progress=normalized_progress,
            step=payload["step"],
            message=payload["message"],
        )

    def _requeue_retryable(
        self,
        task: DurableTask,
        exc: RetryableTaskError,
    ) -> None:
        backoff_seconds = min(2 ** task.attempt_count, 30)
        self.task_store.release_for_retry(
            task.task_id,
            lease_owner=self.worker_id,
            available_at=time.time() + backoff_seconds,
            error_code=exc.code,
            error=str(exc),
        )
        latest = self.task_store.get_durable(task.task_id)
        if latest is None:
            return
        if latest.status == "failed":
            update_job(
                task.task_id,
                status=JobStatus.FAILED,
                step="failed",
                progress=100,
                message="任务超过最大自动尝试次数",
                error_code=latest.error_code,
                error_message=latest.error,
            )
            return
        update_job(
            task.task_id,
            status=JobStatus.QUEUED,
            step="retry_wait",
            progress=0,
            message="后台服务暂不可用，任务将自动重试",
            error_code=exc.code,
            error_message=str(exc),
        )
