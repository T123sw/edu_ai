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
    return TestClient(app)


def test_textbook_import_route_returns_graph_payload(monkeypatch):
    monkeypatch.setattr(course_service, "_get_manager", lambda: DummyManager())
    monkeypatch.setattr(
        courses_api,
        "import_textbook_into_knowledge_graph",
        lambda **kwargs: {
            "source_document": {"name": "book.pdf"},
            "parser_used": "mineru",
            "outline_source": "llm",
            "knowledge_graph": {
                "root": {
                    "id": "root",
                    "label": "Course",
                    "children": [],
                    "data": {"level": 0, "hasChildren": False, "type": "concept"},
                }
            },
            "split_documents": [],
            "vectorized_documents": [],
            "warnings": [],
        },
    )

    response = make_client().post(
        "/api/courses/course-1/knowledge-graph/textbook-import",
        files={"file": ("book.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_document"]["name"] == "book.pdf"
    assert payload["knowledge_graph"]["root"]["id"] == "root"
