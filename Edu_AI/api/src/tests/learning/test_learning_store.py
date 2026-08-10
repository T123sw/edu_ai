from __future__ import annotations

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

