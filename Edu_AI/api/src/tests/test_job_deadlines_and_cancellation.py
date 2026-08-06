from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.chat.tasks import task_store as task_store_module
from app.chat.tasks.task_store import TaskStore
from app.services.durable_task_executor import DurableTaskExecutor
from app.services.durable_task_handlers import DurableTaskHandlerRegistry
from app.services.job_completion_service import JobCompletionService
from app.services.job_reconciliation_service import JobReconciliationService
from app.services.job_store import JobKind, JobStatus, create_job, get_job
from core import Config
from core.course_storage import CourseStorageManager


DEADLINE = datetime(2026, 8, 6, 0, 0, tzinfo=timezone.utc)


class RecordingHandler:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, command, context):
        self.calls.append(dict(command))
        return {"saved": True, "result_ref": {"resource_type": "inline"}}


@pytest.fixture()
def deadline_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "app-storage")
    store = TaskStore(str(tmp_path / "tasks.db"))
    manager = CourseStorageManager(root_path=str(tmp_path / "course-storage"))
    manager.create_course_structure("course-1")
    handler = RecordingHandler()
    registry = DurableTaskHandlerRegistry()
    registry.register("report_direct", 1, handler)
    executor = DurableTaskExecutor(
        task_store=store,
        handler_registry=registry,
        completion_service=JobCompletionService(
            task_store=store,
            course_storage_manager=manager,
        ),
        worker_id="worker-deadline",
        lease_seconds=30,
        heartbeat_interval=1,
    )
    reconciliation = JobReconciliationService(
        task_store=store,
        course_storage_manager=manager,
    )
    yield executor, store, handler, reconciliation, tmp_path / "tasks.db"
    store.close()


def enqueue_deadlined_task(
    store: TaskStore,
    *,
    task_id: str,
    deadline_at: datetime,
    workflow_type: str = "report_direct",
):
    task = store.enqueue(
        task_id=task_id,
        workflow_type=workflow_type,
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command={"resource_type": "report", "deadline_seconds": 300},
        config_snapshot_id="cfg-1",
        idempotency_key=task_id,
        deadline_at=deadline_at,
        available_at=DEADLINE.timestamp() - 3600,
    )
    create_job(
        kind=JobKind.GENERATE_REPORT,
        edu_job_id=task_id,
        owner_user_id="teacher-a",
        course_id="course-1",
    )
    return task


def seed_cancel_requested_task(
    store: TaskStore,
    *,
    task_id: str,
    db_path,
    lease_expires_at: datetime,
):
    task = store.enqueue(
        task_id=task_id,
        workflow_type="report_direct",
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command={"resource_type": "report"},
        config_snapshot_id="cfg-1",
        idempotency_key=task_id,
        available_at=100,
    )
    create_job(
        kind=JobKind.GENERATE_REPORT,
        edu_job_id=task_id,
        owner_user_id="teacher-a",
        course_id="course-1",
    )
    claimed = store.claim_next(
        lease_owner="worker-that-stopped",
        lease_seconds=30,
        now=100,
    )
    assert claimed is not None
    assert store.request_cancel(task_id, owner_user_id="teacher-a")
    connection = sqlite3.connect(db_path)
    connection.execute(
        "UPDATE tasks SET lease_expires_at=? WHERE task_id=?",
        (lease_expires_at.timestamp(), task_id),
    )
    connection.commit()
    connection.close()
    return task


def test_deadline_column_is_migrated_and_round_trips(tmp_path):
    db_path = tmp_path / "tasks.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE tasks (
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
    connection.commit()
    connection.close()

    store = TaskStore(str(db_path))
    task = enqueue_deadlined_task(
        store,
        task_id="job-migrated",
        deadline_at=DEADLINE,
    )

    columns = {
        row[1]
        for row in sqlite3.connect(db_path)
        .execute("PRAGMA table_info(tasks)")
        .fetchall()
    }
    assert "deadline_at" in columns
    assert task.deadline_at == DEADLINE.timestamp()
    store.close()


