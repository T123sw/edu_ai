import json
import sqlite3

import pytest

from app.chat.tasks.task_store import TaskStore


def command_payload(title: str = "Generate report") -> dict:
    return {
        "resource_type": "report",
        "course_id": "course-1",
        "title": title,
    }


def enqueue_task(
    store: TaskStore,
    task_id: str,
    *,
    owner: str = "teacher-a",
    workflow_type: str = "report_direct",
    idempotency_key: str | None = None,
    max_attempts: int = 3,
):
    return store.enqueue(
        task_id=task_id,
        workflow_type=workflow_type,
        handler_version=1,
        owner_user_id=owner,
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command=command_payload(task_id),
        config_snapshot_id="cfg-1",
        idempotency_key=idempotency_key,
        max_attempts=max_attempts,
        available_at=100.0,
    )


def test_schema_migration_is_idempotent_and_preserves_legacy_rows(tmp_path):
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
    connection.execute(
        """
        INSERT INTO tasks (
            task_id, workflow_type, owner_user_id, status, created_at, updated_at
        ) VALUES ('legacy-1', 'legacy', 'teacher-a', 'pending', '2026-01-01', 1)
        """
    )
    connection.commit()
    connection.close()

    first = TaskStore(str(db_path))
    first.close()
    second = TaskStore(str(db_path))

    assert second.get("legacy-1", owner_user_id="teacher-a")["status"] == "pending"
    columns = {
        row[1]
        for row in sqlite3.connect(db_path)
        .execute("PRAGMA table_info(tasks)")
        .fetchall()
    }
    assert {
        "command_json",
        "handler_version",
        "lease_owner",
        "lease_expires_at",
        "attempt_count",
        "cancel_requested",
        "result_ref_json",
    } <= columns
    second.close()


def test_two_store_instances_cannot_claim_the_same_task(tmp_path):
    db_path = tmp_path / "tasks.db"
    first = TaskStore(str(db_path))
    second = TaskStore(str(db_path))
    enqueue_task(first, "job-1")

    claimed = first.claim_next(
        lease_owner="worker-a",
        lease_seconds=45,
        now=100.0,
    )
    duplicate = second.claim_next(
        lease_owner="worker-b",
        lease_seconds=45,
        now=100.0,
    )

    assert claimed is not None
    assert claimed.task_id == "job-1"
    assert claimed.lease_owner == "worker-a"
    assert claimed.attempt_count == 1
    assert duplicate is None
    first.close()
    second.close()


