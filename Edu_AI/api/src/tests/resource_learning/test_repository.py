from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.resource_learning.models import (
    ManifestQuestion,
    ManifestScene,
    ResourceLearningManifestRecord,
)
from app.resource_learning.repository import ResourceLearningRepository


def _repository() -> ResourceLearningRepository:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return ResourceLearningRepository(engine)


def _manifest() -> ResourceLearningManifestRecord:
    return ResourceLearningManifestRecord(
        manifest_id="manifest-1",
        course_id="course-1",
        resource_id="classroom-1",
        resource_version=3,
        content_hash="abc",
        mode="completable",
        scenes=(ManifestScene("s1", "explanation", 100_000, ("a1",), ()),),
        questions=(ManifestQuestion("q1", "quiz-1", "single", True, ("B",), ("kp-1",)),),
        created_at="2026-08-31T00:00:00+00:00",
    )


def test_freeze_manifest_is_idempotent_for_the_same_immutable_content() -> None:
    repository = _repository()

    first = repository.freeze_manifest(_manifest())
    second = repository.freeze_manifest(_manifest())

    assert first == second
    assert repository.get_manifest("course-1", "classroom-1", 3) == first


def test_starting_again_resumes_the_previous_active_session() -> None:
    repository = _repository()
    repository.freeze_manifest(_manifest())
    now = datetime(2026, 8, 31, tzinfo=UTC)

    first = repository.start_session(
        course_id="course-1",
        resource_id="classroom-1",
        resource_version=3,
        student_id="student-1",
        now=now,
    )
    second = repository.start_session(
        course_id="course-1",
        resource_id="classroom-1",
        resource_version=3,
        student_id="student-1",
        now=now,
    )

    assert second.session_id == first.session_id
    assert repository.get_session(first.session_id).status == "active"
