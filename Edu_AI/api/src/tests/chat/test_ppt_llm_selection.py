from app.chat.agents import report_generation


def test_get_ppt_llm_prefers_ppt_specific_env(monkeypatch):
    created = {}

    class DummyChatOpenAI:
        def __init__(self, **kwargs):
            created.update(kwargs)

    monkeypatch.setenv("PPT_LLM_API_BASE", "https://api.vectorengine.ai")
    monkeypatch.setenv("PPT_LLM_API_KEY", "ppt-key")
    monkeypatch.setenv("PPT_LLM_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setattr(report_generation, "ChatOpenAI", DummyChatOpenAI)

    llm = report_generation.get_ppt_llm()

    assert isinstance(llm, DummyChatOpenAI)
    assert created["base_url"] == "https://api.vectorengine.ai/v1"
    assert created["api_key"] == "ppt-key"
    assert created["model"] == "gemini-3.1-pro-preview"


def test_get_ppt_llm_keeps_existing_v1_suffix(monkeypatch):
    created = {}

    class DummyChatOpenAI:
        def __init__(self, **kwargs):
            created.update(kwargs)

    monkeypatch.setenv("PPT_LLM_API_BASE", "https://api.vectorengine.ai/v1")
    monkeypatch.setenv("PPT_LLM_API_KEY", "ppt-key")
    monkeypatch.setenv("PPT_LLM_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setattr(report_generation, "ChatOpenAI", DummyChatOpenAI)

    llm = report_generation.get_ppt_llm()

    assert isinstance(llm, DummyChatOpenAI)
    assert created["base_url"] == "https://api.vectorengine.ai/v1"


def test_get_ppt_llm_falls_back_to_default_llm_when_ppt_env_missing(monkeypatch):
    sentinel = object()

    monkeypatch.delenv("PPT_LLM_API_BASE", raising=False)
    monkeypatch.delenv("PPT_LLM_API_KEY", raising=False)
    monkeypatch.delenv("PPT_LLM_MODEL", raising=False)
    monkeypatch.setattr(report_generation, "get_fallback_llm", lambda: sentinel)

    assert report_generation.get_ppt_llm() is sentinel
