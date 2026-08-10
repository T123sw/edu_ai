from app.services.course_knowledge_planner import preview_course_knowledge_plan


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
    assert plan.source_candidates[0].review_status == "approved"
    assert plan.source_candidates[0].license_name == "CC BY-SA 4.0"
    assert plan.source_candidates[0].selected is True


def test_plan_rejects_unknown_license_and_keeps_audit_reason():
    plan = preview_course_knowledge_plan(
        {"id": "modern-history", "title": "现代史", "objectives": ["理解工业化"]},
        search_provider=lambda _query, _count: [{
            "title": "工业化文章",
            "url": "https://example.com/article",
            "content": "工业化",
        }],
    )

    candidate = plan.source_candidates[0]
    assert candidate.review_status == "rejected"
    assert candidate.selected is False
    assert "许可" in candidate.review_reason
