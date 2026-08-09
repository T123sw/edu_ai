from types import SimpleNamespace

from app.chat.runtime.research.builder import build_research_bundle


def test_research_bundle_reuses_successful_rag_and_web_evidence():
    ctx = SimpleNamespace(
        capability=SimpleNamespace(source_mode="selected_documents", selected_doc_ids=["doc-1"]),
        _call_cache={
            'rag_search:{"query":"快速排序"}': {
                "ok": True,
                "payload": {"answer": "课程讲义：快速排序使用分治。", "sources": [{"document_id": "doc-1", "title": "讲义"}]},
            },
            'web_search:{"query":"快速排序"}': {
                "ok": True,
                "payload": {"summary": "网络资料：平均复杂度 O(n log n)。", "sources": [{"url": "https://example.com/q", "title": "Web"}]},
            },
        },
    )

    first = build_research_bundle(ctx, topic="快速排序")
    second = build_research_bundle(ctx, topic="快速排序")

    assert first.bundle_id == second.bundle_id
    assert first.source_mode == "selected_documents"
    assert len(first.course_evidence) == 1
    assert len(first.web_evidence) == 1
    assert "快速排序使用分治" in first.context_text


def test_research_bundle_deduplicates_sources_and_records_coverage():
    ctx = SimpleNamespace(
        capability=SimpleNamespace(source_mode="course_auto", selected_doc_ids=[]),
        task_contract={
            "intent": "generate_single",
            "topic": "快速排序",
            "resource_types": ["report"],
            "source_mode": "course_auto",
        },
        _call_cache={
            'rag_search:{"query":"快速排序"}': {
                "ok": True,
                "payload": {
                    "query": "快速排序",
                    "answer": "快速排序使用分治法，并可设计课堂活动和学习目标。",
                    "sources": [
                        {"document_id": "doc-1", "chunk_id": "chunk-1", "title": "讲义"},
                        {"document_id": "doc-1", "chunk_id": "chunk-1", "title": "讲义"},
                    ],
                },
            },
        },
    )

    bundle = build_research_bundle(ctx, topic="快速排序")

    assert len(bundle.citations) == 1
    assert bundle.coverage.coverage_ratio >= 0.5
    assert "misconception" in bundle.coverage.missing_aspects
    assert bundle.coverage.next_query
