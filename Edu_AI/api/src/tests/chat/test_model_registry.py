from app.chat.runtime.model_registry import build_default_gateway


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
