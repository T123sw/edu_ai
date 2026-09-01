from sqlalchemy import create_engine, delete
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.database.models import ResourceLearningProgressModel
from app.database.session import database_session
from app.resource_learning.models import ManifestQuestion, ManifestScene, ResourceLearningManifestRecord
from app.resource_learning.repository import ResourceLearningRepository
from app.resource_learning.service import ResourceLearningService


def _service():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    repository = ResourceLearningRepository(engine)
    service = ResourceLearningService(repository)
    service.freeze_manifest(ResourceLearningManifestRecord(
        manifest_id="m1", course_id="c1", resource_id="r1", resource_version=3,
        content_hash="hash", mode="completable",
        scenes=(ManifestScene("slide", "explanation", 1000, (), ()),),
        questions=(ManifestQuestion("q1", "quiz", "single", True, ("A",), ()),),
        created_at="2026-08-31T00:00:00+00:00",
    ))
    return engine, service


def test_projection_rebuilds_from_durable_coverage_and_attempts():
    engine, service = _service()
    session = service.start_session("c1", "r1", 3, "student-1")
    service.record_events(session.session_id, "student-1", [{
        "event_id": "e1", "sequence_number": 1, "event_type": "timeline_heartbeat",
        "scene_id": "slide", "timeline_from_ms": 0, "timeline_to_ms": 800,
        "occurred_at": "2026-08-31T00:00:00+00:00",
    }])
    service.submit_questions("c1", "r1", 3, "student-1", {"q1": "wrong"}, "a1")
    with database_session(engine=engine) as db:
        db.execute(delete(ResourceLearningProgressModel))

    rebuilt = service.rebuild_progress("c1", "r1", 3, "student-1")

    assert rebuilt.explanation_coverage_percent == 80.0
    assert rebuilt.answered_question_count == 1
    assert rebuilt.status == "completed"


def test_start_resumes_an_active_session_for_outbox_recovery():
    _engine, service = _service()
    first = service.start_session("c1", "r1", 3, "student-1")
    second = service.start_session("c1", "r1", 3, "student-1")
    assert second.session_id == first.session_id
