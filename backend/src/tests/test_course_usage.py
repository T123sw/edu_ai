from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from app.database import AppStateRecord
from app.persistence.postgres_app_state_repository import PostgresAppStateRepository
from app.services import course_usage
from core.config import Config
from course_api_test_support import CourseApiTestFactory


@pytest.fixture(params=["json", "postgres"])
def usage_store(request, tmp_path, monkeypatch):
    for mode in ("USER_PERSISTENCE_MODE", "COURSE_PERSISTENCE_MODE", "COURSE_MEMBERSHIP_PERSISTENCE_MODE"):
        monkeypatch.setenv(mode, "json")
    monkeypatch.setenv("APP_STATE_PERSISTENCE_MODE", request.param)
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path)
    if request.param == "postgres":
        engine = create_engine(f"sqlite:///{tmp_path / 'state.db'}")
        AppStateRecord.__table__.create(engine)
        from app.persistence import dependencies
        monkeypatch.setattr(dependencies, "get_postgres_app_state_repository", lambda: PostgresAppStateRepository(engine))
        yield
        engine.dispose()
    else:
        yield


def test_visits_are_persistent_and_isolated_by_user_and_course(usage_store):
    assert course_usage.list_course_usage("teacher-a") == {}
    first = course_usage.record_course_usage("teacher-a", "course-1")
    second = course_usage.record_course_usage("teacher-a", "course-2")
    latest = course_usage.record_course_usage("teacher-a", "course-1")
    assert latest >= first
    assert course_usage.list_course_usage("teacher-a") == {"course-1": latest, "course-2": second}
    assert course_usage.list_course_usage("teacher-b") == {}


def test_only_explicit_authorized_visit_updates_usage(usage_store, tmp_path, monkeypatch):
    factory = CourseApiTestFactory(tmp_path, monkeypatch)
    client = factory.client_for("teacher-a", "teacher")
    before = client.get("/api/courses/course-1").json()
    assert client.get("/api/courses").json()[0]["last_used_at"] is None
    assert course_usage.list_course_usage("teacher-a") == {}
    assert factory.anonymous().post("/api/courses/course-1/usage").status_code == 401
    assert factory.client_for("outsider", "teacher").post("/api/courses/course-1/usage").status_code == 403
    start = datetime.now(timezone.utc)
    response = client.post("/api/courses/course-1/usage")
    assert response.status_code == 200
    timestamp = response.json()["last_used_at"]
    assert datetime.fromisoformat(timestamp) >= start
    assert client.get("/api/courses").json()[0]["last_used_at"] == timestamp
    assert client.get("/api/courses/course-1").json()["updated_at"] == before["updated_at"]
    assert factory.client_for("teacher-b", "teacher").get("/api/courses").json()[0]["last_used_at"] is None
    assert factory.client_for("student-a", "student").post("/api/courses/course-1/usage").status_code == 200
