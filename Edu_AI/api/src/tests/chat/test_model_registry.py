from app.chat.runtime.model_registry import (
    build_agent_gateway,
    build_default_gateway,
    build_planner_gateway,
)


def test_build_default_gateway_uses_requested_model_id():
    gateway = build_default_gateway("deepseek-v3")

    assert gateway.model_name
    assert gateway.api_base.endswith("/v1")


def test_build_default_gateway_prefers_deep_model_by_default():
    gateway = build_default_gateway()

    assert gateway.model_name == "qwen3.5-plus"


def test_build_default_gateway_includes_fallback_candidates():
    gateway = build_default_gateway()

    assert [candidate["model_name"] for candidate in gateway.candidates] == [
        "qwen3.5-plus",
        "openai/gpt-5.4-mini",
    ]


def test_build_agent_gateway_uses_agent_model_config(monkeypatch):
    monkeypatch.setattr(
        "app.chat.runtime.model_registry.Config.get_agent_model",
        lambda: {
            "model_name": "agent-model",
            "api_base": "https://agent.example/v1",
            "api_key": "agent-key",
        },
    )
    monkeypatch.setattr(
        "app.chat.runtime.model_registry.Config.get_planner_model",
        lambda: {
            "model_name": "planner-backup",
            "api_base": "https://planner.example/v1",
            "api_key": "planner-key",
        },
    )
    monkeypatch.setattr(
        "app.chat.runtime.model_registry.Config.REMOTE_MODEL_API_BASE",
        "https://deepseek.example/v1",
    )
    monkeypatch.setattr(
        "app.chat.runtime.model_registry.Config.REMOTE_MODEL_API_KEY",
        "deepseek-key",
    )

    gateway = build_agent_gateway()

    assert gateway.model_name == "agent-model"
    assert gateway.api_base == "https://agent.example/v1"
    assert gateway.api_key == "agent-key"
    assert [item["model_name"] for item in gateway.candidates] == [
        "agent-model",
        "planner-backup",
        "deepseek-chat",
    ]


def test_build_planner_gateway_includes_configured_tool_capable_fallbacks(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.chat.runtime.model_registry.Config.QWEN_BASE_URL",
        "https://qwen.example/v1",
    )
    monkeypatch.setattr(
        "app.chat.runtime.model_registry.Config.QWEN_API_KEY",
        "qwen-key",
    )
    monkeypatch.setattr(
        "app.chat.runtime.model_registry.Config.VISION_MODEL_ID",
        "qwen-primary",
    )
    monkeypatch.setattr(
        "app.chat.runtime.model_registry.Config.get_planner_model",
        lambda: {
            "model_name": "openrouter-backup",
            "api_base": "https://openrouter.example/v1",
            "api_key": "openrouter-key",
        },
    )
    monkeypatch.setattr(
        "app.chat.runtime.model_registry.Config.REMOTE_MODEL_API_BASE",
        "https://deepseek.example/v1",
    )
    monkeypatch.setattr(
        "app.chat.runtime.model_registry.Config.REMOTE_MODEL_API_KEY",
        "deepseek-key",
    )

    gateway = build_planner_gateway()

    assert [item["model_name"] for item in gateway.candidates] == [
        "qwen-primary",
        "openrouter-backup",
        "deepseek-chat",
    ]
