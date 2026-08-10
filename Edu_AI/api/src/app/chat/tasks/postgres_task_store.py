from __future__ import annotations

import threading
import uuid
from typing import Any, Callable, Mapping

from sqlalchemy import delete, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import DurableTaskModel

from .task_store import (
    DEFAULT_TASK_DEADLINE_SECONDS,
    TERMINAL_TASK_STATUSES,
    TTL_SECONDS,
    DurableTask,
    LeaseRecoverySummary,
    _coerce_timestamp,
    _now_iso,
    _now_ts,
    _validate_command_payload,
)


class PostgresTaskStore:
    """Durable task queue backed by the configured SQLAlchemy database."""

    TTL_SECONDS = TTL_SECONDS

    def __init__(self, engine: Engine):
        self._sessions = sessionmaker(engine, expire_on_commit=False)
        self._callbacks: dict[str, Callable] = {}
        self._callback_lock = threading.RLock()

    @staticmethod
    def _to_durable(row: DurableTaskModel) -> DurableTask:
        return DurableTask(
            task_id=row.task_id,
            workflow_type=row.workflow_type or "",
            handler_version=row.handler_version or 1,
            owner_user_id=row.owner_user_id or "",
            course_id=row.course_id,
            scope_type=row.scope_type or "course",
            scope_id=row.scope_id,
            command=dict(row.command) if row.command is not None else None,
            config_snapshot_id=row.config_snapshot_id,
            idempotency_key=row.idempotency_key,
            status=row.status,
            attempt_count=row.attempt_count or 0,
            max_attempts=row.max_attempts or 3,
            available_at=float(row.available_at or 0),
            lease_owner=row.lease_owner,
            lease_expires_at=row.lease_expires_at,
            heartbeat_at=row.heartbeat_at,
            deadline_at=row.deadline_at,
            cancel_requested=bool(row.cancel_requested),
            progress=dict(row.progress) if row.progress is not None else None,
            result=dict(row.result) if row.result is not None else None,
            result_ref=dict(row.result_ref) if row.result_ref is not None else None,
            error_code=row.error_code,
            error=row.error,
            created_at=row.created_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
            updated_at=float(row.updated_at),
        )

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
        deadline_at: float | object | str | None = None,
    ) -> DurableTask:
        task_id = str(task_id or "").strip()
        workflow_type = str(workflow_type or "").strip()
        owner_user_id = str(owner_user_id or "").strip()
        if not task_id:
            raise ValueError("task_id is required")
        if not workflow_type:
            raise ValueError("workflow_type is required")
        if not owner_user_id:
            raise ValueError("owner_user_id is required")
        if int(handler_version) < 1:
            raise ValueError("handler_version must be positive")
        if int(max_attempts) < 1:
            raise ValueError("max_attempts must be positive")
        _validate_command_payload(command)
        now = _now_ts()
        deadline = _coerce_timestamp(deadline_at)  # type: ignore[arg-type]
        if deadline is None and command.get("deadline_seconds") is not None:
            seconds = float(command["deadline_seconds"])
            if seconds <= 0:
                raise ValueError("deadline_seconds must be positive")
            deadline = now + seconds
        if deadline is None:
            deadline = now + DEFAULT_TASK_DEADLINE_SECONDS
        idempotency_key = str(idempotency_key or "").strip() or None
        if idempotency_key:
            with self._sessions() as session:
                existing = session.scalar(
                    select(DurableTaskModel).where(
                        DurableTaskModel.owner_user_id == owner_user_id,
                        DurableTaskModel.workflow_type == workflow_type,
                        DurableTaskModel.idempotency_key == idempotency_key,
                    )
                )
                if existing is not None:
                    return self._to_durable(existing)
        row = DurableTaskModel(
            task_id=task_id,
            workflow_type=workflow_type,
            handler_version=int(handler_version),
            owner_user_id=owner_user_id,
            course_id=str(course_id or "").strip() or None,
            scope_type=str(scope_type or "course").strip() or "course",
            scope_id=str(scope_id or "").strip() or None,
            command=dict(command),
            config_snapshot_id=str(config_snapshot_id or "").strip() or None,
            idempotency_key=idempotency_key,
            status="pending",
            attempt_count=0,
            max_attempts=int(max_attempts),
            available_at=float(available_at if available_at is not None else now),
            deadline_at=deadline,
            cancel_requested=False,
            created_at=_now_iso(),
            updated_at=now,
        )
        try:
            with self._sessions.begin() as session:
                session.add(row)
        except IntegrityError:
            if not idempotency_key:
                raise
            with self._sessions() as session:
                existing = session.scalar(
                    select(DurableTaskModel).where(
                        DurableTaskModel.owner_user_id == owner_user_id,
                        DurableTaskModel.workflow_type == workflow_type,
                        DurableTaskModel.idempotency_key == idempotency_key,
                    )
                )
                if existing is None:
                    raise
                return self._to_durable(existing)
        return self._to_durable(row)

    def claim_next(
        self, *, lease_owner: str, lease_seconds: float, now: float | None = None
    ) -> DurableTask | None:
        lease_owner = str(lease_owner or "").strip()
        if not lease_owner:
            raise ValueError("lease_owner is required")
        if float(lease_seconds) <= 0:
            raise ValueError("lease_seconds must be positive")
        active_now = float(now if now is not None else _now_ts())
        with self._sessions.begin() as session:
            row = session.scalar(
                select(DurableTaskModel)
                .where(
                    DurableTaskModel.status == "pending",
                    DurableTaskModel.command.is_not(None),
                    DurableTaskModel.cancel_requested.is_(False),
                    DurableTaskModel.available_at <= active_now,
                    DurableTaskModel.attempt_count < DurableTaskModel.max_attempts,
                )
                .order_by(
                    DurableTaskModel.available_at,
                    DurableTaskModel.created_at,
                    DurableTaskModel.task_id,
                )
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if row is None:
                return None
            row.status = "leased"
            row.lease_owner = lease_owner
            row.lease_expires_at = active_now + float(lease_seconds)
            row.heartbeat_at = active_now
            row.attempt_count += 1
            row.started_at = row.started_at if row.started_at is not None else active_now
            row.updated_at = active_now
        return self._to_durable(row)

    def heartbeat(
        self,
        task_id: str,
        *,
        lease_owner: str,
        lease_seconds: float,
        now: float | None = None,
    ) -> bool:
        active_now = float(now if now is not None else _now_ts())
        with self._sessions.begin() as session:
            row = session.get(DurableTaskModel, task_id, with_for_update=True)
            if row is None or row.status != "leased" or row.lease_owner != lease_owner:
                return False
            row.heartbeat_at = active_now
            row.lease_expires_at = active_now + float(lease_seconds)
            row.updated_at = active_now
            return True

    def request_cancel(self, task_id: str, *, owner_user_id: str) -> bool:
        active_now = _now_ts()
        with self._sessions.begin() as session:
            row = session.get(DurableTaskModel, task_id, with_for_update=True)
            if row is None or row.owner_user_id != str(owner_user_id or "").strip():
                return False
            if row.status == "pending":
                row.status = "canceled"
                row.cancel_requested = True
                row.error_code = "GENERATION_CANCELLED"
                row.error = "Generation was canceled"
                row.finished_at = active_now
            elif row.status == "leased":
                row.cancel_requested = True
                row.error_code = "GENERATION_CANCELLED"
                row.error = "Generation cancellation requested"
            else:
                return False
            row.updated_at = active_now
            return True

    def is_cancel_requested(self, task_id: str) -> bool:
        with self._sessions() as session:
            row = session.get(DurableTaskModel, task_id)
            return bool(row and row.cancel_requested)

    def mark_succeeded(self, task_id: str, *, lease_owner: str, result: dict[str, Any], result_ref: dict[str, Any], now: float | None = None) -> bool:
        return self._finish_leased(task_id, lease_owner=lease_owner, status="succeeded", result=result, result_ref=result_ref, error_code=None, error=None, now=now)

    def mark_partially_succeeded(self, task_id: str, *, lease_owner: str, result: dict[str, Any], result_ref: dict[str, Any], error_code: str, error: str, now: float | None = None) -> bool:
        return self._finish_leased(task_id, lease_owner=lease_owner, status="partially_succeeded", result=result, result_ref=result_ref, error_code=error_code, error=error, now=now)

    def mark_canceled(self, task_id: str, *, lease_owner: str, now: float | None = None) -> bool:
        return self._finish_leased(task_id, lease_owner=lease_owner, status="canceled", result=None, result_ref=None, error_code="GENERATION_CANCELLED", error="Generation was canceled", now=now)

    def release_for_retry(self, task_id: str, *, lease_owner: str, available_at: float, error_code: str, error: str, now: float | None = None) -> bool:
        active_now = float(now if now is not None else _now_ts())
        with self._sessions.begin() as session:
            row = session.get(DurableTaskModel, task_id, with_for_update=True)
            if row is None or row.status != "leased" or row.lease_owner != lease_owner:
                return False
            if row.attempt_count >= row.max_attempts:
                row.status = "failed"
                row.error_code = "MAX_ATTEMPTS_EXCEEDED"
                row.finished_at = active_now
            else:
                row.status = "pending"
                row.available_at = float(available_at)
                row.error_code = str(error_code or "")
            row.error = str(error or "")
            row.lease_owner = row.lease_expires_at = row.heartbeat_at = None
            row.updated_at = active_now
            return True

    def recover_expired_leases(self, *, now: float | None = None) -> LeaseRecoverySummary:
        active_now = float(now if now is not None else _now_ts())
        requeued: list[str] = []
        failed: list[str] = []
        canceled: list[str] = []
        with self._sessions.begin() as session:
            live_rows = list(session.scalars(
                select(DurableTaskModel)
                .where(DurableTaskModel.status.in_(("pending", "leased")))
                .with_for_update(skip_locked=True)
            ))
            for row in live_rows:
                if row.command is not None and row.deadline_at is None:
                    row.deadline_at = row.updated_at + DEFAULT_TASK_DEADLINE_SECONDS
                if row.status == "pending" and row.deadline_at is not None and row.deadline_at <= active_now:
                    row.status = "failed"
                    row.error_code = "GENERATION_DEADLINE_EXCEEDED"
                    row.error = "Generation deadline exceeded before execution"
                    row.finished_at = row.updated_at = active_now
                    failed.append(row.task_id)
                    continue
                if row.status != "leased" or row.lease_expires_at is None or row.lease_expires_at > active_now:
                    continue
                if row.cancel_requested:
                    row.status = "canceled"
                    row.error_code = "GENERATION_CANCELLED"
                    row.error = "Generation was canceled after worker restart"
                    canceled.append(row.task_id)
                elif row.deadline_at is not None and row.deadline_at <= active_now:
                    row.status = "failed"
                    row.error_code = "GENERATION_DEADLINE_EXCEEDED"
                    row.error = "Generation deadline exceeded while worker was unavailable"
                    failed.append(row.task_id)
                elif row.attempt_count >= row.max_attempts:
                    row.status = "failed"
                    row.error_code = "WORKER_LOST"
                    row.error = "Worker lease expired after maximum attempts"
                    failed.append(row.task_id)
                else:
                    row.status = "pending"
                    row.available_at = active_now
                    row.error_code = "LEASE_EXPIRED"
                    row.error = "Worker lease expired; task requeued"
                    requeued.append(row.task_id)
                row.lease_owner = row.lease_expires_at = row.heartbeat_at = None
                row.updated_at = active_now
                if row.status in {"failed", "canceled"}:
                    row.finished_at = active_now
        return LeaseRecoverySummary(
            requeued=len(requeued), failed=len(failed), canceled=len(canceled),
            requeued_task_ids=tuple(requeued), failed_task_ids=tuple(failed),
            canceled_task_ids=tuple(canceled),
        )

    def mark_reconciled_succeeded(self, task_id: str, *, result: Mapping[str, Any], result_ref: Mapping[str, Any], now: float | None = None) -> bool:
        active_now = float(now if now is not None else _now_ts())
        with self._sessions.begin() as session:
            row = session.get(DurableTaskModel, str(task_id or "").strip(), with_for_update=True)
            if row is None or row.status not in {"pending", "leased"} or row.cancel_requested or (row.deadline_at is not None and row.deadline_at <= active_now):
                return False
            row.status = "succeeded"
            row.result = dict(result)
            row.result_ref = dict(result_ref)
            row.error_code = row.error = None
            row.lease_owner = row.lease_expires_at = row.heartbeat_at = None
            row.finished_at = row.updated_at = active_now
            return True

    def get_durable(self, task_id: str) -> DurableTask | None:
        with self._sessions() as session:
            row = session.get(DurableTaskModel, task_id)
            return self._to_durable(row) if row is not None else None

    def create(self, *, workflow_type: str = "", owner_user_id: str = "", task_id: str | None = None, on_complete: Callable | None = None) -> str:
        task_id = str(task_id or uuid.uuid4())
        now = _now_ts()
        with self._sessions.begin() as session:
            session.add(DurableTaskModel(
                task_id=task_id, workflow_type=workflow_type,
                handler_version=1, owner_user_id=str(owner_user_id or "").strip(),
                scope_type="course", status="pending", attempt_count=0,
                max_attempts=3, available_at=now, cancel_requested=False,
                created_at=_now_iso(), updated_at=now,
            ))
        if on_complete:
            with self._callback_lock:
                self._callbacks[task_id] = on_complete
        self._cleanup()
        return task_id

    def mark_running(self, task_id: str) -> None:
        self._simple_update(task_id, status="running", updated_at=_now_ts())

    def mark_complete(self, task_id: str, result: dict) -> None:
        now = _now_ts()
        self._simple_update(task_id, status="completed", result=dict(result), progress=None, finished_at=now, updated_at=now)
        with self._callback_lock:
            callback = self._callbacks.pop(task_id, None)
        if callback:
            try:
                callback(result)
            except Exception:
                pass

    def mark_failed(self, task_id: str, error: str | None = None, *, lease_owner: str | None = None, error_code: str | None = None, now: float | None = None) -> bool | None:
        if lease_owner is not None:
            return self._finish_leased(task_id, lease_owner=lease_owner, status="failed", result=None, result_ref=None, error_code=error_code or "TASK_FAILED", error=error or "Task failed", now=now)
        active_now = float(now if now is not None else _now_ts())
        self._simple_update(task_id, status="failed", error_code=str(error_code or "") or None, error=str(error or ""), finished_at=active_now, updated_at=active_now)
        return None

    def update_progress(self, task_id: str, progress: dict) -> None:
        with self._sessions.begin() as session:
            row = session.get(DurableTaskModel, task_id, with_for_update=True)
            if row is not None and row.status in {"running", "leased"}:
                row.progress = dict(progress)
                row.updated_at = _now_ts()

    def get(self, task_id: str, *, owner_user_id: str | None = None) -> dict | None:
        with self._sessions() as session:
            row = session.get(DurableTaskModel, task_id)
            if row is None or (owner_user_id is not None and row.owner_user_id != str(owner_user_id or "").strip()):
                return None
            value: dict[str, Any] = {
                "task_id": row.task_id, "workflow_type": row.workflow_type,
                "owner_user_id": row.owner_user_id, "status": row.status,
                "result": dict(row.result) if row.result is not None else None,
                "error": row.error, "created_at": row.created_at,
            }
            if row.progress is not None:
                value["progress"] = dict(row.progress)
            return value

    def _finish_leased(self, task_id: str, *, lease_owner: str, status: str, result: dict[str, Any] | None, result_ref: dict[str, Any] | None, error_code: str | None, error: str | None, now: float | None) -> bool:
        active_now = float(now if now is not None else _now_ts())
        with self._sessions.begin() as session:
            row = session.get(DurableTaskModel, task_id, with_for_update=True)
            if row is None or row.status != "leased" or row.lease_owner != str(lease_owner or "").strip():
                return False
            if status in {"succeeded", "partially_succeeded"} and (row.cancel_requested or (row.deadline_at is not None and row.deadline_at <= active_now)):
                return False
            row.status = status
            row.result = dict(result) if result is not None else None
            row.result_ref = dict(result_ref) if result_ref is not None else None
            row.error_code = error_code
            row.error = error
            row.lease_owner = row.lease_expires_at = row.heartbeat_at = None
            row.finished_at = row.updated_at = active_now
            return True

    def _simple_update(self, task_id: str, **values: Any) -> None:
        with self._sessions.begin() as session:
            row = session.get(DurableTaskModel, task_id, with_for_update=True)
            if row is not None:
                for key, value in values.items():
                    setattr(row, key, value)

    def _cleanup(self, *, now: float | None = None) -> None:
        cutoff = float(now if now is not None else _now_ts()) - self.TTL_SECONDS
        with self._sessions.begin() as session:
            expired = list(session.scalars(select(DurableTaskModel.task_id).where(
                DurableTaskModel.status.in_(TERMINAL_TASK_STATUSES),
                DurableTaskModel.updated_at < cutoff,
            )))
            session.execute(delete(DurableTaskModel).where(
                DurableTaskModel.status.in_(TERMINAL_TASK_STATUSES),
                DurableTaskModel.updated_at < cutoff,
            ))
        with self._callback_lock:
            for task_id in expired:
                self._callbacks.pop(task_id, None)

    def close(self) -> None:
        return None
