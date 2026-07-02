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


def test_run_deepsearch_uses_bocha_recall_and_reranks_to_requested_urls(monkeypatch):
    search_calls = []
    rerank_calls = []

    hits = [
        WebSearchHit(url="https://example.com/low", title="Low", content="barely relevant"),
        WebSearchHit(url="https://example.com/high", title="High", content="very relevant"),
        WebSearchHit(url="https://example.com/mid", title="Mid", content="somewhat relevant"),
    ]

    def fake_search(*args, **kwargs):
        search_calls.append(kwargs)
        return hits

    class FakeRank:
        def __init__(self, index, score):
            self.index = index
            self.score = score

    def fake_rerank(query, documents, **kwargs):
        rerank_calls.append({"query": query, "documents": documents, **kwargs})
        return [FakeRank(1, 0.99), FakeRank(2, 0.50)]

    monkeypatch.setattr(deepsearch_service, "search_bocha", fake_search)
    monkeypatch.setattr(deepsearch_service, "rerank_bocha", fake_rerank)

    result = deepsearch_service.run_deepsearch_and_crawl(
        query="RAG latest",
        owner="teacher-a",
        depth="basic",
        max_urls=2,
        save_to_kb=False,
    )

    assert search_calls[0]["count"] == 50
    assert rerank_calls[0]["top_n"] == 2
    assert "Title: Low" in rerank_calls[0]["documents"][0]
    assert result["links"] == ["https://example.com/high", "https://example.com/mid"]
    assert result["results"][0]["title"] == "High"


def test_import_to_knowledge_base_delegates_to_importer(monkeypatch):
    calls = []

    class FakeBatch:
        results = []

    class FakeRAGSystem:
        pass

    monkeypatch.setattr(deepsearch_service, "get_rag_system", lambda: FakeRAGSystem())

    def fake_import(**kwargs):
        calls.append(kwargs)
        return [{"file_path": "/tmp/doc.md", "index_key": "k", "file_name": "doc.md", "url": "https://example.com"}]

    monkeypatch.setattr(deepsearch_service, "import_crawl_results_to_rag", fake_import)

    imported = deepsearch_service._import_to_knowledge_base(
        FakeBatch(),
        owner="teacher-a",
        course_id=None,
        scope_type=None,
        scope_id=None,
    )

    assert imported
    # 摘要复用博查结果，导入层不再接受 LLM 摘要开关（旧链路已删除）
    assert "generate_summary" not in calls[0]


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


def test_run_deepsearch_full_uses_tavily_advanced_and_preserves_long_content(monkeypatch):
    long_content = "long article " * 400
    extract_calls = []

    monkeypatch.setattr(
        deepsearch_service,
        "search_bocha",
        lambda *args, **kwargs: [
            WebSearchHit(
                url="https://example.com/a",
                title="Example A",
                content="Bocha summary A",
                images=["https://example.com/bocha.png"],
                site="Example",
            )
        ],
    )

    def fake_extract(*args, **kwargs):
        extract_calls.append(kwargs)
        return [
            ExtractResult(
                url="https://example.com/a",
                content=long_content,
                status="success",
                images=["https://example.com/tavily.png"],
            )
        ]

    monkeypatch.setattr(deepsearch_service, "extract_tavily", fake_extract)

    result = deepsearch_service.run_deepsearch_and_crawl(
        query="璁＄畻鎬濈淮",
        owner="teacher-a",
        depth="full",
        save_to_kb=False,
    )

    assert result["ok"] is True
    assert extract_calls[0]["depth"] == "advanced"
    assert result["results"][0]["content"].startswith(long_content.strip())
    assert len(result["results"][0]["content"]) > 2000
    assert result["results"][0]["metadata"]["images"] == [
        "https://example.com/tavily.png",
        "https://example.com/bocha.png",
    ]
    assert "![Image 1](https://example.com/tavily.png)" in result["results"][0]["content"]


def test_run_deepsearch_localizes_preview_images_before_return(monkeypatch, tmp_path):
    monkeypatch.setattr(
        deepsearch_service,
        "search_bocha",
        lambda *args, **kwargs: [
            WebSearchHit(
                url="https://example.com/a",
                title="Example A",
                content="Bocha summary A",
                images=["https://cdn.example.com/bocha.png"],
                site="Example",
            )
        ],
    )
    monkeypatch.setattr(
        deepsearch_service,
        "extract_tavily",
        lambda *args, **kwargs: [
            ExtractResult(
                url="https://example.com/a",
                content="Article body",
                status="success",
                images=["https://cdn.example.com/tavily.png"],
            )
        ],
    )

    class FakeLocalizedAsset:
        def __init__(self, source_url):
            suffix = "tavily" if "tavily" in source_url else "bocha"
            self.local_url = f"/api/images/searched/{suffix}.png"
            self.local_path = tmp_path / f"{suffix}.png"
            self.source_url = source_url

    def fake_localize(asset, **kwargs):
        return FakeLocalizedAsset(asset["url"])

    monkeypatch.setattr(deepsearch_service, "localize_image", fake_localize)

    result = deepsearch_service.run_deepsearch_and_crawl(
        query="image preview",
        owner="teacher-a",
        depth="full",
        save_to_kb=False,
    )

    first = result["results"][0]
    assert first["metadata"]["images"] == [
        "/api/images/searched/tavily.png",
        "/api/images/searched/bocha.png",
    ]
    assert "https://cdn.example.com/tavily.png" not in first["content"]
    assert "![Image 1](/api/images/searched/tavily.png)" in first["content"]
    assert first["metadata"]["image_assets"] == [
        {
            "file_path": str(tmp_path / "tavily.png"),
            "source_url": "/api/images/searched/tavily.png",
            "original_url": "https://cdn.example.com/tavily.png",
        },
        {
            "file_path": str(tmp_path / "bocha.png"),
            "source_url": "/api/images/searched/bocha.png",
            "original_url": "https://cdn.example.com/bocha.png",
        },
    ]
