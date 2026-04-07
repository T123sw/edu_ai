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


def test_report_cards_v2_route_returns_cards_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def get_cards(self, payload):
            assert payload.owner == "tester"
            assert payload.selected_doc_ids == ["doc-1"]
            return {
                "entry_mode": "knowledge_base_report",
                "cards": [
                    {
                        "card_id": "preset-brief",
                        "card_type": "preset",
                        "title": "简要报告",
                        "description": "提炼核心信息",
                        "prompt_draft": "请基于已选文档生成简要报告",
                        "preset_key": "brief",
                    }
                ],
                "trace": {
                    "cache_hit": False,
                    "selected_doc_count": 1,
                },
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_report_entry_cards_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/report/cards",
        json={"course_id": "course-1", "selected_doc_ids": ["doc-1"]},
    )

    assert response.status_code == 200
    assert response.json()["entry_mode"] == "knowledge_base_report"
    assert response.json()["cards"][0]["card_id"] == "preset-brief"


def test_direct_report_v2_route_returns_direct_artifact_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def generate(self, payload):
            assert payload.owner == "tester"
            assert payload.selected_doc_ids == ["doc-1"]
            return {
                "action": {"name": "generate.report.direct"},
                "artifacts": [
                    {
                        "artifact_id": "report-1",
                        "artifact_type": "report",
                        "title": "测试报告.md",
                        "content": "# 测试报告\n\n正文",
                    }
                ],
                "trace": {"path": "direct", "selected_doc_count": 1},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_direct_report_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/report/direct",
        json={
            "question": "请生成报告",
            "course_id": "course-1",
            "selected_doc_ids": ["doc-1"],
        },
    )

    assert response.status_code == 200
    assert response.json()["action"]["name"] == "generate.report.direct"
    assert response.json()["artifacts"][0]["artifact_type"] == "report"


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
