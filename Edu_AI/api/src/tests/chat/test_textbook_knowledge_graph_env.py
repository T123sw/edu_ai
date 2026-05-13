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
    env_path.write_text("PPT_LLM_API_KEY=test-key\nPPT_LLM_API_BASE=https://example.com\n", encoding="utf-8")

    fake_module_file = app_dir / "textbook_knowledge_graph.py"
    fake_module_file.write_text("# test placeholder\n", encoding="utf-8")

    monkeypatch.setattr(textbook_module, "__file__", str(fake_module_file))
    monkeypatch.delenv("TEXTBOOK_PIPELINE_ENV_PATH", raising=False)

    values, resolved_path = textbook_module._resolve_llm_env_values()

    assert values["PPT_LLM_API_KEY"] == "test-key"
    assert resolved_path == env_path
