from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.learning.models import LearningTaskRecord, LearningTaskResourceSnapshot
from app.resource_learning.models import (
    ManifestQuestion,
    ManifestScene,
    ResourceLearningManifestRecord,
)
from app.resource_learning.repository import ResourceLearningRepository
from app.resource_learning.service import ResourceLearningService
from app.resource_learning.task_evidence import TaskResourceEvidenceAdapter


def _setup(*, complete=True):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    repository = ResourceLearningRepository(engine)
    service = ResourceLearningService(repository)
    manifest = ResourceLearningManifestRecord(
        manifest_id="m3", course_id="course-1", resource_id="classroom-1",
        resource_version=3, content_hash="hash", mode="completable",
        scenes=(ManifestScene("slide", "explanation", 1000, (), ()),),
        questions=(ManifestQuestion("q1", "quiz", "single", True, ("A",), ()),),
        created_at="2026-08-31T00:00:00+00:00",
    )
    service.freeze_manifest(manifest)
    progress = None
    if complete:
        session = service.start_session("course-1", "classroom-1", 3, "student-1")
        service.record_events(session.session_id, "student-1", [{
            "event_id": "event-1", "sequence_number": 1,
            "event_type": "timeline_heartbeat", "scene_id": "slide",
            "timeline_from_ms": 0, "timeline_to_ms": 800,
            "occurred_at": "2026-08-31T00:00:00+00:00",
        }])
        progress = service.submit_questions(
            "course-1", "classroom-1", 3, "student-1", {"q1": "wrong"}, "attempt-1"
        )
        assert progress.status == "completed"
    return service, TaskResourceEvidenceAdapter(repository), progress


def _task(
    task_id: str,
    version: int,
    *,
    source_material_type: str = "classroom",
    source_material_id: str = "classroom-1",
    standard_kind: str = "classroom",
):
    snapshot = LearningTaskResourceSnapshot(
        snapshot_id=f"snap-{task_id}", task_id=task_id, position=0,
        source_material_type=source_material_type, source_material_id=source_material_id,
        source_version=version, origin_type="standard", standard_kind=standard_kind,
        title="课堂", content_payload={}, file_refs=[],
    )
    return LearningTaskRecord(
        task_id=task_id, course_id="course-1", title="任务", instructions="",
        created_by="teacher-1", resource_snapshots=[snapshot], status="published",
    )


def test_same_version_completion_is_reused_without_completing_the_task():
    _service, adapter, progress = _setup()
    refs = adapter.initialize_task(_task("task-v3", 3), student_ids=["student-1"])

    assert refs[0].condition_status == "satisfied"
    assert refs[0].resource_completed_at == progress.completed_at


def test_different_version_is_not_reused_and_initialization_is_idempotent():
    _service, adapter, _progress = _setup()
    task = _task("task-v2", 2)
    first = adapter.initialize_task(task, student_ids=["student-1"])
    second = adapter.initialize_task(task, student_ids=["student-1"])

    assert first[0].condition_status == "pending"
    assert len(second) == 1


def test_non_standard_classroom_snapshot_does_not_create_evidence():
    _service, adapter, _progress = _setup()
    task = _task("legacy", 3)
    task.resource_snapshots[0] = LearningTaskResourceSnapshot(
        **{**task.resource_snapshots[0].__dict__, "origin_type": "legacy_shared"}
    )
    assert adapter.initialize_task(task, student_ids=["student-1"]) == []


def test_later_resource_completion_satisfies_pending_reference():
    service, adapter, _progress = _setup(complete=False)
    task = _task("task-later", 3)
    assert adapter.initialize_task(task, student_ids=["student-1"])[0].condition_status == "pending"

    session = service.start_session("course-1", "classroom-1", 3, "student-1")
    service.record_events(session.session_id, "student-1", [{
        "event_id": "later-1", "sequence_number": 1,
        "event_type": "timeline_heartbeat", "scene_id": "slide",
        "timeline_from_ms": 0, "timeline_to_ms": 800,
        "occurred_at": "2026-08-31T00:00:00+00:00",
    }])
    service.submit_questions(
        "course-1", "classroom-1", 3, "student-1", {"q1": "wrong"}, "later-attempt"
    )

    assert adapter.list_for_task_student("task-later", student_id="student-1")[0].condition_status == "satisfied"


def test_standard_report_snapshot_uses_explicit_reading_progress_as_evidence():
    service, adapter, _progress = _setup(complete=False)
    task = _task(
        "task-report",
        2,
        source_material_type="report",
        source_material_id="report-1",
        standard_kind="study_guide",
    )
    assert adapter.initialize_task(task, student_ids=["student-1"])[0].condition_status == "pending"

    service.record_explicit_activity(
        "course-1", "report-1", 2, "student-1",
        event_id="read-complete-1", action="completed",
        occurred_at="2026-09-01T00:00:00+00:00",
    )

    assert adapter.list_for_task_student(
        "task-report", student_id="student-1"
    )[0].condition_status == "satisfied"
