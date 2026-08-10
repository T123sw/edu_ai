from __future__ import annotations

import sqlite3

from app.learning.models import LearningEventRecord, LearningTaskRecord
from app.learning.store import LearningStore


def _task(*, course_id: str = "course-1") -> LearningTaskRecord:
    return LearningTaskRecord.new(
        course_id=course_id,
        title="阅读快速排序材料",
        instructions="阅读后标记完成",
        created_by="teacher-1",
        resource_refs=[
            {"material_type": "report", "material_id": "report-1"}
        ],
        knowledge_point_ids=["quick-sort"],
    )


def test_store_persists_published_task_and_student_progress(tmp_path):
    database_path = tmp_path / "learning.db"
    store = LearningStore(database_path)
    task = _task()
    store.create_task(task)
    published = store.publish_task(
        task.task_id,
        course_id="course-1",
        published_by="teacher-1",
    )
    assert published.status == "published"

    event = LearningEventRecord.new(
        event_id="evt-1",
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_type="completed",
        progress_percent=100,
    )
    first = store.record_event(event)
    second = store.record_event(event)

    assert first.created is True
    assert second.created is False
    assert first.progress.status == "completed"
    assert first.progress.progress_percent == 100

    store.close()
    reopened = LearningStore(database_path)
    restored = reopened.get_progress(task.task_id, "student-1")
    assert restored is not None
    assert restored.status == "completed"
    assert restored.progress_percent == 100


def test_progress_is_monotonic_when_events_arrive_out_of_order(tmp_path):
    store = LearningStore(tmp_path / "learning.db")
    task = _task()
    store.create_task(task)
    store.publish_task(task.task_id, course_id=task.course_id, published_by="teacher-1")

    store.record_event(
        LearningEventRecord.new(
            event_id="evt-60",
            course_id=task.course_id,
            task_id=task.task_id,
            student_id="student-1",
            event_type="progress_updated",
            progress_percent=60,
        )
    )
    store.record_event(
        LearningEventRecord.new(
            event_id="evt-20",
            course_id=task.course_id,
            task_id=task.task_id,
            student_id="student-1",
            event_type="progress_updated",
            progress_percent=20,
        )
    )

    progress = store.get_progress(task.task_id, "student-1")
    assert progress is not None
    assert progress.status == "in_progress"
    assert progress.progress_percent == 60


def test_task_and_progress_queries_are_course_scoped(tmp_path):
    store = LearningStore(tmp_path / "learning.db")
    first = _task(course_id="course-1")
    second = _task(course_id="course-2")
    store.create_task(first)
    store.create_task(second)
    store.publish_task(first.task_id, course_id="course-1", published_by="teacher-1")

    assert [item.task_id for item in store.list_tasks("course-1")] == [first.task_id]
    assert [item.task_id for item in store.list_tasks("course-2")] == [second.task_id]
    assert store.get_task(first.task_id, course_id="course-2") is None


def _build_legacy_learning_database(database_path, *, status: str, progress: int):
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE learning_tasks (
            task_id TEXT PRIMARY KEY, course_id TEXT NOT NULL, title TEXT NOT NULL,
            instructions TEXT NOT NULL, created_by TEXT NOT NULL,
            resource_refs_json TEXT NOT NULL, knowledge_point_ids_json TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL, published_at TEXT,
            published_by TEXT
        );
        CREATE TABLE learning_events (
            event_id TEXT PRIMARY KEY, course_id TEXT NOT NULL, task_id TEXT NOT NULL,
            student_id TEXT NOT NULL, event_type TEXT NOT NULL,
            progress_percent INTEGER NOT NULL, resource_ref_json TEXT, occurred_at TEXT NOT NULL
        );
        CREATE TABLE task_progress (
            task_id TEXT NOT NULL, course_id TEXT NOT NULL, student_id TEXT NOT NULL,
            status TEXT NOT NULL, progress_percent INTEGER NOT NULL, started_at TEXT,
            completed_at TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(task_id, student_id)
        );
        """
    )
    connection.execute(
        """
        INSERT INTO learning_tasks VALUES (
            'lt_legacy', 'course-1', 'Legacy task', '', 'teacher-1', '[]', '[]',
            'published', '2026-01-01T00:00:00+00:00', NULL, NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO task_progress VALUES (
            'lt_legacy', 'course-1', 'student-a', ?, ?, '2026-01-01T00:00:00+00:00',
            '2026-01-01T01:00:00+00:00', '2026-01-01T01:00:00+00:00'
        )
        """,
        (status, progress),
    )
    connection.commit()
    return connection


def test_existing_completed_progress_migrates_as_self_reported(tmp_path):
    database_path = tmp_path / "learning.db"
    legacy = _build_legacy_learning_database(database_path, status="completed", progress=100)
    legacy.close()

    store = LearningStore(database_path)
    progress = store.get_progress("lt_legacy", "student-a")

    assert progress is not None
    assert progress.completion_basis == "self_reported"
    assert progress.evidence_count == 0
    assert progress.last_activity_at is None


def test_completion_basis_is_idempotent_and_monotonic(tmp_path):
    store = LearningStore(tmp_path / "learning.db")
    task = _task()
    store.create_task(task)
    store.publish_task(task.task_id, course_id=task.course_id, published_by="teacher-1")

    def event(event_id: str, event_type: str, progress_percent: int):
        return LearningEventRecord.new(
            event_id=event_id,
            course_id=task.course_id,
            task_id=task.task_id,
            student_id="student-1",
            event_type=event_type,
            progress_percent=progress_percent,
            occurred_at=f"2026-01-01T00:0{event_id[-1]}:00+00:00",
        )

    self_report = event("evt-1", "completed", 100)
    first = store.record_event(self_report)
    duplicate = store.record_event(self_report)
    evidenced = store.record_event(event("evt-2", "resource_completed", 100))
    late_open = store.record_event(event("evt-3", "resource_opened", 1))

    assert first.created is True
    assert duplicate.created is False
    assert evidenced.progress.completion_basis == "activity_evidenced"
    assert late_open.progress.completion_basis == "activity_evidenced"
    assert late_open.progress.progress_percent == 100
    assert late_open.progress.evidence_count == 3
    assert late_open.progress.last_activity_at == "2026-01-01T00:03:00+00:00"

