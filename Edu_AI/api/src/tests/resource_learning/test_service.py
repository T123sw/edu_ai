from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.resource_learning.models import (
    ManifestQuestion,
    ManifestScene,
    ResourceLearningManifestRecord,
)
from app.resource_learning.repository import ResourceLearningRepository
from app.resource_learning.service import ResourceLearningRuleError, ResourceLearningService


NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def _service() -> ResourceLearningService:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return ResourceLearningService(ResourceLearningRepository(engine), clock=lambda: NOW)


def _manifest(*, mode: str = "completable") -> ResourceLearningManifestRecord:
    questions = (
        ManifestQuestion("q1", "quiz-1", "single", True, ("B",), ("kp-1",)),
        ManifestQuestion("q2", "quiz-1", "single", True, ("A",), ("kp-1",)),
    )
    return ResourceLearningManifestRecord(
        manifest_id=f"manifest-{mode}",
        course_id="course-1",
        resource_id="classroom-1",
        resource_version=3,
        content_hash="abc",
        mode=mode,  # type: ignore[arg-type]
        scenes=(
            ManifestScene("s1", "explanation", 100_000, ("a1",), ()),
            ManifestScene("quiz-1", "exercise", 0, (), tuple(q.question_id for q in questions)),
            ManifestScene("demo-1", "demo", 0, (), ()),
        ),
        questions=questions if mode == "completable" else (),
        created_at="2026-08-31T00:00:00+00:00",
    )


def _heartbeat(event_id: str, sequence: int, start: int, end: int) -> dict:
    return {
        "event_id": event_id,
        "sequence_number": sequence,
        "event_type": "timeline_heartbeat",
        "scene_id": "s1",
        "timeline_from_ms": start,
        "timeline_to_ms": end,
        "occurred_at": NOW,
    }


def test_progress_requires_eighty_percent_and_every_required_question() -> None:
    service = _service()
    service.freeze_manifest(_manifest())
    session = service.start_session("course-1", "classroom-1", 3, "student-1")
    service.record_events(
        session.session_id,
        "student-1",
        [_heartbeat(f"e{index}", index, start, start + 20_000) for index, start in enumerate(range(0, 80_000, 20_000), 1)],
    )

    progress = service.get_my_progress("course-1", "classroom-1", 3, "student-1")
    assert progress.status == "in_progress"
    assert progress.explanation_coverage_percent == 80.0

    service.submit_questions(
        "course-1",
        "classroom-1",
        3,
        "student-1",
        {"q1": "wrong", "q2": "wrong"},
        "submit-1",
    )
    progress = service.get_my_progress("course-1", "classroom-1", 3, "student-1")
    assert progress.status == "completed"
    assert progress.answered_question_count == 2
    assert progress.correct_count_latest == 0


def test_event_validation_rejects_unknown_scene_long_spans_and_wrong_owner() -> None:
    service = _service()
    service.freeze_manifest(_manifest())
    session = service.start_session("course-1", "classroom-1", 3, "student-1")

    with pytest.raises(ResourceLearningRuleError, match="scene"):
        event = _heartbeat("unknown", 1, 0, 10_000)
        event["scene_id"] = "missing"
        service.record_events(session.session_id, "student-1", [event])
    with pytest.raises(ResourceLearningRuleError, match="20"):
        service.record_events(session.session_id, "student-1", [_heartbeat("long", 1, 0, 20_001)])
    with pytest.raises(ResourceLearningRuleError, match="owner"):
        service.record_events(session.session_id, "student-2", [_heartbeat("owner", 1, 0, 1_000)])


def test_duplicate_event_is_idempotent_but_sequence_collision_is_rejected() -> None:
    service = _service()
    service.freeze_manifest(_manifest())
    session = service.start_session("course-1", "classroom-1", 3, "student-1")
    event = _heartbeat("event-1", 1, 0, 10_000)

    first = service.record_events(session.session_id, "student-1", [event])
    second = service.record_events(session.session_id, "student-1", [event])
    assert first == second

    with pytest.raises(ResourceLearningRuleError, match="sequence"):
        service.record_events(session.session_id, "student-1", [_heartbeat("event-2", 1, 10_000, 20_000)])


def test_question_submission_is_idempotent_and_completion_never_regresses() -> None:
    service = _service()
    service.freeze_manifest(_manifest())
    session = service.start_session("course-1", "classroom-1", 3, "student-1")
    service.record_events(
        session.session_id,
        "student-1",
        [_heartbeat(f"e{index}", index, start, start + 20_000) for index, start in enumerate(range(0, 80_000, 20_000), 1)],
    )

    first = service.submit_questions("course-1", "classroom-1", 3, "student-1", {"q1": "B", "q2": "A"}, "same")
    second = service.submit_questions("course-1", "classroom-1", 3, "student-1", {"q1": "wrong", "q2": "wrong"}, "same")
    assert first == second
    assert second.status == "completed"
    assert second.correct_count_latest == 2


def test_behavior_only_classroom_records_activity_but_never_completes() -> None:
    service = _service()
    service.freeze_manifest(_manifest(mode="behavior_only"))
    session = service.start_session("course-1", "classroom-1", 3, "student-1")
    service.record_events(
        session.session_id,
        "student-1",
        [
            _heartbeat(f"e{index}", index, start, start + 20_000)
            for index, start in enumerate(range(0, 100_000, 20_000), 1)
        ],
    )

    progress = service.get_my_progress("course-1", "classroom-1", 3, "student-1")
    assert progress.explanation_coverage_percent == 100.0
    assert progress.status == "in_progress"
