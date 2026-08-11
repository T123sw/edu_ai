from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql

from app.database import Base, LearningEventModel
from app.learning.models import LearningEvidence, LearningEventRecord, LearningTaskRecord
from app.persistence.postgres_learning_repository import PostgresLearningRepository


def test_learning_store_uses_postgres_without_sqlite_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'postgres-shim.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("LEARNING_PERSISTENCE_MODE", "postgres")
    sqlite_path = tmp_path / "learning.db"

    from app.learning.store import LearningStore

    store = LearningStore(sqlite_path)
    task = LearningTaskRecord.new(
        course_id="course-1", title="Task", instructions="Learn", created_by="teacher"
    )
    store.create_task(task)
    store.publish_task(task.task_id, course_id="course-1", published_by="teacher")
    result = store.record_event(
        LearningEventRecord.new(
            event_id="event-1",
            course_id="course-1",
            task_id=task.task_id,
            student_id="student",
            event_type="completed",
            progress_percent=100,
        )
    )

    assert result.created is True
    assert result.progress.status == "completed"
    assert store.get_progress(task.task_id, "student").progress_percent == 100
    assert sqlite_path.exists() is False
    store.close()


def test_postgres_learning_projection_persists_evidence_and_is_monotonic(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'learning.db').as_posix()}")
    Base.metadata.create_all(engine)
    repository = PostgresLearningRepository(engine)
    task = LearningTaskRecord.new(
        course_id="course-1", title="Task", instructions="Learn", created_by="teacher"
    )
    repository.create_task(task)
    repository.publish_task(task.task_id, "course-1", "teacher")

    def event(event_id: str, event_type: str, progress_percent: int, evidence=None):
        return LearningEventRecord.new(
            event_id=event_id,
            course_id="course-1",
            task_id=task.task_id,
            student_id="student",
            event_type=event_type,
            progress_percent=progress_percent,
            occurred_at=f"2026-08-10T10:0{event_id[-1]}:00+00:00",
            evidence=evidence,
        )

    completed = event("event-1", "completed", 100)
    first = repository.record_event(completed)
    duplicate = repository.record_event(completed)
    activity = repository.record_event(event("event-2", "resource_completed", 100))
    verified = repository.record_event(
        event(
            "event-3",
            "assessment_scored",
            100,
            LearningEvidence(
                evidence_type="score",
                source_type="quiz",
                source_id="attempt-1",
                value=92.0,
                occurred_at="2026-08-10T10:03:00+00:00",
            ),
        )
    )
    late_open = repository.record_event(event("event-4", "resource_opened", 1))

    assert first.created is True
    assert first.progress.completion_basis == "self_reported"
    assert duplicate.created is False
    assert duplicate.progress.evidence_count == 1
    assert activity.progress.completion_basis == "activity_evidenced"
    assert verified.progress.completion_basis == "assessment_verified"
    assert late_open.progress.progress_percent == 100
    assert late_open.progress.completion_basis == "assessment_verified"
    assert late_open.progress.evidence_count == 4
    assert late_open.progress.last_activity_at == "2026-08-10T10:04:00+00:00"

    with engine.connect() as connection:
        evidence = connection.execute(
            select(LearningEventModel.evidence).where(LearningEventModel.event_id == "event-3")
        ).scalar_one()
    assert evidence["source_id"] == "attempt-1"
    assert repository.get_progress(task.task_id, "student") == late_open.progress


def test_postgres_event_insert_uses_database_conflict_handling():
    task = LearningTaskRecord.new(
        course_id="course-1", title="Task", instructions="Learn", created_by="teacher"
    )
    statement = PostgresLearningRepository._event_insert(
        postgresql.insert,
        LearningEventRecord.new(
            event_id="event-1",
            course_id="course-1",
            task_id=task.task_id,
            student_id="student",
            event_type="started",
            progress_percent=1,
        ),
    )

    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (event_id) DO NOTHING" in sql
    assert "RETURNING learning_events.event_id" in sql
