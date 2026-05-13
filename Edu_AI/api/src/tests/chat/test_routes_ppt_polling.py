from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.chat.routes as chat_routes
from app.chat.routes import get_current_user, router


def test_get_conversation_refreshes_running_ppt_edit_before_returning_payload(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "teacher-a"}

    calls = []

    class RecorderStorage:
        def get_conversation(self, conversation_id, owner=None):
            calls.append(("get_conversation", conversation_id, owner))
            return {
                "conversation_id": conversation_id,
                "history": [],
                "message_count": 0,
                "state": {"workflow_state": {"status": "running"}},
            }

    monkeypatch.setattr(chat_routes, "conversation_storage", RecorderStorage())
    monkeypatch.setattr(
        chat_routes,
        "_maybe_refresh_running_ppt_edit_conversation",
        lambda conversation_id, owner: calls.append(("refresh", conversation_id, owner)),
    )
    monkeypatch.setattr(
        chat_routes,
        "_build_status_card_for_conversation",
        lambda conversation_id, owner: {"mode": "workflow", "status_label": "running"},
    )

    client = TestClient(app)
    response = client.get("/api/chat/conversations/conv-ppt-1")

    assert response.status_code == 200
    assert calls[0] == ("refresh", "conv-ppt-1", "teacher-a")
    assert calls[1] == ("get_conversation", "conv-ppt-1", "teacher-a")
