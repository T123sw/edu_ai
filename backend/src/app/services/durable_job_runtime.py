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
    worker_count: int | None = None,
    control_worker_count: int | None = None,
    light_worker_count: int | None = None,
    exclude_control_from_general: bool = False,
) -> DurableJobRuntime:
    from app.integrations.hyperframes.build_info import runtime_info
    import logging
    logging.getLogger(__name__).info('Generation build: %s', runtime_info())
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
    from app.services.personal_studio import PersonalStudioTaskHandler
    registry.register("personal_studio", 1, PersonalStudioTaskHandler(generator=generation_handler, manager=manager))
    from app.artifact_revision.jobs import ArtifactRevisionTaskHandler
    registry.register("artifact_revision", 1, ArtifactRevisionTaskHandler())
    from app.course_preparation.runner import PreparationStepHandler
    from app.course_preparation.dependencies import configured_runner
    registry.register("preparation_step", 1, PreparationStepHandler(configured_runner))
    from app.course_preparation.adapters.generation import PreparationResourceHandler
    from app.course_preparation.application import application
    registry.register("preparation_resource", 1, PreparationResourceHandler(application))
    from app.practice.service import PracticeTaskHandler
    registry.register("practice_generate", 1, PracticeTaskHandler())
    from app.pbl.service import PblTaskHandler
    registry.register("pbl_generate", 1, PblTaskHandler())
    from app.exam_generation.service import ExamGenerationHandler
    registry.register("exam_generate", 1, ExamGenerationHandler())
    from app.exam_practice.worker import PracticeWorker
    registry.register("exam_practice", 1, PracticeWorker())
    completion = JobCompletionService(
        task_store=store,
        course_storage_manager=manager,
    )
    executor = DurableExecutorPool(
        task_store=store,
        handler_registry=registry,
        completion_service=completion,
        exclude_control_from_general=exclude_control_from_general,
        worker_count=Config.DURABLE_JOB_WORKERS if worker_count is None else worker_count,
        light_worker_count=Config.DURABLE_JOB_LIGHT_WORKERS if light_worker_count is None else light_worker_count,
        control_worker_count=Config.DURABLE_JOB_CONTROL_WORKERS if control_worker_count is None else control_worker_count,
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
