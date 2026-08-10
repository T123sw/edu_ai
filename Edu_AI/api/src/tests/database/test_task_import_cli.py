import json
import sqlite3

from sqlalchemy import create_engine, select

from app.database.migrate_task_cli import main
from app.database.models import Base, DurableTaskModel


def test_task_import_is_idempotent(tmp_path):
    source = tmp_path / "tasks.db"
    connection = sqlite3.connect(source)
    connection.execute(
        """
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY, workflow_type TEXT, status TEXT,
            result_json TEXT, error TEXT, progress_json TEXT,
            created_at TEXT, updated_at REAL, owner_user_id TEXT,
            handler_version INTEGER, course_id TEXT, scope_type TEXT,
            scope_id TEXT, command_json TEXT, config_snapshot_id TEXT,
            idempotency_key TEXT, attempt_count INTEGER, max_attempts INTEGER,
            available_at REAL, lease_owner TEXT, lease_expires_at REAL,
            heartbeat_at REAL, cancel_requested INTEGER, result_ref_json TEXT,
            error_code TEXT, started_at REAL, finished_at REAL, deadline_at REAL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO tasks VALUES (
            'task-1', 'report_direct', 'completed', ?, NULL, NULL,
            '2026-08-10T00:00:00', 100, 'teacher-1', 1, 'course-1',
            'course', 'course-1', NULL, NULL, NULL, 0, 3, 0,
            NULL, NULL, NULL, 0, NULL, NULL, NULL, 120, NULL
        )
        """,
        (json.dumps({"ok": True}),),
    )
    connection.commit()
    connection.close()

    target = tmp_path / "target.db"
    database_url = f"sqlite+pysqlite:///{target.as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    assert main(["--source", str(source), "--database-url", database_url, "--apply"]) == 0
    assert main(["--source", str(source), "--database-url", database_url, "--apply"]) == 0

    with engine.connect() as target_connection:
        rows = target_connection.execute(select(DurableTaskModel)).all()
    assert len(rows) == 1
    assert rows[0].result == {"ok": True}
