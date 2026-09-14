from __future__ import annotations

from app.integrations.websearch.models import WebSearchHit
from app.services.course_knowledge_intent import compile_knowledge_build_intent
from app.services.course_knowledge_quality_gate import evaluate_course_knowledge_quality
from app.services.course_knowledge_source_discovery import discover_course_knowledge_sources


def _operating_system_build():
    course = {
        "title": "操作系统",
        "audience": "掌握 C 语言和数据结构的计算机专业大二学生",
        "difficulty": "intermediate",
        "language": "zh-CN",
    }
    intent = compile_knowledge_build_intent(
        course=course,
        baseline_graph={"id": "existing", "children": []},
        requirements=(
            "本次新增知识点“Linux cgroups 与容器资源隔离”；覆盖 CPU、内存和 I/O 资源限制机制，"
            "提供 1 个 Docker 配置案例和 3 道带解析练习；保留现有目录和全部已有资料；"
            "优先检索 Linux Kernel 与 Docker 官方资料，资料不足时允许 AI 补充。"
        ),
    )
    return {
        "build_id": "kb-os-v2",
        "course_snapshot": course,
        "intent_contract": intent.model_dump(mode="json"),
        "selected_topic_ids": ["cgroups"],
        "config": {
            "graph_depth": 3,
            "target_module_count": 1,
            "target_points_per_module": 1,
            "target_materials_per_leaf": 3,
            "minimum_web_materials_per_leaf": 1,
            "maximum_ai_materials_per_leaf": 1,
            "content_language": "zh-CN",
            "max_search_results_per_leaf": 6,
        },
        "graph_draft": {
            "id": "root",
            "label": "操作系统",
            "data": {"type": "course", "summary": "操作系统课程"},
            "children": [{
                "id": "module",
                "label": "资源管理",
                "data": {"type": "knowledge_module", "summary": "资源隔离"},
                "children": [{
                    "id": "cgroups",
                    "label": "Linux cgroups 与容器资源隔离",
                    "data": {"type": "knowledge_point", "summary": "分析 CPU、内存和 I/O 限制"},
                    "children": [],
                }],
            }],
        },
    }


def test_operating_system_intent_controls_research_and_quality_end_to_end():
    build = _operating_system_build()
    calls = []

    def search(query, _limit):
        calls.append(query)
        return [
            WebSearchHit(
                url="https://docs.kernel.org/admin-guide/cgroup-v2.html",
                title="Linux cgroups v2 CPU memory IO resource control",
                content="Linux cgroups 与容器资源隔离的 CPU、内存和 I/O 控制说明",
            ),
            WebSearchHit(
                url="https://docs.docker.com/engine/containers/resource_constraints/",
                title="Docker resource constraints",
                content="Linux cgroups Docker CPU memory IO 配置案例",
            ),
        ]

    discovery = discover_course_knowledge_sources(build, search_provider=search)

    assert calls
    assert calls[0].startswith("site:docs.docker.com")
    assert calls[1].startswith("site:docs.kernel.org")
    assert {item["authority_tier"] for item in discovery["source_candidates"]} == {
        "teacher_preferred_source"
    }

    persisted = [
        {
            "document_id": "kernel",
            "scope_id": "cgroups",
            "source_type": "web",
            "source_url": "https://docs.kernel.org/admin-guide/cgroup-v2.html",
            "content_hash": "kernel-hash",
            "content_chars": 5000,
            "chunk_count": 4,
            "provenance_ok": True,
            "learning_artifacts": [
                {
                    "requirement_id": build["intent_contract"]["deliverables"][0]["requirement_id"],
                    "type": "worked_case",
                    "count": 1,
                },
                {
                    "requirement_id": build["intent_contract"]["deliverables"][1]["requirement_id"],
                    "type": "exercise_with_solution",
                    "count": 3,
                },
            ],
        },
        {
            "document_id": "docker",
            "scope_id": "cgroups",
            "source_type": "web",
            "source_url": "https://docs.docker.com/engine/containers/resource_constraints/",
            "content_hash": "docker-hash",
            "content_chars": 5000,
            "chunk_count": 4,
            "provenance_ok": True,
        },
        {
            "document_id": "supplement",
            "scope_id": "cgroups",
            "source_type": "model_generated",
            "content_hash": "supplement-hash",
            "content_chars": 1500,
            "chunk_count": 2,
        },
    ]
    quality = evaluate_course_knowledge_quality(build, persisted)

    assert quality["passed"] is True
    assert quality["quality_score"] == 100
    assert all(item["status"] == "passed" for item in quality["checks"])


def test_operating_system_vertical_slice_blocks_v1_false_positive():
    build = _operating_system_build()
    persisted = [
        {
            "document_id": f"community-{index}",
            "scope_id": "cgroups",
            "source_type": "web",
            "source_url": f"https://blog.example.com/cgroups/{index}",
            "content_hash": f"hash-{index}",
            "content_chars": 1500,
            "chunk_count": 2,
            "provenance_ok": True,
        }
        for index in range(3)
    ]

    quality = evaluate_course_knowledge_quality(build, persisted)
    checks = {item["check_type"]: item["status"] for item in quality["checks"]}

    assert quality["passed"] is False
    assert quality["quality_score"] <= 59
    assert checks["preferred_source_policy"] == "needs_teacher_decision"
    assert checks["intent_adherence"] == "failed"
