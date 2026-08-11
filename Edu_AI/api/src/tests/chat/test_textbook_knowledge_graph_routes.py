from io import BytesIO
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app import courses as courses_module
from app.api import courses as courses_api
from app.services.course_access import CoursePrincipal
from app.services import course_service


class DummyManager:
    def get_course_info(self, course_id: str):
        if course_id == "course-1":
            return {"id": "course-1", "title": "Course 1"}
        return None

    def create_course_structure(self, course_id: str):
        return True

    def save_course_info(self, course_id: str, info: dict):
        return True


def make_client():
    app = FastAPI()
    app.include_router(courses_module.router)
    app.dependency_overrides[courses_module.get_current_user] = lambda: {"username": "teacher-a"}
    app.dependency_overrides[courses_api.require_course_generate] = lambda: CoursePrincipal(
        course_id="course-1",
        user_id="teacher-a",
        system_role="teacher",
        course_role="editor",
    )
    return TestClient(app)


def test_legacy_textbook_import_route_is_retired(monkeypatch):
    monkeypatch.setattr(course_service, "_get_manager", lambda: DummyManager())

    response = make_client().post(
        "/api/courses/course-1/knowledge-graph/textbook-import",
        files={"file": ("book.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
    )

    assert response.status_code == 410
    payload = response.json()
    assert payload["detail"]["code"] == "LEGACY_TEXTBOOK_IMPORT_RETIRED"
    assert "knowledge-builds" in payload["detail"]["replacement"]
