import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.chat.api.routes_v2 import router as v2_router


def test_chat_v2_stream_route_returns_sse_frames(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def reply_stream(self, payload):
            assert payload.owner == "tester"
            yield {"type": "metadata", "payload": {"conversation_id": "conv-1", "sources": []}}
            yield {"type": "delta", "payload": {"content": "ok"}}
            yield {
                "type": "result",
                "payload": {
                    "message": {"role": "assistant", "content": "ok"},
                    "conversation": {"conversation_id": "conv-1"},
                    "action": {"name": "chat.reply"},
                    "workflow": None,
                    "artifacts": [],
                    "sources": [],
                    "trace": {"path": "fast"},
                    "status_card": {"status_label": "普通对话"},
                },
            }
            yield {"type": "done", "payload": {"conversation_id": "conv-1"}}

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    response = TestClient(app).post("/api/chat/v2/stream", json={"question": "hello"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = [
        json.loads(line.removeprefix("data: ").strip())
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]
    assert [frame["type"] for frame in frames] == ["metadata", "delta", "result", "done"]
