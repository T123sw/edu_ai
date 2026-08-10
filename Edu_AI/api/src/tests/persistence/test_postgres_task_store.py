from sqlalchemy import create_engine

from app.chat.tasks.postgres_task_store import PostgresTaskStore
from app.chat.tasks import task_store as task_store_module
from app.database.models import Base


def test_postgres_task_store_runs_durable_task_lifecycle_without_sqlite_file(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    store = PostgresTaskStore(engine)

    queued = store.enqueue(
        task_id="task-1",
        workflow_type="report_direct",
        handler_version=1,
        owner_user_id="teacher-1",
        course_id="course-1",
        scope_type="course",
        scope_id="course-1",
        command={"resource_type": "report"},
        config_snapshot_id="cfg-1",
        idempotency_key="request-1",
        available_at=100.0,
        deadline_at=500.0,
    )
    duplicate = store.enqueue(
        task_id="task-duplicate",
        workflow_type="report_direct",
        handler_version=1,
        owner_user_id="teacher-1",
        course_id="course-1",
        scope_type="course",
        scope_id="course-1",
        command={"resource_type": "report"},
        config_snapshot_id="cfg-1",
        idempotency_key="request-1",
        available_at=100.0,
        deadline_at=500.0,
    )

    claimed = store.claim_next(
        lease_owner="worker-1",
        lease_seconds=30,
        now=100.0,
    )
    assert queued.task_id == "task-1"
    assert duplicate.task_id == "task-1"
    assert claimed is not None
    assert claimed.attempt_count == 1
    assert store.mark_succeeded(
        "task-1",
        lease_owner="worker-1",
        result={"saved": True},
        result_ref={"material_id": "report-1"},
        now=120.0,
    )
    assert store.get_durable("task-1").status == "succeeded"
    assert not (tmp_path / "tasks.db").exists()


def test_legacy_compatibility_interface_is_preserved():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    store = PostgresTaskStore(engine)

    task_id = store.create(
        workflow_type="legacy",
        owner_user_id="teacher-1",
        task_id="legacy-1",
    )
    store.mark_running(task_id)
    store.update_progress(task_id, {"percent": 50})
    store.mark_complete(task_id, {"ok": True})

    task = store.get(task_id, owner_user_id="teacher-1")
    assert task["status"] == "completed"
    assert task["result"] == {"ok": True}


def test_factory_uses_postgres_mode_without_opening_legacy_sqlite(monkeypatch, tmp_path):
    target = tmp_path / "target.db"
    engine = create_engine(f"sqlite+pysqlite:///{target.as_posix()}")
    Base.metadata.create_all(engine)
    legacy_path = tmp_path / "legacy-tasks.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{target.as_posix()}")
    monkeypatch.setenv("TASK_PERSISTENCE_MODE", "postgres")
    monkeypatch.setenv("TASKS_DB_PATH", str(legacy_path))
    monkeypatch.setattr(task_store_module, "_store", None)

    store = task_store_module.get_task_store()

    assert isinstance(store, PostgresTaskStore)
    assert not legacy_path.exists()
    monkeypatch.setattr(task_store_module, "_store", None)
