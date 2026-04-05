from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.chat.application.route_feature_flags import RouteFeatureFlags
from app.chat.legacy.compat_service import CompatChatService
from app.chat.application.route_chat_service import RouteChatService
from app.chat.routes import get_current_user, router
from app.chat.service import ChatService
import app.chat.routes as chat_routes
from core.conversation_storage import conversation_storage


def test_chat_route_accepts_compat_service_with_v2_delegate(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    compat_service = CompatChatService(
        delegate=lambda payload: {
            "message": {"role": "assistant", "content": "兼容回复"},
            "conversation": {"conversation_id": "conv-1"},
            "action": {"name": "chat.reply"},
            "artifacts": [],
            "workflow": None,
            "sources": [],
            "trace": {"path": "fast"},
        }
    )
    monkeypatch.setattr(chat_routes, "service", compat_service)

    client = TestClient(app)
    response = client.post("/api/chat", json={"question": "你好"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "兼容回复"
    assert payload["intent_category"] == "chat"


def test_chat_route_uses_hybrid_service_new_fast_path(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyGateway:
        def chat(self, messages, temperature=0.2, max_tokens=1200):
            return "新主链路回复"

    class DummyLegacyService:
        def chat(self, **kwargs):
            return {
                "answer": "旧回复",
                "conversation_id": "legacy-conv",
                "model_id": "",
                "intent_category": "chat",
                "meta": {},
            }

        def chat_stream_with_meta(self, **kwargs):
            return {"conversation_id": "legacy-conv"}, []

        @staticmethod
        def skill_health_check(meta):
            return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}

    monkeypatch.setattr(
        chat_routes,
        "service",
        RouteChatService(
            legacy_service=DummyLegacyService(),
            gateway_factory=lambda model_id: DummyGateway(),
            enable_new_chat=True,
        ),
    )

    client = TestClient(app)
    response = client.post("/api/chat", json={"question": "你好", "allow_rag": False, "allow_web": False})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "新主链路回复"
    assert payload["intent_category"] == "chat"


def test_chat_route_falls_back_for_unsupported_workflow(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyGateway:
        def chat(self, messages, temperature=0.2, max_tokens=1200):
            return "新主链路回复"

    class DummyLegacyService:
        def chat(self, **kwargs):
            return {
                "answer": "legacy-research",
                "conversation_id": "legacy-conv",
                "model_id": "",
                "intent_category": "research",
                "meta": {},
            }

        def chat_stream_with_meta(self, **kwargs):
            return {"conversation_id": "legacy-conv"}, []

        @staticmethod
        def skill_health_check(meta):
            return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}

    monkeypatch.setattr(
        chat_routes,
        "service",
        RouteChatService(
            legacy_service=DummyLegacyService(),
            gateway_factory=lambda model_id: DummyGateway(),
            enable_new_chat=True,
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={"question": "帮我查一下最新课程标准", "action_hint": "research.lookup", "allow_web": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "legacy-research"
    assert payload["intent_category"] == "research"


def test_chat_stream_route_uses_hybrid_fast_path(monkeypatch):
    app = FastAPI()
    app.include_router(router)

    class DummyGateway:
        def chat(self, messages, temperature=0.2, max_tokens=1200):
            return "流式新主链路回复"

    class DummyLegacyService:
        def chat(self, **kwargs):
            return {
                "answer": "旧回复",
                "conversation_id": "legacy-conv",
                "model_id": "",
                "intent_category": "chat",
                "meta": {},
            }

        def chat_stream_with_meta(self, **kwargs):
            return {"conversation_id": "legacy-conv"}, []

        @staticmethod
        def skill_health_check(meta):
            return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}

    monkeypatch.setattr(chat_routes.auth_manager, "get_current_user", lambda token: {"username": "tester"})
    monkeypatch.setattr(
        chat_routes,
        "service",
        RouteChatService(
            legacy_service=DummyLegacyService(),
            gateway_factory=lambda model_id: DummyGateway(),
            enable_new_chat=True,
        ),
    )

    client = TestClient(app)
    response = client.get("/api/chat/stream", params={"question": "你好", "token": "stub-token"})

    assert response.status_code == 200
    body = response.text
    assert "event: meta" in body
    assert "event: delta" in body
    assert "event: done" in body


def test_chat_stream_route_forwards_allow_web_and_action_hint(monkeypatch):
    app = FastAPI()
    app.include_router(router)

    class RecorderService:
        def __init__(self):
            self.calls = []

        def chat_stream_with_meta(self, **kwargs):
            self.calls.append(kwargs)
            return {"conversation_id": "conv-1"}, [{"type": "done"}]

        def skill_health_check(self, meta):
            return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}

    recorder = RecorderService()
    monkeypatch.setattr(chat_routes.auth_manager, "get_current_user", lambda token: {"username": "tester"})
    monkeypatch.setattr(chat_routes, "service", recorder)

    client = TestClient(app)
    response = client.get(
        "/api/chat/stream",
        params={
            "question": "帮我查一下最新课程标准",
            "token": "stub-token",
            "allow_web": "true",
            "action_hint": "research.lookup",
        },
    )

    assert response.status_code == 200
    assert recorder.calls[-1]["allow_web"] is True
    assert recorder.calls[-1]["action_hint"] == "research.lookup"


def test_chat_stream_route_passes_raw_rag_flags_without_inferring_from_selected_docs(monkeypatch):
    app = FastAPI()
    app.include_router(router)

    class RecorderService:
        def __init__(self):
            self.calls = []

        def chat_stream_with_meta(self, **kwargs):
            self.calls.append(kwargs)
            return {"conversation_id": "conv-1"}, [{"type": "done"}]

        def skill_health_check(self, meta):
            return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}

    recorder = RecorderService()
    monkeypatch.setattr(chat_routes.auth_manager, "get_current_user", lambda token: {"username": "tester"})
    monkeypatch.setattr(chat_routes, "service", recorder)

    client = TestClient(app)
    response = client.get(
        "/api/chat/stream",
        params={
            "question": "hello",
            "token": "stub-token",
            "use_rag": "false",
            "allow_rag": "false",
            "selected_doc_ids": "doc-1",
        },
    )

    assert response.status_code == 200
    assert recorder.calls[-1]["use_rag"] is False
    assert recorder.calls[-1]["allow_rag"] is False
    assert recorder.calls[-1]["selected_doc_ids"] == ["doc-1"]


def test_chat_route_passes_raw_rag_flags_without_inferring_from_selected_docs(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class RecorderService:
        def __init__(self):
            self.calls = []

        def chat(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "answer": "ok",
                "conversation_id": "conv-1",
                "model_id": "",
                "intent_category": "chat",
                "meta": {},
            }

        def skill_health_check(self, meta):
            return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}

    recorder = RecorderService()
    monkeypatch.setattr(chat_routes, "service", recorder)

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "question": "hello",
            "use_rag": False,
            "allow_rag": False,
            "selected_doc_ids": ["doc-1"],
        },
    )

    assert response.status_code == 200
    assert recorder.calls[-1]["use_rag"] is False
    assert recorder.calls[-1]["allow_rag"] is False


def test_chat_stream_route_can_emit_v2_events_with_feature_flag(monkeypatch):
    app = FastAPI()
    app.include_router(router)

    class RecorderService:
        def chat_stream_with_meta(self, **kwargs):
            return {"conversation_id": "conv-1"}, [
                {"type": "meta", "payload": {"path": "fast"}},
                {"type": "delta", "delta": "新协议内容"},
                {"type": "done"},
            ]

        def skill_health_check(self, meta):
            return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}

    monkeypatch.setattr(chat_routes.auth_manager, "get_current_user", lambda token: {"username": "tester"})
    monkeypatch.setattr(chat_routes, "service", RecorderService())
    monkeypatch.setattr(
        chat_routes,
        "FLAGS",
        RouteFeatureFlags(
            enable_new_chat=True,
            enable_fast_runtime=True,
            enable_report_workflow=False,
            enforce_capability_policy=False,
            enable_sse_v2_events=True,
            enable_llm_enhancement=False,
            trace_llm_enhancement=False,
        ),
    )

    client = TestClient(app)
    response = client.get("/api/chat/stream", params={"question": "你好", "token": "stub-token"})

    assert response.status_code == 200
    body = response.text
    assert "event: meta" in body
    assert "event: delta" in body
    assert "event: trace.meta" in body
    assert "event: message.delta" in body


