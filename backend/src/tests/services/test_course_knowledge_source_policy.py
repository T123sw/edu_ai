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


def test_operating_system_queries_start_with_curated_authoritative_courses():
    queries = build_course_source_queries(
        {"title": "操作系统", "audience": "计算机专业大二学生"},
        content_language="zh-CN",
    )

    assert "pdos.csail.mit.edu" in queries[0].query
    assert "pages.cs.wisc.edu" in queries[1].query
    assert "cs.nju.edu.cn" in queries[2].query


def test_chinese_operating_system_course_accepts_english_authoritative_textbook():
    intent = SourceQueryIntent(
        query="site:pdos.csail.mit.edu xv6 teaching operating system book PDF",
        language="en",
        discovery_scope="course",
        intent="complete_textbook_pdf",
    )
    candidate = classify_source_candidate(
        intent=intent,
        course={"title": "操作系统"},
        title="xv6: a simple Unix-like teaching operating system",
        snippet="A book and source code for an operating systems course.",
        url="https://pdos.csail.mit.edu/6.828/2023/xv6/book-riscv-rev3.pdf",
        bocha_rank=1,
    )

    assert candidate["selected"] is True
    assert candidate["authority_tier"] == "authoritative_source"


def test_pdf_query_does_not_mislabel_html_result_as_pdf():
    intent = SourceQueryIntent(
        query="site:pdos.csail.mit.edu xv6 book PDF",
        language="en",
        discovery_scope="course",
        intent="complete_textbook_pdf",
    )
    candidate = classify_source_candidate(
        intent=intent,
        course={"title": "操作系统"},
        title="Xv6 teaching operating system",
        snippet="The online home page for the xv6 book.",
        url="https://pdos.csail.mit.edu/6.828/2023/xv6/",
        bocha_rank=1,
    )

    assert candidate["metadata"]["content_format_hint"] == "html"


def test_low_quality_document_marketplace_is_rejected_before_fetch():
    intent = SourceQueryIntent(
        query="操作系统 进程同步 教程",
        language="zh-CN",
        discovery_scope="leaf",
        intent="leaf_explanation",
    )
    candidate = classify_source_candidate(
        intent=intent,
        course={"title": "操作系统"},
        topic={"title": "进程同步", "objective": "理解信号量"},
        title="操作系统进程同步完整答案 - 原创力文档",
        snippet="进程同步与信号量课程资料下载",
        url="https://max.book118.com/html/example.html",
        bocha_rank=1,
    )

    assert candidate["selected"] is False
    assert candidate["metadata"]["low_quality_source"] is True
    assert "低质量" in candidate["review_reason"]


def test_authoritative_but_topic_irrelevant_result_is_rejected():
    intent = SourceQueryIntent(
        query="site:edu.cn 操作系统 进程状态",
        language="zh-CN",
        discovery_scope="leaf",
        intent="leaf_explanation",
    )
    candidate = classify_source_candidate(
        intent=intent,
        course={"title": "操作系统"},
        topic={"title": "进程状态与转换", "objective": "理解就绪、运行和阻塞状态"},
        title="线性代数课程简介",
        snippet="矩阵、行列式与向量空间",
        url="https://math.example.edu.cn/linear-algebra",
        bocha_rank=1,
    )

    assert candidate["authority_tier"] == "authoritative_source"
    assert candidate["metadata"]["topic_relevance"] == 0
    assert candidate["selected"] is False


def test_university_news_page_is_not_instructional_evidence():
    intent = SourceQueryIntent(
        query="site:edu.cn 操作系统 FCFS SJF 调度",
        language="zh-CN",
        discovery_scope="leaf",
        intent="leaf_explanation",
    )
    candidate = classify_source_candidate(
        intent=intent,
        course={"title": "操作系统"},
        topic={"title": "FCFS 与 SJF 调度", "objective": "计算平均等待时间"},
        title="学院成功举办2025年度新教师讲课比赛",
        snippet="参赛教师讲解 FCFS 和 SJF 调度算法",
        url="https://cs.example.edu.cn/news/teacher-contest.html",
        bocha_rank=1,
    )

    assert candidate["authority_tier"] == "authoritative_source"
    assert candidate["selected"] is False
    assert candidate["metadata"]["non_instructional"] is True


def test_official_release_archive_is_not_instructional_evidence():
    intent = SourceQueryIntent(
        query="site:docs.docker.com container resource constraints --cpus --memory block IO official documentation guide",
        language="en",
        discovery_scope="leaf",
        intent="leaf_examples",
    )
    candidate = classify_source_candidate(
        intent=intent,
        course={"title": "操作系统"},
        topic={
            "title": "Linux cgroups 与容器资源隔离",
            "objective": "理解 CPU、内存与 I/O 资源限制",
            "source_policy": {"preferred_domains": ["docs.docker.com"]},
        },
        title="Docker Engine Prior Releases | Docker Docs",
        snippet="Archive navigation that incidentally contains resource-related links.",
        url="https://docs.docker.com/engine/release-notes/prior-releases/",
        bocha_rank=1,
    )

    assert candidate["selected"] is False
    assert candidate["metadata"]["non_instructional"] is True
    assert "知识点正文" in candidate["review_reason"]


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


def test_exact_preferred_document_ranks_ahead_of_broad_same_domain_page():
    intent = SourceQueryIntent(
        query="site:docs.kernel.org cgroup v2 cpu.max memory.max io.max official documentation guide",
        language="en",
        discovery_scope="leaf",
        intent="leaf_examples",
    )
    topic = {
        "title": "Linux cgroups 与容器资源隔离",
        "objective": "理解 CPU、内存与 I/O 资源限制",
        "source_policy": {"preferred_domains": ["docs.kernel.org"]},
    }
    exact = classify_source_candidate(
        intent=intent,
        course={"title": "操作系统"},
        topic=topic,
        title="Control Group v2",
        snippet="The cpu.max, memory.max and io.max files control cgroup resources.",
        url="https://docs.kernel.org/admin-guide/cgroup-v2.html",
        bocha_rank=3,
    )
    broad = classify_source_candidate(
        intent=intent,
        course={"title": "操作系统"},
        topic=topic,
        title="The kernel's command-line parameters",
        snippet="A broad list of kernel parameters including one cgroup option.",
        url="https://docs.kernel.org/admin-guide/kernel-parameters.html",
        bocha_rank=1,
    )

    ranked = rank_source_candidates([broad, exact])

    assert exact["metadata"]["query_focus_score"] > broad["metadata"]["query_focus_score"]
    assert ranked[0]["url"] == exact["url"]
    assert broad["selected"] is False
    assert "标题与路径" in broad["review_reason"]


def test_preferred_domain_rejects_tangential_docker_build_page():
    intent = SourceQueryIntent(
        query="site:docs.docker.com container resource constraints --cpus --memory block IO official documentation guide",
        language="en",
        discovery_scope="leaf",
        intent="leaf_examples",
    )
    candidate = classify_source_candidate(
        intent=intent,
        course={"title": "操作系统"},
        topic={
            "title": "Linux cgroups 与容器资源隔离",
            "objective": "理解 CPU、内存与 I/O 资源限制",
            "source_policy": {"preferred_domains": ["docs.docker.com"]},
        },
        title="docker buildx build",
        snippet="Build options can incidentally mention CPU and memory resources.",
        url="https://docs.docker.com/reference/cli/docker/buildx/build",
        bocha_rank=1,
    )

    assert candidate["selected"] is False
    assert candidate["metadata"]["query_title_focus_score"] == 0
