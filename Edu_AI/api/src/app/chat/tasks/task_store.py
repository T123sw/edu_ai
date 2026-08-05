from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

# Default DB path: <repo>/api/data/tasks.db, overridable via env var.
_DEFAULT_DB_PATH = os.getenv(
    "TASKS_DB_PATH",
    str(Path(__file__).resolve().parents[4] / "data" / "tasks.db"),
)

TTL_SECONDS = 3600  # tasks expire after 1 hour


def _now_ts() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now().isoformat()


class TaskStore:
    TTL_SECONDS = TTL_SECONDS

    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._callbacks: dict[str, Callable] = {}
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id      TEXT PRIMARY KEY,
                workflow_type TEXT NOT NULL DEFAULT '',
                owner_user_id TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'pending',
                result_json  TEXT,
                error        TEXT,
                progress_json TEXT,
                created_at   TEXT NOT NULL,
                updated_at   REAL NOT NULL
            )
        """)
        columns = {
            str(row[1])
            for row in self._conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "owner_user_id" not in columns:
            self._conn.execute(
                "ALTER TABLE tasks ADD COLUMN owner_user_id TEXT NOT NULL DEFAULT ''"
            )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        workflow_type: str = "",
        owner_user_id: str = "",
        task_id: Optional[str] = None,
        on_complete: Optional[Callable] = None,
    ) -> str:
        task_id = str(task_id or uuid.uuid4())
        now_iso = _now_iso()
        now_ts = _now_ts()
        with self._lock:
            self._conn.execute(
                "INSERT INTO tasks (task_id, workflow_type, owner_user_id, status, created_at, updated_at)"
                " VALUES (?, ?, ?, 'pending', ?, ?)",
                (task_id, workflow_type, str(owner_user_id or "").strip(), now_iso, now_ts),
            )
            self._conn.commit()
            if on_complete:
                self._callbacks[task_id] = on_complete
        self._cleanup()
        return task_id

    def mark_running(self, task_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE tasks SET status='running', updated_at=? WHERE task_id=?",
                (_now_ts(), task_id),
            )
            self._conn.commit()

    def mark_complete(self, task_id: str, result: dict) -> None:
        callback = None
        result_json = json.dumps(result, ensure_ascii=False, default=str)
        with self._lock:
            self._conn.execute(
                "UPDATE tasks SET status='completed', result_json=?, progress_json=NULL, updated_at=? WHERE task_id=?",
                (result_json, _now_ts(), task_id),
            )
            self._conn.commit()
            callback = self._callbacks.pop(task_id, None)
        if callback:
            try:
                callback(result)
            except Exception:
                pass

    def mark_failed(self, task_id: str, error: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE tasks SET status='failed', error=?, updated_at=? WHERE task_id=?",
                (str(error), _now_ts(), task_id),
            )
            self._conn.commit()

    def update_progress(self, task_id: str, progress: dict) -> None:
        """Write intermediate progress without changing the task status."""
        progress_json = json.dumps(progress, ensure_ascii=False, default=str)
        with self._lock:
            self._conn.execute(
                "UPDATE tasks SET progress_json=?, updated_at=? WHERE task_id=? AND status='running'",
                (progress_json, _now_ts(), task_id),
            )
            self._conn.commit()

    def get(
        self, task_id: str, *, owner_user_id: Optional[str] = None
    ) -> Optional[dict]:
        with self._lock:
            if owner_user_id is None:
                row = self._conn.execute(
                    "SELECT * FROM tasks WHERE task_id=?", (task_id,)
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT * FROM tasks WHERE task_id=? AND owner_user_id=?",
                    (task_id, str(owner_user_id or "").strip()),
                ).fetchone()
        if row is None:
            return None
        result = json.loads(row["result_json"]) if row["result_json"] else None
        progress = json.loads(row["progress_json"]) if row["progress_json"] else None
        out: dict[str, Any] = {
            "task_id": row["task_id"],
            "workflow_type": row["workflow_type"],
            "owner_user_id": row["owner_user_id"],
            "status": row["status"],
            "result": result,
            "error": row["error"],
            "created_at": row["created_at"],
        }
        if progress is not None:
            out["progress"] = progress
        return out

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _cleanup(self) -> None:
        cutoff = _now_ts() - self.TTL_SECONDS
        with self._lock:
            expired = [
                row[0]
                for row in self._conn.execute(
                    "SELECT task_id FROM tasks WHERE updated_at < ?", (cutoff,)
                ).fetchall()
            ]
            for tid in expired:
                self._callbacks.pop(tid, None)
            self._conn.execute("DELETE FROM tasks WHERE updated_at < ?", (cutoff,))
            self._conn.commit()


# ------------------------------------------------------------------
# Singleton — lazy so DB is created on first use, not at import time.
# ------------------------------------------------------------------

_store: Optional[TaskStore] = None
_store_init_lock = threading.Lock()


def get_task_store() -> TaskStore:
    global _store
    if _store is None:
        with _store_init_lock:
            if _store is None:
                _store = TaskStore()
    return _store