def test_chat_route_interrupts_existing_workflow_instead_of_resuming(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyGateway:
        def chat(self, messages, temperature=0.2, max_tokens=1200):
            return "已中断并回到聊天"

    class DummyLegacyService:
        def chat(self, **kwargs):
            return {
                "answer": "旧回复",
                "conversation_id": kwargs.get("conversation_id") or "legacy-conv",
                "model_id": "",
                "intent_category": "chat",
                "meta": {},
            }

        def chat_stream_with_meta(self, **kwargs):
            return {"conversation_id": "legacy-conv"}, []

        @staticmethod
        def skill_health_check(meta):
            return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}

    conversation_storage.ensure_conversation("conv-interrupt", "开始报告")
    conversation_storage.update_state(
        "conv-interrupt",
        {
            "workflow_state": {
                "workflow_id": "wf-1",
                "workflow_type": "report",
                "status": "running",
                "stage": "collecting",
            }
        },
    )

    monkeypatch.setattr(
        chat_routes,
        "service",
        RouteChatService(
            legacy_service=DummyLegacyService(),
            gateway_factory=lambda model_id: DummyGateway(),
            enable_new_chat=True,
        ),
    )

    client = TestClient(app)
    response = client.post("/api/chat", json={"question": "重新开始", "conversation_id": "conv-interrupt"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "已中断并回到聊天"


def test_chat_service_exposes_report_engine_via_public_method():
    assert hasattr(ChatService, "get_report_engine")


def test_routes_module_no_longer_exposes_legacy_runtime_global():
    assert not hasattr(chat_routes, "legacy_service")


def test_routes_module_uses_service_factory_output():
    from app.chat.application.route_chat_service import RouteChatService

    chat_routes.service = None
    assert isinstance(chat_routes._get_service(), RouteChatService)


def test_list_conversations_route_filters_by_current_user(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "teacher-a"}

    class RecorderStorage:
        def list_conversations(self, owner=None):
            assert owner == "teacher-a"
            return {
                "conversations": [{"conversation_id": "conv-a", "message_count": 2}],
                "count": 1,
                "total_messages": 2,
            }

    monkeypatch.setattr(chat_routes, "conversation_storage", RecorderStorage())

    client = TestClient(app)
    response = client.get("/api/chat/conversations")

    assert response.status_code == 200
    assert response.json()["conversations"][0]["conversation_id"] == "conv-a"


def test_get_conversation_route_returns_status_card(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "teacher-a"}

    class RecorderStorage:
        def get_conversation(self, conversation_id, owner=None):
            assert conversation_id == "conv-a"
            assert owner == "teacher-a"
            return {
                "conversation_id": "conv-a",
                "title": "课堂观察",
                "history": [{"role": "user", "content": "生成报告"}],
                "message_count": 1,
                "created_at": "2026-04-03T10:00:00",
                "updated_at": "2026-04-03T10:01:00",
            }

    monkeypatch.setattr(chat_routes, "conversation_storage", RecorderStorage())
    monkeypatch.setattr(chat_routes, "_context_builder", None)
    monkeypatch.setattr(chat_routes, "_status_card_builder", None)
    monkeypatch.setattr(
        chat_routes,
        "_build_status_card_for_conversation",
        lambda conversation_id, owner: {
            "mode": "workflow",
            "status_label": "正在生成报告",
            "source_labels": ["当前会话"],
        },
    )

    client = TestClient(app)
    response = client.get("/api/chat/conversations/conv-a")

    assert response.status_code == 200
    assert response.json()["status_card"]["status_label"] == "正在生成报告"
