from app.chat.application.route_service_factory import build_default_route_chat_service
from app.chat.application.route_chat_service import RouteChatService
from app.chat.legacy.legacy_chat_runtime import LegacyChatRuntime


def test_build_default_route_chat_service_returns_hybrid_route_service(monkeypatch):
    monkeypatch.setenv("CHAT_USE_NEW_ORCHESTRATOR", "1")
    monkeypatch.setenv("CHAT_USE_FAST_RUNTIME", "1")
    monkeypatch.setenv("CHAT_USE_REPORT_WORKFLOW_V2", "0")
    monkeypatch.setenv("CHAT_CAPABILITY_POLICY_ENFORCED", "1")
    monkeypatch.setenv("CHAT_USE_LLM_ENHANCEMENT", "0")
    monkeypatch.setenv("CHAT_TRACE_LLM_ENHANCEMENT", "0")

    service = build_default_route_chat_service()

    assert isinstance(service, RouteChatService)
    assert isinstance(service.legacy_service, LegacyChatRuntime)
    assert service.enable_new_chat is True
    assert service.enable_fast_runtime is True
    assert service.enable_report_workflow is False
    assert service.enforce_capability_policy is True
    assert service.conversation_store.enhancement_router.enabled is False
    assert service.conversation_store.enhancement_trace_enabled is False
