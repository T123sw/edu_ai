from pathlib import Path
import sys

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app import textbook_knowledge_graph as textbook_module


def test_resolve_llm_env_values_prefers_backend_repo_env(monkeypatch, tmp_path):
    backend_root = tmp_path / "Edu_AI" / "api" / "Edu_AI"
    app_dir = backend_root / "app"
    app_dir.mkdir(parents=True)
    env_path = backend_root / ".env"
    env_path.write_text("ANSWER_LLM_API_KEY=test-key\nANSWER_LLM_API_BASE=https://example.com\n", encoding="utf-8")

    fake_module_file = app_dir / "textbook_knowledge_graph.py"
    fake_module_file.write_text("# test placeholder\n", encoding="utf-8")

    monkeypatch.setattr(textbook_module, "__file__", str(fake_module_file))
    monkeypatch.delenv("TEXTBOOK_PIPELINE_ENV_PATH", raising=False)

    values, resolved_path = textbook_module._resolve_llm_env_values()

    assert values["ANSWER_LLM_API_KEY"] == "test-key"
    assert resolved_path == env_path


def test_textbook_completion_uses_central_deepseek_key_policy(monkeypatch):
    captured = {}

    def route(base_url, api_key):
        captured["requested"] = (base_url, api_key)
        return "http://127.0.0.1:43123/v1", "local-transport-token"

    def post(url, **kwargs):
        captured["url"] = url
        captured["authorization"] = kwargs["headers"]["Authorization"]
        return object()

    monkeypatch.setattr(
        "app.services.deepseek_key_failover.completion_endpoint",
        route,
    )
    monkeypatch.setattr(textbook_module.requests, "post", post)

    response = textbook_module._post_chat_completion(
        {
            "api_base": "https://api.deepseek.example/v1",
            "api_key": "stale-role-key",
        },
        {"model": "deepseek-chat", "messages": []},
        timeout=120,
    )

    assert response is not None
    assert captured["requested"] == (
        "https://api.deepseek.example/v1",
        "stale-role-key",
    )
    assert captured["url"] == "http://127.0.0.1:43123/v1/chat/completions"
    assert captured["authorization"] == "Bearer local-transport-token"
