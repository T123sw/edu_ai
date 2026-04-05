from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.chat.api.routes_v2 import router as v2_router


def test_reply_v2_route_returns_v2_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def reply(self, payload):
            assert payload.owner == "tester"
            return {
                "message": {"role": "assistant", "content": "ok"},
                "conversation": {"conversation_id": "conv-1"},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post("/api/chat/v2/reply", json={"question": "hello"})

    assert response.status_code == 200
    assert response.json()["action"]["name"] == "chat.reply"


def test_report_v2_route_returns_v2_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def report(self, payload):
            assert payload.owner == "tester"
            return {
                "message": {"role": "assistant", "content": "report"},
                "conversation": {"conversation_id": "conv-1"},
                "action": {"name": "generate.report"},
                "workflow": {"type": "report", "status": "running"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "report"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_report_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post("/api/chat/v2/report", json={"question": "生成报告"})

    assert response.status_code == 200
    assert response.json()["action"]["name"] == "generate.report"


def test_reply_v2_route_returns_structured_error_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def reply(self, payload):
            raise ValueError("broken")

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post("/api/chat/v2/reply", json={"question": "hello"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "workflow_failed"
    assert response.json()["error"]["message"] == "broken"


def test_reply_v2_report_intent_error_uses_workflow_trace(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def reply(self, payload):
            raise ValueError("report broken")

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/reply",
        json={"question": "帮我整理成报告"},
    )

    assert response.status_code == 500
    assert response.json()["trace"]["path"] == "workflow"
