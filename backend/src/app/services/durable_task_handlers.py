from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol


class UnsupportedTaskHandler(LookupError):
    pass


class DurableTaskExecutionError(RuntimeError):
    """Non-retryable business failure with a stable public error code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code or "TASK_EXECUTION_FAILED").strip()
        super().__init__(str(message or "Task execution failed"))


@dataclass(frozen=True)
class DurableExecutionContext:
    task_id: str
    owner_user_id: str
    course_id: str | None
    config_snapshot_id: str | None
    progress: Callable[[int, str, str], None]
    is_cancel_requested: Callable[[], bool]


class DurableTaskHandler(Protocol):
    def __call__(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> Mapping[str, Any]:
        raise NotImplementedError


class DurableTaskHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[tuple[str, int], DurableTaskHandler] = {}

    def register(
        self,
        workflow_type: str,
        handler_version: int,
        handler: DurableTaskHandler,
    ) -> None:
        key = self._key(workflow_type, handler_version)
        if key in self._handlers:
            raise ValueError(
                f"handler already registered for {key[0]} v{key[1]}"
            )
        self._handlers[key] = handler

    def resolve(
        self,
        workflow_type: str,
        handler_version: int,
    ) -> DurableTaskHandler:
        key = self._key(workflow_type, handler_version)
        handler = self._handlers.get(key)
        if handler is None:
            raise UnsupportedTaskHandler(
                f"unsupported durable task handler {key[0]} v{key[1]}"
            )
        return handler

    @staticmethod
    def _key(workflow_type: str, handler_version: int) -> tuple[str, int]:
        normalized_workflow = str(workflow_type or "").strip()
        normalized_version = int(handler_version)
        if not normalized_workflow:
            raise ValueError("workflow_type is required")
        if normalized_version < 1:
            raise ValueError("handler_version must be positive")
        return normalized_workflow, normalized_version
