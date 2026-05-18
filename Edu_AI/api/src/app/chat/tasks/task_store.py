from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Optional


class TaskRecord:
    def __init__(
        self,
        task_id: str,
        workflow_type: str = "",
        on_complete: Optional[Callable] = None,
    ):
        self.task_id = task_id
        self.workflow_type = workflow_type
        self.status = "pending"  # pending | running | completed | failed
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now()
        self._on_complete = on_complete

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "workflow_type": self.workflow_type,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
        }


class TaskStore:
    TTL_SECONDS = 3600  # tasks expire after 1 hour

    def __init__(self):
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

    def create(self, *, workflow_type: str = "", on_complete: Optional[Callable] = None) -> str:
        task_id = str(uuid.uuid4())
        record = TaskRecord(task_id=task_id, workflow_type=workflow_type, on_complete=on_complete)
        with self._lock:
            self._tasks[task_id] = record
        self._cleanup()
        return task_id

    def mark_running(self, task_id: str) -> None:
        with self._lock:
            t = self._tasks.get(task_id)
            if t:
                t.status = "running"
                t.updated_at = datetime.now()

    def mark_complete(self, task_id: str, result: dict) -> None:
        callback = None
        with self._lock:
            t = self._tasks.get(task_id)
            if t:
                t.status = "completed"
                t.result = result
                t.updated_at = datetime.now()
                callback = t._on_complete
        if callback:
            try:
                callback(result)
            except Exception:
                pass

    def mark_failed(self, task_id: str, error: str) -> None:
        with self._lock:
            t = self._tasks.get(task_id)
            if t:
                t.status = "failed"
                t.error = error
                t.updated_at = datetime.now()

    def get(self, task_id: str) -> Optional[dict]:
        with self._lock:
            t = self._tasks.get(task_id)
            return t.to_dict() if t else None

    def _cleanup(self) -> None:
        cutoff = datetime.now() - timedelta(seconds=self.TTL_SECONDS)
        with self._lock:
            expired = [tid for tid, t in self._tasks.items() if t.updated_at < cutoff]
            for tid in expired:
                del self._tasks[tid]


_store = TaskStore()


def get_task_store() -> TaskStore:
    return _store
