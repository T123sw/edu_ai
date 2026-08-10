from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.database import Base
from app.learning.models import LearningEventRecord, LearningTaskRecord


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
