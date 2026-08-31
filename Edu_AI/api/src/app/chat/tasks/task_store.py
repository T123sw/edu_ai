from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Callable, Mapping, Optional

# Default DB path: <repo>/api/data/tasks.db, overridable via env var.
_DEFAULT_DB_PATH = os.getenv(
    "TASKS_DB_PATH",
    str(Path(__file__).resolve().parents[4] / "data" / "tasks.db"),
)

TTL_SECONDS = 3600
DEFAULT_TASK_DEADLINE_SECONDS = 300
TERMINAL_TASK_STATUSES = (
    "completed",
    "succeeded",
    "partially_succeeded",
    "failed",
    "canceled",
)
_SENSITIVE_COMMAND_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
}
_SENSITIVE_COMMAND_SUFFIXES = (
    "_api_key",
    "_authorization",
    "_credential",
    "_password",
    "_secret",
    "_access_token",
    "_refresh_token",
)


def _now_ts() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now().isoformat()


def _coerce_timestamp(value: float | datetime | str | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        active = value
    elif isinstance(value, str):
        active = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        return float(value)
    if active.tzinfo is None:
        active = active.replace(tzinfo=timezone.utc)
    return active.timestamp()


def _execution_deadline_at(
    command: Mapping[str, Any] | None,
    *,
    started_at: float,
) -> float | None:
    if not command or command.get("execution_timeout_seconds") is None:
        return None
    timeout_seconds = float(command["execution_timeout_seconds"])
    if timeout_seconds <= 0:
        raise ValueError("execution_timeout_seconds must be positive")
    return float(started_at) + timeout_seconds


def _queue_deadline_at(
    command: Mapping[str, Any] | None,
    *,
    queued_at: float,
) -> float | None:
    if not command or command.get("execution_timeout_seconds") is None:
        return None
    timeout_seconds = float(
        command.get("deadline_seconds") or DEFAULT_TASK_DEADLINE_SECONDS
    )
    if timeout_seconds <= 0:
        raise ValueError("deadline_seconds must be positive")
    return float(queued_at) + timeout_seconds


def _json_load(value: Any) -> Any:
    if not value:
        return None
    return json.loads(str(value))


def _validate_command_payload(
    value: Any,
    *,
    path: str = "command",
    field_name: str = "",
) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized_key = key.lower().replace("-", "_")
            if (
                normalized_key in _SENSITIVE_COMMAND_KEYS
                or normalized_key.endswith(_SENSITIVE_COMMAND_SUFFIXES)
            ):
                raise ValueError(
                    f"command payload contains sensitive field at {path}.{key}"
                )
            _validate_command_payload(
                item,
                path=f"{path}.{key}",
                field_name=normalized_key,
            )
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_command_payload(
                item,
                path=f"{path}[{index}]",
                field_name=field_name,
            )
        return
    if isinstance(value, str):
        path_field = (
            "path" in field_name
            or field_name.endswith(
                ("file", "filename", "directory", "dir", "root")
            )
        )
        if (
            path_field
            and (
                value.startswith(("/", "\\"))
                or Path(value).is_absolute()
                or PureWindowsPath(value).is_absolute()
            )
        ):
            raise ValueError(
                f"command payload contains an absolute path at {path}"
            )
        return
    if value is not None and not isinstance(value, (bool, int, float)):
        raise ValueError(f"command payload is not JSON-safe at {path}")


@dataclass(frozen=True)
class DurableTask:
    task_id: str
    workflow_type: str
    handler_version: int
    owner_user_id: str
    course_id: str | None
    scope_type: str
    scope_id: str | None
    command: dict[str, Any] | None
    config_snapshot_id: str | None
    idempotency_key: str | None
    status: str
    attempt_count: int
    max_attempts: int
    available_at: float
    lease_owner: str | None
    lease_expires_at: float | None
    heartbeat_at: float | None
    deadline_at: float | None
    cancel_requested: bool
    progress: dict[str, Any] | None
    result: dict[str, Any] | None
    result_ref: dict[str, Any] | None
    error_code: str | None
    error: str | None
    created_at: str
    started_at: float | None
    finished_at: float | None
    updated_at: float


@dataclass(frozen=True)
class LeaseRecoverySummary:
    requeued: int = 0
    failed: int = 0
    canceled: int = 0
    requeued_task_ids: tuple[str, ...] = ()
    failed_task_ids: tuple[str, ...] = ()
    canceled_task_ids: tuple[str, ...] = ()


class TaskStore:
    TTL_SECONDS = TTL_SECONDS

    _MIGRATION_COLUMNS: dict[str, str] = {
        "handler_version": "INTEGER NOT NULL DEFAULT 1",
        "course_id": "TEXT",
        "scope_type": "TEXT NOT NULL DEFAULT 'course'",
        "scope_id": "TEXT",
        "command_json": "TEXT",
        "config_snapshot_id": "TEXT",
        "idempotency_key": "TEXT",
        "attempt_count": "INTEGER NOT NULL DEFAULT 0",
        "max_attempts": "INTEGER NOT NULL DEFAULT 3",
        "available_at": "REAL NOT NULL DEFAULT 0",
        "lease_owner": "TEXT",
        "lease_expires_at": "REAL",
        "heartbeat_at": "REAL",
        "deadline_at": "REAL",
        "cancel_requested": "INTEGER NOT NULL DEFAULT 0",
        "result_ref_json": "TEXT",
        "error_code": "TEXT",
        "started_at": "REAL",
        "finished_at": "REAL",
    }

    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        self._callbacks: dict[str, Callable] = {}
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            timeout=5,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    workflow_type TEXT NOT NULL DEFAULT '',
                    owner_user_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    result_json TEXT,
                    error TEXT,
                    progress_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            columns = {
                str(row[1])
                for row in self._conn.execute(
                    "PRAGMA table_info(tasks)"
                ).fetchall()
            }
            if "owner_user_id" not in columns:
                self._conn.execute(
                    "ALTER TABLE tasks ADD COLUMN "
                    "owner_user_id TEXT NOT NULL DEFAULT ''"
                )
                columns.add("owner_user_id")
            for name, declaration in self._MIGRATION_COLUMNS.items():
                if name not in columns:
                    self._conn.execute(
                        f"ALTER TABLE tasks ADD COLUMN {name} {declaration}"
                    )
            self._conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_tasks_idempotency
                ON tasks(owner_user_id, workflow_type, idempotency_key)
                WHERE idempotency_key IS NOT NULL AND idempotency_key <> ''
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_tasks_claim
                ON tasks(status, available_at, created_at)
                """
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Durable execution interface
    # ------------------------------------------------------------------

    def enqueue(
        self,
        *,
        task_id: str,
        workflow_type: str,
        handler_version: int,
        owner_user_id: str,
        course_id: str | None,
        scope_type: str,
        scope_id: str | None,
        command: dict[str, Any],
        config_snapshot_id: str | None,
        idempotency_key: str | None,
        max_attempts: int = 3,
        available_at: float | None = None,
        deadline_at: float | datetime | str | None = None,
    ) -> DurableTask:
        normalized_task_id = str(task_id or "").strip()
        normalized_workflow = str(workflow_type or "").strip()
        normalized_owner = str(owner_user_id or "").strip()
        if not normalized_task_id:
            raise ValueError("task_id is required")
        if not normalized_workflow:
            raise ValueError("workflow_type is required")
        if not normalized_owner:
            raise ValueError("owner_user_id is required")
        if int(handler_version) < 1:
            raise ValueError("handler_version must be positive")
        if int(max_attempts) < 1:
            raise ValueError("max_attempts must be positive")
        _validate_command_payload(command)
        try:
            command_json = json.dumps(
                command,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("command payload is not JSON-safe") from exc

        normalized_idempotency_key = (
            str(idempotency_key or "").strip() or None
        )
        now = _now_ts()
        normalized_deadline = _coerce_timestamp(deadline_at)
        if normalized_deadline is None and command.get("deadline_seconds") is not None:
            deadline_seconds = float(command["deadline_seconds"])
            if deadline_seconds <= 0:
                raise ValueError("deadline_seconds must be positive")
            normalized_deadline = now + deadline_seconds
        if normalized_deadline is None:
            normalized_deadline = now + DEFAULT_TASK_DEADLINE_SECONDS
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                if normalized_idempotency_key:
                    existing = self._conn.execute(
                        """
                        SELECT * FROM tasks
                        WHERE owner_user_id=?
                          AND workflow_type=?
                          AND idempotency_key=?
                        """,
                        (
                            normalized_owner,
                            normalized_workflow,
                            normalized_idempotency_key,
                        ),
                    ).fetchone()
                    if existing is not None:
                        self._conn.commit()
                        return self._row_to_durable(existing)
                self._conn.execute(
                    """
                    INSERT INTO tasks (
                        task_id, workflow_type, handler_version,
                        owner_user_id, course_id, scope_type, scope_id,
                        command_json, config_snapshot_id, idempotency_key,
                        status, attempt_count, max_attempts, available_at,
                        deadline_at, cancel_requested, created_at, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'pending', 0, ?, ?, ?, 0, ?, ?
                    )
                    """,
                    (
                        normalized_task_id,
                        normalized_workflow,
                        int(handler_version),
                        normalized_owner,
                        str(course_id or "").strip() or None,
                        str(scope_type or "course").strip() or "course",
                        str(scope_id or "").strip() or None,
                        command_json,
                        str(config_snapshot_id or "").strip() or None,
                        normalized_idempotency_key,
                        int(max_attempts),
                        float(available_at if available_at is not None else now),
                        normalized_deadline,
                        _now_iso(),
                        now,
                    ),
                )
                row = self._conn.execute(
                    "SELECT * FROM tasks WHERE task_id=?",
                    (normalized_task_id,),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        if row is None:
            raise RuntimeError("durable task enqueue did not persist a row")
        return self._row_to_durable(row)

    def claim_next(
        self,
        *,
        lease_owner: str,
        lease_seconds: float,
        now: float | None = None,
    ) -> DurableTask | None:
        normalized_owner = str(lease_owner or "").strip()
        if not normalized_owner:
            raise ValueError("lease_owner is required")
        if float(lease_seconds) <= 0:
            raise ValueError("lease_seconds must be positive")
        active_now = float(now if now is not None else _now_ts())
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                candidate = self._conn.execute(
                    """
                    SELECT task_id, command_json, deadline_at FROM tasks
                    WHERE status='pending'
                      AND command_json IS NOT NULL
                      AND cancel_requested=0
                      AND available_at<=?
                      AND attempt_count<max_attempts
                    ORDER BY available_at ASC, created_at ASC, task_id ASC
                    LIMIT 1
                    """,
                    (active_now,),
                ).fetchone()
                if candidate is None:
                    self._conn.commit()
                    return None
                execution_deadline = _execution_deadline_at(
                    _json_load(candidate["command_json"]),
                    started_at=active_now,
                )
                cursor = self._conn.execute(
                    """
                    UPDATE tasks
                    SET status='leased',
                        lease_owner=?,
                        lease_expires_at=?,
                        heartbeat_at=?,
                        attempt_count=attempt_count+1,
                        started_at=COALESCE(started_at, ?),
                        deadline_at=?,
                        updated_at=?
                    WHERE task_id=? AND status='pending'
                    """,
                    (
                        normalized_owner,
                        active_now + float(lease_seconds),
                        active_now,
                        active_now,
                        execution_deadline
                        if execution_deadline is not None
                        else candidate["deadline_at"],
                        active_now,
                        candidate["task_id"],
                    ),
                )
                if cursor.rowcount != 1:
                    self._conn.rollback()
                    return None
                row = self._conn.execute(
                    "SELECT * FROM tasks WHERE task_id=?",
                    (candidate["task_id"],),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._row_to_durable(row) if row is not None else None

    def heartbeat(
        self,
        task_id: str,
        *,
        lease_owner: str,
        lease_seconds: float,
        now: float | None = None,
    ) -> bool:
        active_now = float(now if now is not None else _now_ts())
        with self._lock:
            cursor = self._conn.execute(
                """
                UPDATE tasks
                SET heartbeat_at=?, lease_expires_at=?, updated_at=?
                WHERE task_id=? AND status='leased' AND lease_owner=?
                """,
                (
                    active_now,
                    active_now + float(lease_seconds),
                    active_now,
                    task_id,
                    str(lease_owner or "").strip(),
                ),
            )
            self._conn.commit()
        return cursor.rowcount == 1

    def request_cancel(self, task_id: str, *, owner_user_id: str) -> bool:
        owner = str(owner_user_id or "").strip()
        now = _now_ts()
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._conn.execute(
                    """
                    SELECT status FROM tasks
                    WHERE task_id=? AND owner_user_id=?
                    """,
                    (task_id, owner),
                ).fetchone()
                if row is None:
                    self._conn.commit()
                    return False
                status = str(row["status"])
                if status == "pending":
                    self._conn.execute(
                        """
                        UPDATE tasks
                        SET status='canceled', cancel_requested=1,
                            error_code='GENERATION_CANCELLED',
                            error='Generation was canceled',
                            finished_at=?, updated_at=?
                        WHERE task_id=? AND status='pending'
                        """,
                        (now, now, task_id),
                    )
                elif status == "leased":
                    self._conn.execute(
                        """
                        UPDATE tasks
                        SET cancel_requested=1,
                            error_code='GENERATION_CANCELLED',
                            error='Generation cancellation requested',
                            updated_at=?
                        WHERE task_id=? AND status='leased'
                        """,
                        (now, task_id),
                    )
                else:
                    self._conn.commit()
                    return False
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()
                raise

    def is_cancel_requested(self, task_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT cancel_requested FROM tasks WHERE task_id=?",
                (task_id,),
            ).fetchone()
        return bool(row and row["cancel_requested"])

    def mark_succeeded(
        self,
        task_id: str,
        *,
        lease_owner: str,
        result: dict[str, Any],
        result_ref: dict[str, Any],
        now: float | None = None,
    ) -> bool:
        return self._finish_leased(
            task_id,
            lease_owner=lease_owner,
            status="succeeded",
            result=result,
            result_ref=result_ref,
            error_code=None,
            error=None,
            now=now,
        )

    def mark_partially_succeeded(
        self,
        task_id: str,
        *,
        lease_owner: str,
        result: dict[str, Any],
        result_ref: dict[str, Any],
        error_code: str,
        error: str,
        now: float | None = None,
    ) -> bool:
        return self._finish_leased(
            task_id,
            lease_owner=lease_owner,
            status="partially_succeeded",
            result=result,
            result_ref=result_ref,
            error_code=error_code,
            error=error,
            now=now,
        )

    def mark_canceled(
        self,
        task_id: str,
        *,
        lease_owner: str,
        now: float | None = None,
    ) -> bool:
        return self._finish_leased(
            task_id,
            lease_owner=lease_owner,
            status="canceled",
            result=None,
            result_ref=None,
            error_code="GENERATION_CANCELLED",
            error="Generation was canceled",
            now=now,
        )

    def release_for_retry(
        self,
        task_id: str,
        *,
        lease_owner: str,
        available_at: float,
        error_code: str,
        error: str,
        now: float | None = None,
    ) -> bool:
        active_now = float(now if now is not None else _now_ts())
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._conn.execute(
                    """
                    SELECT attempt_count, max_attempts, command_json FROM tasks
                    WHERE task_id=? AND status='leased' AND lease_owner=?
                    """,
                    (task_id, lease_owner),
                ).fetchone()
                if row is None:
                    self._conn.commit()
                    return False
                exhausted = int(row["attempt_count"]) >= int(row["max_attempts"])
                if exhausted:
                    self._conn.execute(
                        """
                        UPDATE tasks
                        SET status='failed', error_code='MAX_ATTEMPTS_EXCEEDED',
                            error=?, lease_owner=NULL, lease_expires_at=NULL,
                            heartbeat_at=NULL, finished_at=?, updated_at=?
                        WHERE task_id=? AND status='leased' AND lease_owner=?
                        """,
                        (error, active_now, active_now, task_id, lease_owner),
                    )
                else:
                    queue_deadline = _queue_deadline_at(
                        _json_load(row["command_json"]),
                        queued_at=active_now,
                    )
                    self._conn.execute(
                        """
                        UPDATE tasks
                        SET status='pending', available_at=?,
                            error_code=?, error=?, lease_owner=NULL,
                            lease_expires_at=NULL, heartbeat_at=NULL,
                            deadline_at=COALESCE(?, deadline_at),
                            updated_at=?
                        WHERE task_id=? AND status='leased' AND lease_owner=?
                        """,
                        (
                            float(available_at),
                            str(error_code or ""),
                            str(error or ""),
                            queue_deadline,
                            active_now,
                            task_id,
                            lease_owner,
                        ),
                    )
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()
                raise

    def recover_expired_leases(
        self,
        *,
        now: float | None = None,
    ) -> LeaseRecoverySummary:
        active_now = float(now if now is not None else _now_ts())
        requeued = 0
        failed = 0
        canceled = 0
        requeued_task_ids: list[str] = []
        failed_task_ids: list[str] = []
        canceled_task_ids: list[str] = []
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    """
                    UPDATE tasks
                    SET deadline_at=updated_at+?
                    WHERE status IN ('pending', 'leased')
                      AND command_json IS NOT NULL
                      AND deadline_at IS NULL
                    """,
                    (float(DEFAULT_TASK_DEADLINE_SECONDS),),
                )
                pending_timeout_rows = self._conn.execute(
                    """
                    SELECT task_id FROM tasks
                    WHERE status='pending'
                      AND deadline_at IS NOT NULL
                      AND deadline_at<=?
                    """,
                    (active_now,),
                ).fetchall()
                pending_timeouts = self._conn.execute(
                    """
                    UPDATE tasks
                    SET status='failed',
                        error_code='GENERATION_DEADLINE_EXCEEDED',
                        error='Generation deadline exceeded before execution',
                        finished_at=?, updated_at=?
                    WHERE status='pending'
                      AND deadline_at IS NOT NULL
                      AND deadline_at<=?
                    """,
                    (active_now, active_now, active_now),
                )
                failed += int(pending_timeouts.rowcount)
                failed_task_ids.extend(
                    str(row["task_id"]) for row in pending_timeout_rows
                )
                rows = self._conn.execute(
                    """
                    SELECT task_id, attempt_count, max_attempts,
                           cancel_requested, deadline_at, command_json
                    FROM tasks
                    WHERE status='leased'
                      AND lease_expires_at IS NOT NULL
                      AND lease_expires_at<=?
                    """,
                    (active_now,),
                ).fetchall()
                for row in rows:
                    if bool(row["cancel_requested"]):
                        self._conn.execute(
                            """
                            UPDATE tasks
                            SET status='canceled',
                                error_code='GENERATION_CANCELLED',
                                error='Generation was canceled after worker restart',
                                lease_owner=NULL, lease_expires_at=NULL,
                                heartbeat_at=NULL, finished_at=?, updated_at=?
                            WHERE task_id=? AND status='leased'
                            """,
                            (active_now, active_now, row["task_id"]),
                        )
                        canceled += 1
                        canceled_task_ids.append(str(row["task_id"]))
                    elif (
                        row["deadline_at"] is not None
                        and float(row["deadline_at"]) <= active_now
                    ):
                        self._conn.execute(
                            """
                            UPDATE tasks
                            SET status='failed',
                                error_code='GENERATION_DEADLINE_EXCEEDED',
                                error='Generation deadline exceeded while worker was unavailable',
                                lease_owner=NULL, lease_expires_at=NULL,
                                heartbeat_at=NULL, finished_at=?, updated_at=?
                            WHERE task_id=? AND status='leased'
                            """,
                            (active_now, active_now, row["task_id"]),
                        )
                        failed += 1
                        failed_task_ids.append(str(row["task_id"]))
                    elif int(row["attempt_count"]) >= int(row["max_attempts"]):
                        self._conn.execute(
                            """
                            UPDATE tasks
                            SET status='failed', error_code='WORKER_LOST',
                                error='Worker lease expired after maximum attempts',
                                lease_owner=NULL, lease_expires_at=NULL,
                                heartbeat_at=NULL, finished_at=?, updated_at=?
                            WHERE task_id=? AND status='leased'
                            """,
                            (active_now, active_now, row["task_id"]),
                        )
                        failed += 1
                        failed_task_ids.append(str(row["task_id"]))
                    else:
                        queue_deadline = _queue_deadline_at(
                            _json_load(row["command_json"]),
                            queued_at=active_now,
                        )
                        self._conn.execute(
                            """
                            UPDATE tasks
                            SET status='pending', available_at=?,
                                error_code='LEASE_EXPIRED',
                                error='Worker lease expired; task requeued',
                                lease_owner=NULL, lease_expires_at=NULL,
                                heartbeat_at=NULL,
                                deadline_at=COALESCE(?, deadline_at), updated_at=?
                            WHERE task_id=? AND status='leased'
                            """,
                            (
                                active_now,
                                queue_deadline,
                                active_now,
                                row["task_id"],
                            ),
                        )
                        requeued += 1
                        requeued_task_ids.append(str(row["task_id"]))
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return LeaseRecoverySummary(
            requeued=requeued,
            failed=failed,
            canceled=canceled,
            requeued_task_ids=tuple(requeued_task_ids),
            failed_task_ids=tuple(failed_task_ids),
            canceled_task_ids=tuple(canceled_task_ids),
        )

    def mark_reconciled_succeeded(
        self,
        task_id: str,
        *,
        result: Mapping[str, Any],
        result_ref: Mapping[str, Any],
        now: float | None = None,
    ) -> bool:
        """Finish a task whose resource was published before its worker stopped."""
        active_now = float(now if now is not None else _now_ts())
        result_json = json.dumps(
            dict(result),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        result_ref_json = json.dumps(
            dict(result_ref),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        with self._lock:
            cursor = self._conn.execute(
                """
                UPDATE tasks
                SET status='succeeded', result_json=?, result_ref_json=?,
                    error_code=NULL, error=NULL,
                    lease_owner=NULL, lease_expires_at=NULL,
                    heartbeat_at=NULL, finished_at=?, updated_at=?
                WHERE task_id=? AND status IN ('pending', 'leased')
                  AND cancel_requested=0
                  AND (deadline_at IS NULL OR deadline_at>?)
                """,
                (
                    result_json,
                    result_ref_json,
                    active_now,
                    active_now,
                    str(task_id or "").strip(),
                    active_now,
                ),
            )
            self._conn.commit()
        return cursor.rowcount == 1

    def get_durable(self, task_id: str) -> DurableTask | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tasks WHERE task_id=?",
                (task_id,),
            ).fetchone()
        return self._row_to_durable(row) if row is not None else None

    # ------------------------------------------------------------------
    # Legacy chat task compatibility interface
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
                """
                INSERT INTO tasks (
                    task_id, workflow_type, owner_user_id, status,
                    available_at, created_at, updated_at
                ) VALUES (?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    task_id,
                    workflow_type,
                    str(owner_user_id or "").strip(),
                    now_ts,
                    now_iso,
                    now_ts,
                ),
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
        result_json = json.dumps(result, ensure_ascii=False, default=str)
        with self._lock:
            self._conn.execute(
                """
                UPDATE tasks
                SET status='completed', result_json=?, progress_json=NULL,
                    finished_at=?, updated_at=?
                WHERE task_id=?
                """,
                (result_json, _now_ts(), _now_ts(), task_id),
            )
            self._conn.commit()
            callback = self._callbacks.pop(task_id, None)
        if callback:
            try:
                callback(result)
            except Exception:
                pass

    def mark_failed(
        self,
        task_id: str,
        error: str | None = None,
        *,
        lease_owner: str | None = None,
        error_code: str | None = None,
        now: float | None = None,
    ) -> bool | None:
        if lease_owner is not None:
            return self._finish_leased(
                task_id,
                lease_owner=lease_owner,
                status="failed",
                result=None,
                result_ref=None,
                error_code=error_code or "TASK_FAILED",
                error=error or "Task failed",
                now=now,
            )
        active_now = float(now if now is not None else _now_ts())
        with self._lock:
            self._conn.execute(
                """
                UPDATE tasks
                SET status='failed', error_code=?, error=?,
                    finished_at=?, updated_at=?
                WHERE task_id=?
                """,
                (
                    str(error_code or "") or None,
                    str(error or ""),
                    active_now,
                    active_now,
                    task_id,
                ),
            )
            self._conn.commit()
        return None

    def update_progress(self, task_id: str, progress: dict) -> None:
        progress_json = json.dumps(progress, ensure_ascii=False, default=str)
        with self._lock:
            self._conn.execute(
                """
                UPDATE tasks SET progress_json=?, updated_at=?
                WHERE task_id=? AND status IN ('running', 'leased')
                """,
                (progress_json, _now_ts(), task_id),
            )
            self._conn.commit()

    def get(
        self,
        task_id: str,
        *,
        owner_user_id: Optional[str] = None,
    ) -> Optional[dict]:
        with self._lock:
            if owner_user_id is None:
                row = self._conn.execute(
                    "SELECT * FROM tasks WHERE task_id=?",
                    (task_id,),
                ).fetchone()
            else:
                row = self._conn.execute(
                    """
                    SELECT * FROM tasks
                    WHERE task_id=? AND owner_user_id=?
                    """,
                    (task_id, str(owner_user_id or "").strip()),
                ).fetchone()
        if row is None:
            return None
        result = _json_load(row["result_json"])
        progress = _json_load(row["progress_json"])
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
    # Internal helpers
    # ------------------------------------------------------------------

    def _finish_leased(
        self,
        task_id: str,
        *,
        lease_owner: str,
        status: str,
        result: dict[str, Any] | None,
        result_ref: dict[str, Any] | None,
        error_code: str | None,
        error: str | None,
        now: float | None,
    ) -> bool:
        active_now = float(now if now is not None else _now_ts())
        result_json = (
            json.dumps(result, ensure_ascii=False, default=str)
            if result is not None
            else None
        )
        result_ref_json = (
            json.dumps(result_ref, ensure_ascii=False, default=str)
            if result_ref is not None
            else None
        )
        with self._lock:
            terminal_guard = ""
            parameters: list[Any] = [
                status,
                result_json,
                result_ref_json,
                error_code,
                error,
                active_now,
                active_now,
                task_id,
                str(lease_owner or "").strip(),
            ]
            if status in {"succeeded", "partially_succeeded"}:
                terminal_guard = (
                    " AND cancel_requested=0"
                    " AND (deadline_at IS NULL OR deadline_at>?)"
                )
                parameters.append(active_now)
            cursor = self._conn.execute(
                f"""
                UPDATE tasks
                SET status=?, result_json=?, result_ref_json=?,
                    error_code=?, error=?, lease_owner=NULL,
                    lease_expires_at=NULL, heartbeat_at=NULL,
                    finished_at=?, updated_at=?
                WHERE task_id=? AND status='leased' AND lease_owner=?
                {terminal_guard}
                """,
                parameters,
            )
            self._conn.commit()
        return cursor.rowcount == 1

    @staticmethod
    def _row_to_durable(row: sqlite3.Row) -> DurableTask:
        return DurableTask(
            task_id=str(row["task_id"]),
            workflow_type=str(row["workflow_type"] or ""),
            handler_version=int(row["handler_version"] or 1),
            owner_user_id=str(row["owner_user_id"] or ""),
            course_id=str(row["course_id"] or "").strip() or None,
            scope_type=str(row["scope_type"] or "course"),
            scope_id=str(row["scope_id"] or "").strip() or None,
            command=_json_load(row["command_json"]),
            config_snapshot_id=(
                str(row["config_snapshot_id"] or "").strip() or None
            ),
            idempotency_key=(
                str(row["idempotency_key"] or "").strip() or None
            ),
            status=str(row["status"]),
            attempt_count=int(row["attempt_count"] or 0),
            max_attempts=int(row["max_attempts"] or 3),
            available_at=float(row["available_at"] or 0),
            lease_owner=str(row["lease_owner"] or "").strip() or None,
            lease_expires_at=(
                float(row["lease_expires_at"])
                if row["lease_expires_at"] is not None
                else None
            ),
            heartbeat_at=(
                float(row["heartbeat_at"])
                if row["heartbeat_at"] is not None
                else None
            ),
            deadline_at=(
                float(row["deadline_at"])
                if row["deadline_at"] is not None
                else None
            ),
            cancel_requested=bool(row["cancel_requested"]),
            progress=_json_load(row["progress_json"]),
            result=_json_load(row["result_json"]),
            result_ref=_json_load(row["result_ref_json"]),
            error_code=str(row["error_code"] or "").strip() or None,
            error=str(row["error"] or "").strip() or None,
            created_at=str(row["created_at"]),
            started_at=(
                float(row["started_at"])
                if row["started_at"] is not None
                else None
            ),
            finished_at=(
                float(row["finished_at"])
                if row["finished_at"] is not None
                else None
            ),
            updated_at=float(row["updated_at"]),
        )

    def _cleanup(self, *, now: float | None = None) -> None:
        cutoff = float(now if now is not None else _now_ts()) - self.TTL_SECONDS
        placeholders = ",".join("?" for _ in TERMINAL_TASK_STATUSES)
        with self._lock:
            expired = [
                row[0]
                for row in self._conn.execute(
                    f"""
                    SELECT task_id FROM tasks
                    WHERE status IN ({placeholders}) AND updated_at < ?
                    """,
                    (*TERMINAL_TASK_STATUSES, cutoff),
                ).fetchall()
            ]
            for task_id in expired:
                self._callbacks.pop(task_id, None)
            self._conn.execute(
                f"""
                DELETE FROM tasks
                WHERE status IN ({placeholders}) AND updated_at < ?
                """,
                (*TERMINAL_TASK_STATUSES, cutoff),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_store: Optional[Any] = None
_store_init_lock = threading.Lock()


def get_task_store() -> Any:
    global _store
    if _store is None:
        with _store_init_lock:
            if _store is None:
                if os.getenv("TASK_PERSISTENCE_MODE", "json").strip().lower() == "postgres":
                    from sqlalchemy import create_engine

                    from app.database import DatabaseNotConfigured
                    from app.chat.tasks.postgres_task_store import PostgresTaskStore

                    database_url = os.getenv("DATABASE_URL", "").strip()
                    if not database_url:
                        raise DatabaseNotConfigured("DATABASE_URL is not configured")
                    _store = PostgresTaskStore(
                        create_engine(database_url, pool_pre_ping=True)
                    )
                else:
                    _store = TaskStore()
    return _store
