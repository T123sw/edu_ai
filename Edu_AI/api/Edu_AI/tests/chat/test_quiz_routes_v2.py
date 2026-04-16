from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.chat.api.routes_v2 import router as v2_router


def test_reply_v2_quiz_intent_error_uses_workflow_trace(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def reply(self, payload):
            raise ValueError("quiz broken")

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/reply",
        json={"question": "generate a quiz", "action_hint": "generate.quiz"},
    )

    assert response.status_code == 500
    assert response.json()["trace"]["path"] == "workflow"
