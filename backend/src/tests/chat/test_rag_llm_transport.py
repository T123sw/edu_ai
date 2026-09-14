import os

from modules.rag_v2.rag_main import system as runtime_system


class _DummyRagSystem:
    llm_model = "qwen3.5-plus"
    api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key = "test-key"


class _FakeResponse:
    status_code = 200

    @staticmethod
    def json():
        return {"choices": [{"message": {"content": "ok"}}]}

    @staticmethod
    def close():
        return None


def test_call_llm_uses_session_with_system_proxy_support(monkeypatch):
    captured = {}

    class FakeSession:
        def __init__(self):
            self.trust_env = True

        def post(self, url, json=None, headers=None, timeout=None, stream=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            captured["timeout"] = timeout
            captured["stream"] = stream
            captured["trust_env"] = self.trust_env
            captured["HTTP_PROXY"] = os.environ.get("HTTP_PROXY")
            return _FakeResponse()

        @staticmethod
        def close():
            return None

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setattr(runtime_system.requests, "Session", FakeSession)

    result = runtime_system.RAGSystem._call_llm(
        _DummyRagSystem(),
        prompt="hello",
        llm_config={
            "model_name": "qwen3.5-plus",
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "test-key",
            "max_tokens": 8192,
            "thinking": "disabled",
        },
        stream=False,
    )

    assert result == "ok"
    assert captured["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert captured["json"]["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["json"]["enable_thinking"] is False
    assert captured["json"]["max_tokens"] == 8192
    assert captured["json"]["thinking"] == {"type": "disabled"}
    assert captured["timeout"] == 120
    assert captured["trust_env"] is True
    assert captured["HTTP_PROXY"] == "http://127.0.0.1:9"


def test_call_llm_routes_completion_through_deepseek_key_policy(monkeypatch):
    captured = {}

    class FakeSession:
        trust_env = True

        def post(self, url, json=None, headers=None, timeout=None, stream=None):
            captured["url"] = url
            captured["authorization"] = headers["Authorization"]
            return _FakeResponse()

        @staticmethod
        def close():
            return None

    def route(base_url, api_key):
        captured["requested"] = (base_url, api_key)
        return "http://127.0.0.1:43123/v1", "local-transport-token"

    monkeypatch.setattr(runtime_system.requests, "Session", FakeSession)
    monkeypatch.setattr(
        "app.services.deepseek_key_failover.completion_endpoint",
        route,
    )

    result = runtime_system.RAGSystem._call_llm(
        _DummyRagSystem(),
        prompt="hello",
        llm_config={
            "model_name": "deepseek-chat",
            "api_base": "https://api.deepseek.example/v1",
            "api_key": "stale-role-key",
        },
        stream=False,
    )

    assert result == "ok"
    assert captured["requested"] == (
        "https://api.deepseek.example/v1",
        "stale-role-key",
    )
    assert captured["url"] == "http://127.0.0.1:43123/v1/chat/completions"
    assert captured["authorization"] == "Bearer local-transport-token"
