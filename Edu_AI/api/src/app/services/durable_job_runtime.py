from __future__ import annotations

import threading
from typing import Any

from app.chat.tasks.task_store import TaskStore, get_task_store
from app.services.durable_executor_pool import DurableExecutorPool
from app.services.durable_task_handlers import DurableTaskHandlerRegistry
from app.services.generation_task_handlers import (
    GenerationTaskHandler,
    register_generation_task_handlers,
)
from app.services.job_completion_service import JobCompletionService
from app.services.job_reconciliation_service import JobReconciliationService
from app.services.platform_task_handlers import register_platform_task_handlers
from core.course_storage import CourseStorageManager
from core.config import Config


class DurableJobRuntime:
    def __init__(
        self,
        *,
        task_store: TaskStore,
        executor: Any,
        reconciler: Any,
        handler_registry: DurableTaskHandlerRegistry | None = None,
    ) -> None:
        self.task_store = task_store
        self.executor = executor
        self.reconciler = reconciler
        self.handler_registry = handler_registry or DurableTaskHandlerRegistry()
        self._lock = threading.RLock()
        self._started = False

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self.reconciler.reconcile_startup()
            self.executor.start()
            self._started = True

    def stop(self, *, grace_seconds: float = 10) -> None:
        with self._lock:
            if not self._started:
                return
            self.executor.stop(timeout_seconds=grace_seconds)
            self._started = False


def build_durable_job_runtime(
    *,
    task_store: TaskStore | None = None,
) -> DurableJobRuntime:
    store = task_store or get_task_store()
    manager = CourseStorageManager()
    registry = DurableTaskHandlerRegistry()
    generation_handler = GenerationTaskHandler(
        course_storage_manager=manager,
    )
    register_generation_task_handlers(
        registry,
        handler=generation_handler,
    )
    register_platform_task_handlers(registry)
    completion = JobCompletionService(
        task_store=store,
        course_storage_manager=manager,
    )
    executor = DurableExecutorPool(
        task_store=store,
        handler_registry=registry,
        completion_service=completion,
        worker_count=Config.DURABLE_JOB_WORKERS,
    )
    reconciler = JobReconciliationService(
        task_store=store,
        course_storage_manager=manager,
    )
    return DurableJobRuntime(
        task_store=store,
        executor=executor,
        reconciler=reconciler,
        handler_registry=registry,
    )
