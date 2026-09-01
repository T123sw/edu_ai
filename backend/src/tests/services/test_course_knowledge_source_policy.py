from __future__ import annotations

from app.services.course_knowledge_source_policy import (
    SourceQueryIntent,
    build_course_source_queries,
    classify_source_candidate,
    rank_source_candidates,
)


def test_course_queries_put_complete_pdf_textbooks_before_general_resources():
    queries = build_course_source_queries(
        {"title": "数据结构", "audience": "大学一年级"},
        content_language="zh-CN",
    )

    assert [item.intent for item in queries[:3]] == [
        "complete_textbook_pdf",
        "course_notes_pdf",
        "complete_textbook_html",
    ]
    assert queries[0].discovery_scope == "course"
    assert "数据结构" in queries[0].query
    assert "filetype:pdf" in queries[0].query
    assert any(item.language == "en" for item in queries)


def test_related_pdf_textbook_ranks_before_fragment_page_but_unrelated_pdf_is_rejected():
    intent = SourceQueryIntent(
        query="数据结构 完整教材 PDF filetype:pdf",
        language="zh-CN",
        discovery_scope="course",
        intent="complete_textbook_pdf",
    )
    textbook = classify_source_candidate(
        intent=intent,
        course={"title": "数据结构", "audience": "大学一年级"},
        title="数据结构完整教材（含目录与章节）PDF",
        snippet="覆盖线性表、树、图、排序与算法分析的课程教材",
        url="https://university.example.edu/books/data-structures.pdf",
        bocha_rank=2,
    )
    fragment = classify_source_candidate(
        intent=intent,
        course={"title": "数据结构", "audience": "大学一年级"},
        title="数据结构中的栈是什么",
        snippet="一篇介绍栈的短教程",
        url="https://blog.example.com/stack.html",
        bocha_rank=1,
    )
    unrelated = classify_source_candidate(
        intent=intent,
        course={"title": "数据结构", "audience": "大学一年级"},
        title="世界历史完整教材 PDF",
        snippet="古代文明与近代历史",
        url="https://example.edu/history.pdf",
        bocha_rank=1,
    )

    ranked = rank_source_candidates([fragment, textbook, unrelated])

    assert textbook["metadata"]["resource_kind"] == "textbook"
    assert textbook["metadata"]["content_format_hint"] == "pdf"
    assert textbook["selected"] is True
    assert ranked[0]["url"] == textbook["url"]
    assert unrelated["selected"] is False
    assert unrelated["review_status"] == "rejected_irrelevant"