def test_expired_lease_returns_to_pending_until_max_attempts(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    enqueue_task(store, "job-1", max_attempts=2)
    assert store.claim_next(
        lease_owner="worker-a",
        lease_seconds=10,
        now=100.0,
    )

    summary = store.recover_expired_leases(now=111.0)
    recovered = store.get_durable("job-1")

    assert summary.requeued == 1
    assert summary.failed == 0
    assert summary.requeued_task_ids == ("job-1",)
    assert recovered is not None
    assert recovered.status == "pending"
    assert recovered.lease_owner is None
    assert recovered.error_code == "LEASE_EXPIRED"
    store.close()


def test_expired_lease_fails_after_max_attempts(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    enqueue_task(store, "job-1", max_attempts=1)
    assert store.claim_next(
        lease_owner="worker-a",
        lease_seconds=10,
        now=100.0,
    )

    summary = store.recover_expired_leases(now=111.0)
    recovered = store.get_durable("job-1")

    assert summary.requeued == 0
    assert summary.failed == 1
    assert summary.failed_task_ids == ("job-1",)
    assert recovered is not None
    assert recovered.status == "failed"
    assert recovered.error_code == "WORKER_LOST"
    store.close()


def test_durable_enqueue_assigns_a_default_deadline(tmp_path, monkeypatch):
    store = TaskStore(str(tmp_path / "tasks.db"))
    monkeypatch.setattr(
        "app.chat.tasks.task_store._now_ts",
        lambda: 100.0,
    )

    task = enqueue_task(store, "job-default-deadline")

    assert task.deadline_at == 400.0
    store.close()


def test_recovery_fails_legacy_pending_task_after_bounded_deadline(tmp_path):
    db_path = tmp_path / "tasks.db"
    store = TaskStore(str(db_path))
    enqueue_task(store, "job-legacy")
    connection = sqlite3.connect(db_path)
    connection.execute(
        "UPDATE tasks SET deadline_at=NULL, updated_at=100 WHERE task_id=?",
        ("job-legacy",),
    )
    connection.commit()
    connection.close()

    summary = store.recover_expired_leases(now=401.0)
    recovered = store.get_durable("job-legacy")

    assert summary.failed == 1
    assert summary.failed_task_ids == ("job-legacy",)
    assert recovered is not None
    assert recovered.status == "failed"
    assert recovered.error_code == "GENERATION_DEADLINE_EXCEEDED"
    store.close()


def test_mark_failed_without_a_lease_persists_user_visible_failure(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    enqueue_task(store, "job-failed")

    store.mark_failed(
        "job-failed",
        "provider unavailable",
        error_code="TASK_EXECUTION_FAILED",
        now=123.0,
    )

    failed = store.get_durable("job-failed")
    assert failed is not None
    assert failed.status == "failed"
    assert failed.error_code == "TASK_EXECUTION_FAILED"
    assert failed.error == "provider unavailable"
    assert failed.finished_at == 123.0
    store.close()


def test_heartbeat_only_extends_the_current_lease_owner(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    enqueue_task(store, "job-1")
    assert store.claim_next(
        lease_owner="worker-a",
        lease_seconds=10,
        now=100.0,
    )

    assert (
        store.heartbeat(
            "job-1",
            lease_owner="worker-b",
            lease_seconds=10,
            now=105.0,
        )
        is False
    )
    assert (
        store.heartbeat(
            "job-1",
            lease_owner="worker-a",
            lease_seconds=10,
            now=105.0,
        )
        is True
    )
    task = store.get_durable("job-1")
    assert task is not None
    assert task.heartbeat_at == 105.0
    assert task.lease_expires_at == 115.0
    store.close()


def test_terminal_cleanup_never_deletes_pending_or_leased_tasks(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    store.TTL_SECONDS = 1
    enqueue_task(store, "leased")
    enqueue_task(store, "pending")
    assert store.claim_next(
        lease_owner="worker-a",
        lease_seconds=100,
        now=100.0,
    )
    completed = store.create(
        task_id="completed",
        workflow_type="legacy",
        owner_user_id="teacher-a",
    )
    store.mark_complete(completed, {"ok": True})

    connection = sqlite3.connect(tmp_path / "tasks.db")
    connection.execute("UPDATE tasks SET updated_at=0")
    connection.commit()
    connection.close()
    store._cleanup(now=10.0)

    assert store.get_durable("pending") is not None
    assert store.get_durable("leased") is not None
    assert store.get("completed", owner_user_id="teacher-a") is None
    store.close()


def test_idempotency_key_is_scoped_by_owner_and_workflow(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    original = enqueue_task(
        store,
        "job-1",
        idempotency_key="same-request",
    )
    duplicate = enqueue_task(
        store,
        "job-2",
        idempotency_key="same-request",
    )
    another_owner = enqueue_task(
        store,
        "job-3",
        owner="teacher-b",
        idempotency_key="same-request",
    )
    another_workflow = enqueue_task(
        store,
        "job-4",
        workflow_type="quiz_direct",
        idempotency_key="same-request",
    )

    assert duplicate.task_id == original.task_id
    assert another_owner.task_id == "job-3"
    assert another_workflow.task_id == "job-4"
    store.close()


@pytest.mark.parametrize(
    "payload",
    [
        {"api_key": "sk-secret"},
        {"nested": {"authorization": "Bearer secret"}},
        {"source_path": "C:\\private\\upload.pdf"},
        {"source_path": "/srv/private/upload.pdf"},
    ],
)
def test_command_payload_rejects_secrets_and_absolute_paths(tmp_path, payload):
    store = TaskStore(str(tmp_path / "tasks.db"))

    with pytest.raises(ValueError, match="command payload"):
        store.enqueue(
            task_id="job-1",
            workflow_type="report_direct",
            handler_version=1,
            owner_user_id="teacher-a",
            course_id="course-1",
            scope_type="course",
            scope_id=None,
            command=payload,
            config_snapshot_id="cfg-1",
            idempotency_key=None,
            max_attempts=3,
        )

    count = sqlite3.connect(tmp_path / "tasks.db").execute(
        "SELECT COUNT(*) FROM tasks"
    ).fetchone()[0]
    assert count == 0
    store.close()


def test_command_payload_allows_nonsecret_model_token_limits(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))

    task = store.enqueue(
        task_id="job-1",
        workflow_type="report_direct",
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command={"config": {"max_tokens": 4096}},
        config_snapshot_id="cfg-1",
        idempotency_key=None,
        max_attempts=3,
    )

    assert task.command == {"config": {"max_tokens": 4096}}
    store.close()


def test_command_payload_allows_text_and_internal_urls_that_start_with_slash(
    tmp_path,
):
    store = TaskStore(str(tmp_path / "tasks.db"))

    task = store.enqueue(
        task_id="job-1",
        workflow_type="classroom_generate",
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command={
            "requirement": "/ 用图示解释除法",
            "media_url": "/api/courses/course-1/audio/clip.mp3",
        },
        config_snapshot_id="cfg-1",
        idempotency_key=None,
        max_attempts=3,
    )

    assert task.command["media_url"].startswith("/api/")
    store.close()


def test_durable_result_fields_round_trip_as_json(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    enqueue_task(store, "job-1")
    assert store.claim_next(
        lease_owner="worker-a",
        lease_seconds=45,
        now=100.0,
    )
    assert store.mark_succeeded(
        "job-1",
        lease_owner="worker-a",
        result={"saved": True},
        result_ref={
            "course_id": "course-1",
            "material_type": "report",
            "material_id": "report-1",
        },
        now=120.0,
    )

    task = store.get_durable("job-1")
    assert task is not None
    assert task.status == "succeeded"
    assert task.result == {"saved": True}
    assert task.result_ref["material_id"] == "report-1"
    assert task.finished_at == 120.0
    assert json.loads(
        sqlite3.connect(tmp_path / "tasks.db")
        .execute(
            "SELECT result_ref_json FROM tasks WHERE task_id='job-1'"
        )
        .fetchone()[0]
    )["material_type"] == "report"
    store.close()
