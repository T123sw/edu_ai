from __future__ import annotations

from app.integrations.websearch.models import WebSearchHit
from app.services.course_knowledge_source_discovery import (
    canonical_source_url,
    discover_course_knowledge_sources,
)


def _build(leaf_count=7):
    return {
        "course_snapshot": {"title": "数据结构", "audience": "大学一年级"},
        "config": {"content_language": "zh-CN", "max_search_results_per_leaf": 1},
        "graph_draft": {
            "id": "root",
            "label": "数据结构",
            "data": {"type": "course", "summary": "课程"},
            "children": [
                {
                    "id": "module",
                    "label": "核心结构",
                    "data": {"type": "knowledge_module", "summary": "模块"},
                    "children": [
                        {
                            "id": f"leaf-{index}",
                            "label": f"链表概念 {index}",
                            "data": {"type": "knowledge_point", "summary": "理解链表节点与指针"},
                            "children": [],
                        }
                        for index in range(leaf_count)
                    ],
                }
            ],
        },
    }


def test_discovery_searches_every_confirmed_leaf_and_accepts_unknown_license():
    calls = []

    def search(query, limit):
        calls.append((query, limit))
        index = query.split("链表概念 ", 1)[1].split(" ", 1)[0]
        return [
            WebSearchHit(
                url=f"https://learning.example.org/linked-list-{index}?utm_source=test",
                title=f"链表概念 {index} 教程",
                content="链表节点与指针的课程讲解",
            )
        ]

    result = discover_course_knowledge_sources(_build(), search_provider=search)

    assert len(calls) == 7
    assert result["metrics"]["leaf_count"] == 7
    assert result["metrics"]["selected_candidate_count"] == 7
    assert all(item["review_status"] == "relevant" for item in result["source_candidates"])
    assert all(item["license_name"] is None for item in result["source_candidates"])
    assert all(item["selected"] is True for item in result["source_candidates"])


def test_discovery_isolates_search_error_and_rejects_non_https():
    call_count = 0

    def search(query, _limit):
        nonlocal call_count
        call_count += 1
        if "链表概念 0" in query:
            raise RuntimeError("provider unavailable")
        return [WebSearchHit(url="http://example.org/page", title="链表概念", content="链表节点")]

    result = discover_course_knowledge_sources(_build(2), search_provider=search)

    assert call_count == 4
    assert result["metrics"]["search_failure_count"] == 2
    assert all(item["selected"] is False for item in result["source_candidates"])
    assert all(item["review_status"] == "rejected_irrelevant" for item in result["source_candidates"])


def test_discovery_deduplicates_canonical_urls_across_queries_and_leaves():
    def search(_query, _limit):
        return [
            WebSearchHit(
                url="https://Example.org/course/?b=2&utm_campaign=x&a=1#chapter",
                title="链表概念与节点",
                content="链表节点与指针",
            )
        ]

    result = discover_course_knowledge_sources(_build(2), search_provider=search)

    selected = [item for item in result["source_candidates"] if item["selected"]]
    assert len(selected) == 1
    assert selected[0]["url"] == "https://example.org/course?a=1&b=2"
    assert canonical_source_url("javascript:alert(1)") == ""


def test_later_relevant_mapping_replaces_earlier_irrelevant_duplicate():
    def search(query, _limit):
        relevant = "链表概念 1" in query
        return [
            WebSearchHit(
                url="https://example.org/shared",
                title="链表概念 1" if relevant else "无关页面",
                content="链表节点与指针" if relevant else "天气预报",
            )
        ]

    result = discover_course_knowledge_sources(_build(2), search_provider=search)

    assert len(result["source_candidates"]) == 1
    candidate = result["source_candidates"][0]
    assert candidate["topic_id"] == "leaf-1"
    assert candidate["review_status"] == "relevant"
    assert candidate["selected"] is True
