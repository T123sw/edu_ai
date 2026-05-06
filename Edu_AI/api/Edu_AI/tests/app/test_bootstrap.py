from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient


def test_create_app_is_importable():
    from app.bootstrap import create_app

    assert callable(create_app)


@dataclass
class _DummyLecturerManager:
    started: int = 0
    stopped: int = 0

    def ensure_started(self) -> None:
        self.started += 1

    def shutdown(self) -> None:
        self.stopped += 1


class _DummyRagSystem:
    def __init__(self, document_count: int = 3) -> None:
        self.document_count = document_count

    def get_stats(self):
        return {"document_count": self.document_count}


def test_create_app_keeps_health_and_lifecycle(monkeypatch):
    from app import bootstrap
    from app.services import course_service

    manager = _DummyLecturerManager()
    monkeypatch.setattr(bootstrap, "get_ai_lecturer_process_manager", lambda: manager)
    monkeypatch.setattr("app.api.health.get_rag_system", lambda: _DummyRagSystem(document_count=4))
    monkeypatch.setattr(course_service, "ensure_default_courses", lambda: None)

    app = bootstrap.create_app()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "service ready",
        "knowledge_base_ready": True,
        "document_count": 4,
    }
    assert manager.started == 1
    assert manager.stopped == 1


def test_main_app_keeps_major_routes(monkeypatch):
    from app import bootstrap
    from app.bootstrap import create_app

    manager = _DummyLecturerManager()
    monkeypatch.setattr(bootstrap, "get_ai_lecturer_process_manager", lambda: manager)
    # patch get_rag_system in all modules that import it

    # create a fresh app to get all routes (bypassing cached module-level app)
    app = create_app()
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert {"/health", "/chat", "/teacher/lesson_plan", "/models"}.issubset(paths)
    assert any(p.startswith("/api/pipeline") for p in paths)
