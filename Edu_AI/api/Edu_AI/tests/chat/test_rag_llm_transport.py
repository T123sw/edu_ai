import os

from rag_v2.rag_main import system as runtime_system


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


def test_call_llm_uses_session_with_trust_env_disabled(monkeypatch):
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
        llm_config={"model_name": "qwen3.5-plus", "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": "test-key"},
        stream=False,
    )

    assert result == "ok"
    assert captured["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert captured["json"]["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["trust_env"] is False
    assert captured["HTTP_PROXY"] == "http://127.0.0.1:9"
