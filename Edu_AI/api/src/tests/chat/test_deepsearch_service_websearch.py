from __future__ import annotations

from app.integrations.websearch.models import ExtractResult, WebSearchHit
from app.services import deepsearch_service


def test_run_deepsearch_basic_uses_bocha_summaries_without_import(monkeypatch):
    monkeypatch.setattr(
        deepsearch_service,
        "search_bocha",
        lambda *args, **kwargs: [
            WebSearchHit(
                url="https://example.com/a",
                title="Example A",
                content="Bocha summary A",
                site="Example",
            )
        ],
    )

    def fail_import(*args, **kwargs):  # pragma: no cover - should not be called
        raise AssertionError("basic save_to_kb=False must not import to RAG")

    monkeypatch.setattr(deepsearch_service, "_import_to_knowledge_base", fail_import)

    result = deepsearch_service.run_deepsearch_and_crawl(
        query="计算思维",
        owner="teacher-a",
        depth="basic",
        save_to_kb=False,
    )

    assert result["ok"] is True
    assert result["links"] == ["https://example.com/a"]
    assert result["summary"] == "Bocha summary A"
    assert result["sources"] == [{"title": "Example A", "url": "https://example.com/a", "site": "Example"}]
    assert result["results"][0]["content"] == "Bocha summary A"
    assert result["saved_to_kb"] is False


def test_run_deepsearch_returns_error_when_bocha_search_fails(monkeypatch):
    def fail_search(*args, **kwargs):
        raise RuntimeError("bocha timeout")

    monkeypatch.setattr(deepsearch_service, "search_bocha", fail_search)

    result = deepsearch_service.run_deepsearch_and_crawl(
        query="计算思维",
        owner="teacher-a",
        depth="basic",
        save_to_kb=False,
    )

    assert result["ok"] is False
    assert "bocha timeout" in result["message"]


def test_run_deepsearch_full_falls_back_to_bocha_basic_when_tavily_fails(monkeypatch):
    monkeypatch.setattr(
        deepsearch_service,
        "search_bocha",
        lambda *args, **kwargs: [
            WebSearchHit(
                url="https://example.com/a",
                title="Example A",
                content="Bocha summary A",
                site="Example",
            )
        ],
    )

    def fail_extract(*args, **kwargs):
        raise RuntimeError("tavily timeout")

    monkeypatch.setattr(deepsearch_service, "extract_tavily", fail_extract)

    result = deepsearch_service.run_deepsearch_and_crawl(
        query="计算思维",
        owner="teacher-a",
        depth="full",
        save_to_kb=False,
    )

    assert result["ok"] is True
    assert result["summary"] == "Bocha summary A"
    assert result["results"][0]["content_type"] == "summary"
    assert result["fallback_reason"] == "tavily timeout"


def test_run_deepsearch_full_falls_back_when_tavily_returns_all_failed(monkeypatch):
    monkeypatch.setattr(
        deepsearch_service,
        "search_bocha",
        lambda *args, **kwargs: [
            WebSearchHit(
                url="https://example.com/a",
                title="Example A",
                content="Bocha summary A",
                site="Example",
            )
        ],
    )
    monkeypatch.setattr(
        deepsearch_service,
        "extract_tavily",
        lambda *args, **kwargs: [
            ExtractResult(url="https://example.com/a", content="", status="failed", error="extract_failed")
        ],
    )

    result = deepsearch_service.run_deepsearch_and_crawl(
        query="计算思维",
        owner="teacher-a",
        depth="full",
        save_to_kb=False,
    )

    assert result["ok"] is True
    assert result["summary"] == "Bocha summary A"
    assert result["success_count"] == 1
    assert result["fallback_reason"] == "tavily_all_failed"
