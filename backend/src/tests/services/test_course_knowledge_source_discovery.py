from __future__ import annotations

from app.integrations.websearch.models import WebSearchHit
from app.services.course_knowledge_source_discovery import (
    canonical_source_url,
    discover_course_knowledge_sources,
    discover_course_textbook_sources,
    discover_leaf_gap_sources,
)
from app.services.course_knowledge_source_policy import build_leaf_source_queries


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


def test_course_textbook_discovery_uses_course_scope_and_prioritizes_pdf():
    calls = []

    def search(query, limit):
        calls.append((query, limit))
        return [
            WebSearchHit(
                url="https://blog.example.com/linked-list",
                title="数据结构中的链表",
                content="介绍链表节点的短文章",
            ),
            WebSearchHit(
                url="https://university.example.edu/data-structures.pdf",
                title="数据结构完整教材 PDF",
                content="含目录，覆盖线性表、树、图和排序章节",
            ),
        ]

    build = _build(2)
    build["config"]["max_online_textbooks"] = 1
    result = discover_course_textbook_sources(build, search_provider=search)

    selected = [item for item in result["source_candidates"] if item["selected"]]
    assert len(calls) == 1
    assert len(selected) == 1
    assert selected[0]["topic_id"] is None
    assert selected[0]["url"] == "https://university.example.edu/data-structures.pdf"
    assert selected[0]["metadata"]["discovery_scope"] == "course"
    assert result["metrics"]["selected_textbook_count"] == 1


def test_course_textbook_discovery_rejects_community_downloads():
    def search(_query, _limit):
        return [
            WebSearchHit(
                url="https://blog.csdn.net/example/data-structures.pdf",
                title="数据结构完整课程讲义 PDF",
                content="含线性表、树、图和排序章节",
            )
        ]

    build = _build(1)
    result = discover_course_textbook_sources(build, search_provider=search)

    assert not any(item["selected"] for item in result["source_candidates"])
    assert all(
        "高校、政府或已知官方" in item["review_reason"]
        for item in result["source_candidates"]
    )


def test_operating_system_discovery_keeps_curated_complete_sources_ahead_of_fragments():
    def search(_query, _limit):
        return [
            WebSearchHit(
                url="https://pages.cs.wisc.edu/~remzi/OSTEP/preface.pdf",
                title="[PDF] Preface",
                content="Preface for the operating systems book",
            )
        ]

    build = _build(1)
    build["course_snapshot"]["title"] = "操作系统"
    build["config"]["max_online_textbooks"] = 2
    result = discover_course_textbook_sources(build, search_provider=search)
    selected_urls = {item["url"] for item in result["source_candidates"] if item["selected"]}

    assert selected_urls == {
        "https://pdos.csail.mit.edu/6.828/2023/xv6/book-riscv-rev3.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/",
    }
    ostep = next(
        item for item in result["source_candidates"]
        if item["url"] == "https://pages.cs.wisc.edu/~remzi/OSTEP/"
    )
    assert ostep["metadata"]["linked_chapter_urls"] == [
        "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-intro.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-api.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-mechanisms.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched-mlfq.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-intro.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-cv.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-sema.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-bugs.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-intro.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-api.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-paging.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-beyondphys.pdf",
        "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-beyondphys-policy.pdf",
    ]


def test_gap_discovery_only_searches_requested_leaves_and_advances_query_intent():
    calls = []

    def search(query, limit):
        calls.append((query, limit))
        return [
            WebSearchHit(
                url=f"https://example.org/{len(calls)}",
                title="链表概念 1 例题讲解",
                content="链表节点与指针的例题和课程讲解",
            )
        ]

    build = _build(2)
    first = discover_leaf_gap_sources(
        build,
        topic_ids={"leaf-1"},
        round_index=0,
        search_provider=search,
    )
    second = discover_leaf_gap_sources(
        build,
        topic_ids={"leaf-1"},
        round_index=1,
        search_provider=search,
    )

    assert len(calls) == 2
    assert "教程" in calls[0][0]
    assert "例题" in calls[1][0]
    assert calls[0][0].startswith("site:edu.cn")
    assert calls[1][0].startswith("site:edu.cn")
    assert all(item["topic_id"] == "leaf-1" for item in first["source_candidates"])
    assert all(item["topic_id"] == "leaf-1" for item in second["source_candidates"])
    assert first["metrics"]["searched_leaf_count"] == 1
    assert first["source_candidates"][0]["metadata"]["search_round"] == 1


def test_gap_discovery_deduplicates_url_without_losing_matched_leaf_ids():
    def search(_query, _limit):
        return [
            WebSearchHit(
                url="https://example.org/shared-course-page?utm_source=bocha",
                title="链表概念 0 与链表概念 1",
                content="链表节点、指针、定义和例题",
            )
        ]

    result = discover_leaf_gap_sources(
        _build(2),
        topic_ids={"leaf-0", "leaf-1"},
        round_index=0,
        search_provider=search,
    )

    assert len(result["source_candidates"]) == 1
    candidate = result["source_candidates"][0]
    assert candidate["url"] == "https://example.org/shared-course-page"
    assert set(candidate["metadata"]["matched_topic_ids"]) == {"leaf-0", "leaf-1"}


def test_leaf_queries_consume_audience_depth_sources_and_requested_artifacts():
    topic = {
        "title": "Linux cgroups 与容器资源隔离",
        "objective": "分析 CPU、内存和 I/O 资源限制",
        "graph_path": "操作系统 / 资源管理",
        "audience": "掌握 C 语言的计算机专业大二学生",
        "depth_profile": {"conceptual_rigor": "进阶", "example_complexity": "可执行并可验证"},
        "requested_materials": "Docker 配置案例",
        "deliverables": [{"type": "exercise_with_solution", "count": 3}],
        "source_policy": {
            "preferred_domains": ["docs.kernel.org", "docs.docker.com"],
        },
    }

    queries = build_leaf_source_queries(
        {"title": "操作系统"}, topic, content_language="zh-CN"
    )

    assert queries[0].query.startswith("site:docs.kernel.org")
    assert queries[1].query.startswith("site:docs.docker.com")
    assert "cgroup v2" in queries[0].query
    assert "resource constraints" in queries[1].query
    assert "Docker 配置案例" in queries[2].query
    assert "答案 解析" in queries[2].query
    assert "计算机专业大二学生" in queries[2].query
    assert "进阶" in queries[2].query


def test_required_source_domains_reject_other_domains_during_discovery():
    build = _build(1)
    build["intent_contract"] = {
        "source_policy": {
            "required_domains": ["docs.kernel.org"],
            "minimum_authoritative_sources_per_topic": 1,
        }
    }

    def search(_query, _limit):
        return [
            WebSearchHit(
                url="https://community.example.com/linked-list",
                title="链表概念 0 教程",
                content="链表节点与指针",
            ),
            WebSearchHit(
                url="https://docs.kernel.org/linked-list.html",
                title="链表概念 0 官方教程",
                content="链表节点与指针",
            ),
        ]

    result = discover_course_knowledge_sources(build, search_provider=search)
    by_domain = {item["domain"]: item for item in result["source_candidates"]}

    assert by_domain["community.example.com"]["selected"] is False
    assert "必选域名" in by_domain["community.example.com"]["review_reason"]
    assert by_domain["docs.kernel.org"]["selected"] is True
    assert by_domain["docs.kernel.org"]["authority_tier"] == "teacher_required_source"
