from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api import resource_learning as api
from app.database.base import Base
from app.resource_learning.models import ManifestQuestion, ManifestScene, ResourceLearningManifestRecord
from app.resource_learning.repository import ResourceLearningRepository
from app.resource_learning.service import ResourceLearningService
from app.services.course_access import CoursePrincipal


@pytest.fixture
def api_clients():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    service = ResourceLearningService(ResourceLearningRepository(engine))
    service.freeze_manifest(
        ResourceLearningManifestRecord(
            manifest_id="manifest-1",
            course_id="course-1",
            resource_id="classroom-1",
            resource_version=3,
            content_hash="abc",
            mode="completable",
            scenes=(
                ManifestScene("s1", "explanation", 60_000, ("a1",), ()),
                ManifestScene("q-scene", "exercise", 0, (), ("q1",)),
            ),
            questions=(ManifestQuestion("q1", "q-scene", "single", True, ("B",), ()),),
            created_at=datetime.now(UTC).isoformat(),
        )
    )

    def client(user_id: str, role: str):
        app = FastAPI()
        app.include_router(api.router)
        principal = CoursePrincipal(
            course_id="course-1",
            user_id=user_id,
            system_role="student" if role == "viewer" else "teacher",
            course_role=role,
        )
        app.dependency_overrides[api.get_resource_learning_service] = lambda: service
        app.dependency_overrides[api.require_course_read] = lambda: principal
        if role == "viewer":
            def deny_edit():
                raise HTTPException(status_code=403, detail={"code": "COURSE_ACCESS_DENIED"})
            app.dependency_overrides[api.require_course_edit] = deny_edit
        else:
            app.dependency_overrides[api.require_course_edit] = lambda: principal
        return TestClient(app)

    try:
        yield client("student-1", "viewer"), client("teacher-1", "editor")
    finally:
        engine.dispose()


def test_student_can_write_only_own_session(api_clients) -> None:
    student, _teacher = api_clients
    started = student.post(
        "/api/courses/course-1/resources/classroom-1/versions/3/learning/sessions"
    )

    assert started.status_code == 201
    payload = started.json()
    assert "student_id" not in payload
    denied = student.get(
        "/api/courses/course-1/resources/classroom-1/versions/3/learning/students/student-2"
    )
    assert denied.status_code == 403


def test_client_cannot_post_progress_or_correctness(api_clients) -> None:
    student, _teacher = api_clients
    session = student.post(
        "/api/courses/course-1/resources/classroom-1/versions/3/learning/sessions"
    ).json()
    response = student.post(
        f"/api/courses/course-1/resources/classroom-1/versions/3/learning/sessions/{session['session_id']}/events:batch",
        json={
            "events": [
                {
                    "event_id": "e1",
                    "sequence_number": 1,
                    "event_type": "timeline_heartbeat",
                    "scene_id": "s1",
                    "timeline_from_ms": 0,
                    "timeline_to_ms": 10_000,
                    "occurred_at": datetime.now(UTC).isoformat(),
                    "progress_percent": 100,
                    "is_correct": True,
                }
            ]
        },
    )

    assert response.status_code == 422


def test_student_progress_has_safe_manifest_without_scoring_values(api_clients) -> None:
    student, _teacher = api_clients
    student.post(
        "/api/courses/course-1/resources/classroom-1/versions/3/learning/sessions"
    )

    response = student.get(
        "/api/courses/course-1/resources/classroom-1/versions/3/learning/me"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["manifest"]["required_question_ids"] == ["q1"]
    assert "questions" not in payload["manifest"]
    assert "scoring_values" not in str(payload)


def test_teacher_can_read_student_progress_but_not_write_for_them(api_clients) -> None:
    student, teacher = api_clients
    student.post(
        "/api/courses/course-1/resources/classroom-1/versions/3/learning/sessions"
    )

    response = teacher.get(
        "/api/courses/course-1/resources/classroom-1/versions/3/learning/students/student-1"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "not_started"
