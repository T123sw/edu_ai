from app.services.course_knowledge_planner import preview_course_knowledge_plan


def _leaf_nodes(node):
    children = node.get("children") or []
    if not children:
        return [node]
    result = []
    for child in children:
        result.extend(_leaf_nodes(child))
    return result


def test_plan_builds_semantic_three_level_graph_and_searches_chinese_first():
    calls = []

    def search(query: str, count: int):
        calls.append(query)
        if "lang:zh-CN" in query:
            return [{
                "title": "Python 条件语句",
                "url": "https://zh.wikibooks.org/wiki/Python/条件语句",
                "content": "条件判断 if elif else",
            }]
        return [{
            "title": "Python compound statements",
            "url": "https://docs.python.org/3/reference/compound_stmts.html",
            "content": "if statement and loops",
        }]

    plan = preview_course_knowledge_plan(
        {
            "id": "python-control",
            "title": "Python 控制流程入门",
            "objectives": ["条件判断", "循环控制"],
            "language": "zh-CN",
        },
        search_provider=search,
    )

    graph = plan.graph_draft
    assert graph["label"] == "Python 控制流程入门课程知识图谱"
    assert len(graph["children"]) == 1
    assert graph["children"][0]["label"] == "Python 控制流程"
    assert [node["label"] for node in _leaf_nodes(graph)] == ["条件判断", "循环控制"]
    assert all(node["data"]["level"] == 2 for node in _leaf_nodes(graph))
    assert "lang:zh-CN" in calls[0]
    approved = [candidate for candidate in plan.source_candidates if candidate.selected]
    assert all(
        sum(candidate.topic_id == topic.topic_id for candidate in approved) >= 3
        for topic in plan.topics
    )
    assert any(
        candidate.metadata.get("acquisition_stage") == "curated_chinese"
        for candidate in approved
    )


def test_python_plan_uses_three_official_chinese_sources_per_leaf_before_ai_fallback():
    plan = preview_course_knowledge_plan(
        {
            "id": "python-control",
            "title": "Python 控制流程入门",
            "description": "学习 Python 条件判断与循环控制",
            "objectives": ["条件判断", "循环控制"],
            "language": "zh-CN",
        },
        search_provider=lambda _query, _count: [{
            "title": "无法确认授权的搜索结果",
            "url": "https://example.com/python-control",
            "content": "Python 条件判断 循环控制",
        }],
    )

    for topic in plan.topics:
        approved = [
            candidate
            for candidate in plan.source_candidates
            if candidate.topic_id == topic.topic_id and candidate.selected
        ]
        assert len(approved) >= 3
        assert any(candidate.domain == "docs.python.org" for candidate in approved)
    assert any(
        candidate.domain == "example.com" and candidate.selected
        for candidate in plan.source_candidates
    )


def test_plan_uses_course_semantics_not_course_id_for_topics_and_sources():
    course = {
        "id": "course-1720000000000",
        "title": "线性代数",
        "description": "工程数学基础",
        "audience": "大学一年级",
        "objectives": ["理解向量空间", "掌握矩阵分解"],
        "language": "zh-CN",
        "difficulty": "intermediate",
    }

    def search(query: str, count: int):
        assert "线性代数" in query
        assert count == 6
        return [{
            "title": "向量空间 - 维基百科",
            "url": "https://zh.wikipedia.org/wiki/向量空间",
            "content": "向量空间是线性代数的基本结构",
        }]

    plan = preview_course_knowledge_plan(course, search_provider=search)

    assert [topic.title for topic in plan.topics] == ["理解向量空间", "掌握矩阵分解"]
    assert plan.source_candidates[0].review_status == "relevant"
    assert plan.source_candidates[0].license_name == "CC BY-SA 4.0"
    assert plan.source_candidates[0].selected is True


def test_plan_accepts_relevant_https_source_without_license_metadata():
    plan = preview_course_knowledge_plan(
        {"id": "modern-history", "title": "现代史", "objectives": ["理解工业化"]},
        search_provider=lambda _query, _count: [{
            "title": "工业化文章",
            "url": "https://example.com/article",
            "content": "工业化",
        }],
    )

    candidate = plan.source_candidates[0]
    assert candidate.review_status == "relevant"
    assert candidate.selected is True
    assert candidate.license_name is None
    assert "相关" in candidate.review_reason


def test_plan_deduplicates_same_search_url_across_leaf_topics():
    plan = preview_course_knowledge_plan(
        {
            "id": "python-control",
            "title": "Python 控制流程入门",
            "objectives": ["条件判断", "循环控制"],
        },
        search_provider=lambda _query, _count: [{
            "title": "Python 控制流程",
            "url": "https://docs.python.org/3/tutorial/controlflow.html",
            "content": "条件判断 循环控制 if for while",
        }],
    )

    urls = [candidate.url for candidate in plan.source_candidates]
    assert len(urls) == len(set(urls))