def test_deadline_seconds_is_converted_to_an_absolute_deadline(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(task_store_module, "_now_ts", lambda: 100.0)
    store = TaskStore(str(tmp_path / "tasks.db"))

    task = store.enqueue(
        task_id="job-derived-deadline",
        workflow_type="report_direct",
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command={"resource_type": "report", "deadline_seconds": 45},
        config_snapshot_id="cfg-1",
        idempotency_key="job-derived-deadline",
    )

    assert task.deadline_at == 145.0
    store.close()


def test_expired_queued_job_fails_without_handler_call(deadline_runtime):
    executor, store, handler, _, _ = deadline_runtime
    enqueue_deadlined_task(
        store,
        task_id="job-expired",
        deadline_at=DEADLINE,
    )

    executor.run_once(
        now=datetime(2026, 8, 6, 0, 0, 1, tzinfo=timezone.utc)
    )

    task = store.get_durable("job-expired")
    job = get_job("job-expired")
    assert task is not None
    assert task.status == "failed"
    assert task.error_code == "GENERATION_DEADLINE_EXCEEDED"
    assert handler.calls == []
    assert job is not None
    assert job.status == JobStatus.FAILED
    assert job.error_code == "GENERATION_DEADLINE_EXCEEDED"


def test_unexpired_job_still_invokes_handler(deadline_runtime):
    executor, store, handler, _, _ = deadline_runtime
    enqueue_deadlined_task(
        store,
        task_id="job-active",
        deadline_at=DEADLINE,
    )

    executor.run_once(
        now=datetime(2026, 8, 5, 23, 59, 59, tzinfo=timezone.utc)
    )

    assert store.get_durable("job-active").status == "succeeded"
    assert len(handler.calls) == 1


def test_cancel_requested_inside_handler_cannot_finish_as_succeeded(
    deadline_runtime,
):
    executor, store, _, _, _ = deadline_runtime
    task = enqueue_deadlined_task(
        store,
        task_id="job-cancel-race",
        deadline_at=DEADLINE,
        workflow_type="report_cancel_race",
    )
    handler = RecordingHandler()

    def cancel_then_return(command, context):
        assert store.request_cancel(
            task.task_id,
            owner_user_id=task.owner_user_id,
        )
        return handler(command, context)

    executor.handler_registry.register(
        "report_cancel_race",
        1,
        cancel_then_return,
    )

    executor.run_once(
        now=datetime(2026, 8, 5, 23, 59, 59, tzinfo=timezone.utc)
    )

    durable = store.get_durable(task.task_id)
    assert durable is not None
    assert durable.status == "canceled"
    assert durable.result_ref is None
    assert durable.error_code == "GENERATION_CANCELLED"


def test_reconciliation_finishes_cancel_requested_job(deadline_runtime):
    _, store, handler, reconciliation, db_path = deadline_runtime
    seed_cancel_requested_task(
        store,
        task_id="job-cancel",
        db_path=db_path,
        lease_expires_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )

    reconciliation.run(
        now=datetime(2026, 8, 6, tzinfo=timezone.utc)
    )

    task = store.get_durable("job-cancel")
    job = get_job("job-cancel")
    assert task is not None
    assert task.status == "canceled"
    assert task.error_code == "GENERATION_CANCELLED"
    assert handler.calls == []
    assert job is not None
    assert job.status == JobStatus.CANCELED
    assert job.error_code == "GENERATION_CANCELLED"


def test_reconciliation_fails_expired_leased_job_instead_of_retrying(
    deadline_runtime,
):
    _, store, _, reconciliation, db_path = deadline_runtime
    enqueue_deadlined_task(
        store,
        task_id="job-lease-expired",
        deadline_at=DEADLINE,
    )
    assert store.claim_next(
        lease_owner="worker-that-stopped",
        lease_seconds=30,
        now=DEADLINE.timestamp() - 1800,
    )
    connection = sqlite3.connect(db_path)
    connection.execute(
        "UPDATE tasks SET lease_expires_at=? WHERE task_id=?",
        (datetime(2026, 8, 5, tzinfo=timezone.utc).timestamp(), "job-lease-expired"),
    )
    connection.commit()
    connection.close()

    reconciliation.run(
        now=datetime(2026, 8, 6, 0, 0, 1, tzinfo=timezone.utc)
    )

    task = store.get_durable("job-lease-expired")
    assert task is not None
    assert task.status == "failed"
    assert task.error_code == "GENERATION_DEADLINE_EXCEEDED"
