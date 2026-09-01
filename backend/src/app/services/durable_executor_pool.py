"""Bounded lifecycle owner for durable task executor threads."""

from __future__ import annotations

import threading
import time

from app.chat.tasks.task_store import TaskStore
from app.services.durable_task_executor import DurableTaskExecutor
from app.services.durable_task_handlers import DurableTaskHandlerRegistry
from app.services.job_completion_service import JobCompletionService


class DurableExecutorPool:
    def __init__(
        self,
        *,
        task_store: TaskStore,
        handler_registry: DurableTaskHandlerRegistry,
        completion_service: JobCompletionService,
        worker_count: int,
        lease_seconds: float = 45,
        heartbeat_interval: float = 10,
        poll_interval: float = 0.5,
    ) -> None:
        if int(worker_count) < 1:
            raise ValueError("worker_count must be positive")
        self.task_store = task_store
        self.handler_registry = handler_registry
        self.completion_service = completion_service
        pool_id = f"durable-{id(self):x}"
        self.executors = tuple(
            DurableTaskExecutor(
                task_store=task_store,
                handler_registry=handler_registry,
                completion_service=completion_service,
                worker_id=f"{pool_id}-{index + 1}",
                lease_seconds=lease_seconds,
                heartbeat_interval=heartbeat_interval,
                poll_interval=poll_interval,
            )
            for index in range(int(worker_count))
        )
        self._lock = threading.RLock()
        self._started = False

    @property
    def worker_count(self) -> int:
        return len(self.executors)

    @property
    def worker_ids(self) -> tuple[str, ...]:
        return tuple(executor.worker_id for executor in self.executors)

    def start(self) -> None:
        with self._lock:
            if self._started or any(
                executor.is_running for executor in self.executors
            ):
                return
            for executor in self.executors:
                executor.start()
            self._started = True

    def stop(self, *, timeout_seconds: float = 10) -> tuple[str, ...]:
        with self._lock:
            for executor in self.executors:
                executor.request_stop()
            deadline = time.monotonic() + max(0, float(timeout_seconds))
            for executor in self.executors:
                remaining = max(0.0, deadline - time.monotonic())
                executor.join(timeout_seconds=remaining)
            stuck = tuple(
                executor.worker_id
                for executor in self.executors
                if executor.is_running
            )
            self._started = bool(stuck)
            return stuck
