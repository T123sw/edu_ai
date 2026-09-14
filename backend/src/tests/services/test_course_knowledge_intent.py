from __future__ import annotations

from app.services.course_knowledge_intent import compile_knowledge_build_intent


def _course():
    return {
        "title": "操作系统",
        "description": "面向计算机专业学生的 8 课时课程",
        "audience": "掌握 C 语言和数据结构的计算机专业大二学生",
        "difficulty": "intermediate",
        "language": "zh-CN",
        "objectives": ["解释进程与线程", "分析资源隔离机制"],
    }


def test_compiler_preserves_audience_depth_sources_and_deliverables():
    intent = compile_knowledge_build_intent(
        course=_course(),
        baseline_graph={"id": "root", "children": []},
        requirements=(
            "本次新增知识点“Linux cgroups 与容器资源隔离”\n"
            "补充内容：CPU、内存和 I/O 资源限制机制，1 个 Docker 配置案例，3 道带解析练习\n"
            "保留范围：保留现有目录和全部已有资料，不修改其他章节\n"
            "资料偏好：优先检索 Linux Kernel 与 Docker 官方资料，资料不足时允许 AI 补充"
        ),
    )

    assert intent.mode == "supplement"
    assert intent.course_profile.audience == _course()["audience"]
    assert intent.course_profile.prerequisites == ["C 语言", "数据结构"]
    assert intent.course_profile.duration_lessons == 8
    assert intent.course_profile.difficulty == "intermediate"
    assert intent.scope.include_topics == ["Linux cgroups 与容器资源隔离"]
    assert intent.scope.preserve_existing_graph is True
    assert intent.scope.preserve_existing_documents is True
    assert intent.source_policy.preferred_organizations == ["Docker", "Linux Kernel"]
    assert intent.source_policy.preferred_domains == ["docs.docker.com", "docs.kernel.org"]
    assert intent.source_policy.allow_ai_fallback is True
    deliverables = {item.type: item for item in intent.deliverables}
    assert deliverables["worked_case"].count == 1
    assert deliverables["exercise_with_solution"].count == 3
    assert deliverables["exercise_with_solution"].hardness == "hard"
    assert not intent.clarification_questions


def test_compiler_preserves_generic_university_and_open_textbook_preferences():
    intent = compile_knowledge_build_intent(
        course=_course(),
        baseline_graph=None,
        requirements=(
            "共 8 课时，达到本科基础到应用深度；"
            "优先使用大学课程和公认开放教材，资料不足时允许 AI 基于权威来源补充。"
        ),
    )

    assert intent.source_policy.preferred_organizations == ["公认开放教材", "大学课程"]
    assert intent.source_policy.minimum_authoritative_sources_per_topic == 1
    assert intent.source_policy.allow_ai_fallback is True
    source_requirement = next(item for item in intent.requirements if item.kind == "source")
    assert source_requirement.hardness == "preference"


def test_compiler_distinguishes_required_sources_from_preferences():
    intent = compile_knowledge_build_intent(
        course=_course(),
        baseline_graph=None,
        requirements="只允许使用 docs.kernel.org 和 docs.docker.com 的资料，不要社区博客。",
    )

    assert intent.mode == "create"
    assert intent.source_policy.required_domains == ["docs.docker.com", "docs.kernel.org"]
    assert intent.source_policy.preferred_domains == []
    assert intent.source_policy.allow_community_fallback is False
    source_requirements = [item for item in intent.requirements if item.kind == "source"]
    assert source_requirements
    assert all(item.hardness == "hard" for item in source_requirements)


def test_compiler_flags_vague_source_and_depth_requests_for_clarification():
    intent = compile_knowledge_build_intent(
        course={"title": "操作系统"},
        baseline_graph=None,
        requirements="内容讲深一点，资料质量要好一些。",
    )

    assert intent.status == "needs_clarification"
    assert len(intent.clarification_questions) == 2
    assert any("深度" in item for item in intent.clarification_questions)
    assert any("来源" in item for item in intent.clarification_questions)


def test_compiler_requirement_ids_are_stable():
    first = compile_knowledge_build_intent(
        course=_course(), baseline_graph=None, requirements="至少提供 3 道带解析练习"
    )
    second = compile_knowledge_build_intent(
        course=_course(), baseline_graph=None, requirements="至少提供 3 道带解析练习"
    )

    assert [item.requirement_id for item in first.requirements] == [
        item.requirement_id for item in second.requirements
    ]


def test_compiler_preserves_explicit_exclusions():
    intent = compile_knowledge_build_intent(
        course=_course(), baseline_graph=None, requirements="暂不涉及分布式操作系统和形式化验证。"
    )

    assert intent.scope.exclude_topics == ["分布式操作系统和形式化验证"]


def test_compiler_accepts_chinese_single_quotes_around_incremental_topic():
    intent = compile_knowledge_build_intent(
        course=_course(),
        baseline_graph={"id": "root", "children": []},
        requirements="新增知识点‘Linux cgroups 与容器资源隔离’。",
    )

    assert intent.scope.include_topics == ["Linux cgroups 与容器资源隔离"]


def test_compiler_treats_unquoted_core_scope_list_as_hard_contract():
    intent = compile_knowledge_build_intent(
        course=_course(),
        baseline_graph=None,
        requirements=(
            "核心范围（三档方案必须保留相同的核心知识点）："
            "进程与线程、CPU 调度、进程同步、死锁、虚拟内存。"
        ),
    )

    assert intent.scope.include_topics == [
        "进程与线程",
        "CPU 调度",
        "进程同步",
        "死锁",
        "虚拟内存",
    ]
    scope_requirements = [item for item in intent.requirements if item.kind == "scope"]
    assert len(scope_requirements) == 1
    assert scope_requirements[0].hardness == "hard"


def test_compiler_extracts_scope_from_course_description_covering_sentence():
    intent = compile_knowledge_build_intent(
        course=_course(),
        baseline_graph=None,
        requirements=(
            "课程简介：面向大二学生，共 8 课时，覆盖进程与线程、CPU 调度、"
            "进程同步、死锁和虚拟内存；课程目标：理解操作系统核心机制。"
        ),
    )

    assert intent.scope.include_topics == [
        "进程与线程",
        "CPU 调度",
        "进程同步",
        "死锁",
        "虚拟内存",
    ]


def test_compiler_separates_scope_depth_and_per_topic_artifacts():
    intent = compile_knowledge_build_intent(
        course=_course(),
        baseline_graph=None,
        requirements=(
            "共 8 课时，覆盖进程与线程、CPU 调度、进程同步、死锁和虚拟内存，"
            "达到本科基础到应用深度；优先使用大学课程和公认开放教材，"
            "资料不足时允许 AI 基于权威来源补充；"
            "每个主题需要机制讲解、可验证例子、练习和实验建议。"
        ),
    )

    assert intent.scope.include_topics == [
        "进程与线程", "CPU 调度", "进程同步", "死锁", "虚拟内存",
    ]
    assert {item.type for item in intent.deliverables} == {
        "concept_explanation", "worked_case", "exercise_with_solution", "lab",
    }
    assert all(item.application == "topic" for item in intent.deliverables)


def test_compiler_does_not_treat_coverage_density_as_a_topic():
    intent = compile_knowledge_build_intent(
        course=_course(), baseline_graph=None,
        requirements="三档方案的差别体现在讲解深度与覆盖密度，不体现在模块数量上。",
    )

    assert intent.scope.include_topics == []
