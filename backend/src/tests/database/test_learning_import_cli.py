import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base, LearningEventModel, LearningProgressModel, LearningTaskModel


def test_learning_import_cli_imports_sqlite_tasks(tmp_path: Path, capsys):
    from app.database.migrate_learning_cli import main

    source = tmp_path / "learning.db"
    connection = sqlite3.connect(source)
    connection.execute("""CREATE TABLE learning_tasks (
        task_id TEXT PRIMARY KEY, course_id TEXT, title TEXT, instructions TEXT,
        created_by TEXT, resource_refs_json TEXT, knowledge_point_ids_json TEXT,
        status TEXT, created_at TEXT, published_at TEXT, published_by TEXT)""")
    connection.execute("""CREATE TABLE task_progress (
        task_id TEXT, course_id TEXT, student_id TEXT, status TEXT,
        progress_percent INTEGER, started_at TEXT, completed_at TEXT, updated_at TEXT)""")
    connection.execute(
        "INSERT INTO learning_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("task-1", "course-1", "Task", "Learn", "teacher", "[]", "[]", "draft", "2026-08-10T10:00:00+00:00", None, None),
    )
    connection.execute(
        "INSERT INTO task_progress VALUES (?,?,?,?,?,?,?,?)",
        ("task-1", "course-1", "student", "completed", 100, "2026-08-10T10:00:00+00:00", "2026-08-10T10:05:00+00:00", "2026-08-10T10:05:00+00:00"),
    )
    connection.commit()
    connection.close()
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'target.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    assert main(["--source", str(source), "--database-url", database_url, "--apply"]) == 0
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(LearningTaskModel)) == 1
        progress = session.get(LearningProgressModel, ("task-1", "student"))
        assert progress.completion_basis == "self_reported"
        assert progress.evidence_count == 0


def test_learning_import_cli_preserves_evidence_projection_fields(tmp_path: Path):
    from app.database.migrate_learning_cli import main

    source = tmp_path / "learning.db"
    connection = sqlite3.connect(source)
    connection.executescript(
        """
        CREATE TABLE learning_tasks (
            task_id TEXT PRIMARY KEY, course_id TEXT, title TEXT, instructions TEXT,
            created_by TEXT, resource_refs_json TEXT, knowledge_point_ids_json TEXT,
            status TEXT, created_at TEXT, published_at TEXT, published_by TEXT);
        CREATE TABLE learning_events (
            event_id TEXT PRIMARY KEY, course_id TEXT, task_id TEXT, student_id TEXT,
            event_type TEXT, progress_percent INTEGER, resource_ref_json TEXT,
            evidence_json TEXT, occurred_at TEXT);
        CREATE TABLE task_progress (
            task_id TEXT, course_id TEXT, student_id TEXT, status TEXT,
            progress_percent INTEGER, completion_basis TEXT, evidence_count INTEGER,
            last_activity_at TEXT, started_at TEXT, completed_at TEXT, updated_at TEXT);
        """
    )
    connection.execute(
        "INSERT INTO learning_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("task-1", "course-1", "Task", "Learn", "teacher", "[]", "[]", "published", "2026-08-10T10:00:00+00:00", None, None),
    )
    connection.execute(
        "INSERT INTO learning_events VALUES (?,?,?,?,?,?,?,?,?)",
        ("event-1", "course-1", "task-1", "student", "assessment_scored", 100, None, '{"evidence_type":"score","source_type":"quiz","source_id":"attempt-1","value":92}', "2026-08-10T10:02:00+00:00"),
    )
    connection.execute(
        "INSERT INTO task_progress VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("task-1", "course-1", "student", "completed", 100, "assessment_verified", 1, "2026-08-10T10:02:00+00:00", "2026-08-10T10:00:00+00:00", "2026-08-10T10:02:00+00:00", "2026-08-10T10:02:00+00:00"),
    )
    connection.commit()
    connection.close()
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'target.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    assert main(["--source", str(source), "--database-url", database_url, "--apply"]) == 0
    with Session(engine) as session:
        assert session.get(LearningEventModel, "event-1").evidence["source_id"] == "attempt-1"
        progress = session.get(LearningProgressModel, ("task-1", "student"))
        assert (progress.completion_basis, progress.evidence_count) == ("assessment_verified", 1)
        assert progress.last_activity_at is not None
