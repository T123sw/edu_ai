from pathlib import Path
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.chat import routes as chat_routes
from app.chat.routes import router
from core.conversation_storage import ConversationStorage


def _build_app():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "teacher-a"}
    return app


def _make_storage() -> ConversationStorage:
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    return ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")


def test_get_conversation_route_returns_scope_fields(monkeypatch):
    storage = _make_storage()
    storage.ensure_conversation("conv-scope", "hello", owner="teacher-a")
    storage.append_message("conv-scope", "user", "hello")
    storage.update_state(
        "conv-scope",
        {
            "course_id": "course-a",
            "scope_type": "knowledge_point",
            "scope_id": "sorting",
        },
    )

    monkeypatch.setattr(chat_routes, "conversation_storage", storage)
    monkeypatch.setattr(chat_routes, "_build_status_card_for_conversation", lambda conversation_id, owner: {"mode": "idle"})
    app = _build_app()

    client = TestClient(app)
    response = client.get("/api/chat/conversations/conv-scope")

    assert response.status_code == 200
    payload = response.json()
    assert payload["course_id"] == "course-a"
    assert payload["scope_type"] == "knowledge_point"
    assert payload["scope_id"] == "sorting"


def test_list_conversations_route_filters_descendant_knowledge_points(monkeypatch):
    storage = _make_storage()
    for conversation_id, scope_type, scope_id in (
        ("conv-root", "course", None),
        ("conv-sorting", "knowledge_point", "sorting"),
        ("conv-bubble", "knowledge_point", "bubble"),
        ("conv-graphs", "knowledge_point", "graphs"),
    ):
        storage.ensure_conversation(conversation_id, conversation_id, owner="teacher-a")
        storage.append_message(conversation_id, "user", conversation_id)
        storage.update_state(
            conversation_id,
            {
                "course_id": "course-a",
                "scope_type": scope_type,
                "scope_id": scope_id,
            },
        )

    class FakeStorageManager:
        @staticmethod
        def get_knowledge_graph(course_id):
            assert course_id == "course-a"
            return {
                "id": "root",
                "children": [
                    {
                        "id": "sorting",
                        "children": [
                            {"id": "bubble", "children": []},
                        ],
                    },
                    {"id": "graphs", "children": []},
                ],
            }

    monkeypatch.setattr(chat_routes, "conversation_storage", storage)
    monkeypatch.setattr(chat_routes, "storage_manager", FakeStorageManager())
    app = _build_app()

    client = TestClient(app)
    response = client.get(
        "/api/chat/conversations",
        params={
            "course_id": "course-a",
            "scope_type": "knowledge_point",
            "scope_id": "sorting",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert {item["conversation_id"] for item in payload["conversations"]} == {
        "conv-bubble",
        "conv-sorting",
    }
    assert payload["total"] == 2


def test_list_conversations_route_aggregates_course_scope_with_pagination(monkeypatch):
    storage = _make_storage()
    for index in range(25):
        conversation_id = f"conv-{index:02d}"
        scope_type = "course" if index % 2 == 0 else "knowledge_point"
        scope_id = None if scope_type == "course" else f"kp-{index:02d}"
        storage.ensure_conversation(conversation_id, conversation_id, owner="teacher-a")
        storage.append_message(conversation_id, "user", conversation_id)
        storage.update_state(
            conversation_id,
            {
                "course_id": "course-a",
                "scope_type": scope_type,
                "scope_id": scope_id,
            },
        )

    monkeypatch.setattr(chat_routes, "conversation_storage", storage)
    app = _build_app()

    client = TestClient(app)
    response = client.get(
        "/api/chat/conversations",
        params={
            "course_id": "course-a",
            "scope_type": "course",
            "aggregate": "true",
            "limit": 20,
            "offset": 20,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 25
    assert payload["count"] == 5
    assert payload["limit"] == 20
    assert payload["offset"] == 20


def test_list_conversations_uses_active_context_scope_fallback():
    storage = _make_storage()
    storage.ensure_conversation("conv-active-context", "hello", owner="teacher-a")
    storage.append_message("conv-active-context", "user", "hello")
    storage.update_state(
        "conv-active-context",
        {
            "active_context": {
                "current_course_id": "course-a",
                "scope_type": "knowledge_point",
                "scope_id": "sorting",
            }
        },
    )

    listed = storage.list_conversations(
        owner="teacher-a",
        course_id="course-a",
        scope_type="knowledge_point",
        scope_ids={"sorting"},
    )

    assert [item["conversation_id"] for item in listed["conversations"]] == [
        "conv-active-context"
    ]
    assert listed["conversations"][0]["course_id"] == "course-a"
    assert listed["conversations"][0]["scope_type"] == "knowledge_point"
    assert listed["conversations"][0]["scope_id"] == "sorting"
