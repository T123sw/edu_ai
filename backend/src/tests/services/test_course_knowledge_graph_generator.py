from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.services.course_knowledge_graph_generator import (
    CourseKnowledgeGraphGenerationError,
    generate_course_knowledge_graph_draft,
    regenerate_course_knowledge_graph_module,
)


def _build(*, preset: str = "standard", textbooks=None):
    sizes = {
        "small": (3, 3),
        "standard": (4, 4),
        "large": (6, 6),
    }
    modules, points = sizes[preset]
    return {
        "build_id": "kb-1",
        "library_id": "course-1",
        "revision": 1,
        "course_snapshot": {
            "id": "course-1",
            "title": "古诗文鉴赏",
            "description": "学习诗歌意象、语言、结构和文化语境。",
            "audience": "高中一年级",
            "objectives": ["分析诗歌意象", "形成有证据的鉴赏表达"],
            "language": "zh-CN",
            "difficulty": "intermediate",
        },
        "config": {
            "preset": preset,
            "graph_depth": 3,
            "target_module_count": modules,
            "target_points_per_module": points,
            "target_materials_per_leaf": 3,
            "minimum_web_materials_per_leaf": 1,
            "maximum_ai_materials_per_leaf": 1,
            "max_search_results_per_leaf": 8,
            "ai_supplement_enabled": True,
            "content_language": "zh-CN",
            "update_strategy": "merge_rebuild",
        },
        "textbooks": list(textbooks or []),
    }


def _valid_payload(*, modules: int = 4, points: int = 4, refs=None):
    refs = list(refs or [])
    return {
        "root": {
            "id": "course-poetry",
            "label": "古诗文鉴赏知识体系",
            "type": "course",
            "summary": "面向高中生的古诗文鉴赏知识结构",
            "children": [
                {
                    "id": f"module-{module_index}",
                    "label": f"诗歌鉴赏维度{module_index}",
                    "type": "knowledge_module",
                    "summary": f"鉴赏维度 {module_index} 的核心方法",
                    "source_outline_refs": [refs[module_index - 1]]
                    if module_index <= len(refs)
                    else [],
                    "children": [
                        {
                            "id": f"point-{module_index}-{point_index}",
                            "label": f"维度{module_index}分析方法{point_index}",
                            "type": "knowledge_point",
                            "summary": f"使用证据完成维度 {module_index} 方法 {point_index} 的分析",
                            "children": [],
                        }
                        for point_index in range(1, points + 1)
                    ],
                }
                for module_index in range(1, modules + 1)
            ],
        },
        "unmapped_outline_items": [],
    }


class FakeAdapter:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.messages = []

    def complete(self, messages, *, owner_user_id):
        self.messages.append((list(messages), owner_user_id))
        payload = self.payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return json.dumps(payload, ensure_ascii=False), "fake-graph-model"


def test_graph_generation_always_calls_model_without_textbook():
    adapter = FakeAdapter(_valid_payload())

    graph = generate_course_knowledge_graph_draft(
        _build(),
        owner_user_id="teacher-1",
        model_adapter=adapter,
        now=lambda: datetime(2026, 8, 12, tzinfo=timezone.utc),
    )

    assert len(adapter.messages) == 1
    assert graph["children"][0]["label"] == "诗歌鉴赏维度1"
    assert graph["data"]["generation_model"] == "fake-graph-model"
    assert graph["data"]["prompt_version"] == "course-knowledge-graph-v1"
    assert graph["data"]["validation"]["leaf_count"] == 16


def test_incremental_generation_merges_candidate_without_changing_baseline_nodes():
    build = _build(preset="small")
    baseline = _valid_payload(modules=3, points=3)["root"]
    build["config"]["update_strategy"] = "incremental"
    build.update(
        baseline_graph=baseline,
        baseline_graph_version=4,
        current_graph_summary={"node_count": 13},
    )
    candidate = _valid_payload(modules=3, points=3)
    candidate["root"]["children"][0]["label"] = "模型试图改名"
    candidate["root"]["children"][0]["children"].append(
        {
            "id": "point-new",
            "label": "新增鉴赏方法",
            "type": "knowledge_point",
            "summary": "新增教材覆盖的方法",
            "children": [],
        }
    )
    adapter = FakeAdapter(candidate)

    graph = generate_course_knowledge_graph_draft(
        build,
        owner_user_id="teacher-1",
        model_adapter=adapter,
    )

    assert graph["children"][0]["label"] == baseline["children"][0]["label"]
    assert [item["id"] for item in graph["children"][0]["children"]][-1] == "point-new"
    assert graph["data"]["baseline_graph_version"] == 4
    prompt = "\n".join(item["content"] for item in adapter.messages[0][0])
    assert "保留全部已有节点" in prompt
    assert "不得删除、改名、移动或重排已有节点" in prompt
    assert '"current_graph": {"node_count": 13}' in prompt


def test_invalid_semantic_label_is_repaired_by_model():
    invalid = _valid_payload()
    invalid["root"]["children"][0]["children"][0]["label"] = "1"
    adapter = FakeAdapter(invalid, _valid_payload())

    graph = generate_course_knowledge_graph_draft(
        _build(), owner_user_id="teacher-1", model_adapter=adapter
    )

    assert len(adapter.messages) == 2
    repair_prompt = adapter.messages[1][0][-1]["content"]
    assert "PLACEHOLDER_LABEL" in repair_prompt
    assert graph["data"]["validation"]["status"] == "passed"


def test_scale_failure_never_returns_fallback_graph():
    undersized = _valid_payload(modules=1, points=1)
    adapter = FakeAdapter(undersized, undersized, undersized)

    with pytest.raises(CourseKnowledgeGraphGenerationError) as raised:
        generate_course_knowledge_graph_draft(
            _build(), owner_user_id="teacher-1", model_adapter=adapter
        )

    assert raised.value.code == "GRAPH_SCALE_UNSATISFIED"
    assert len(adapter.messages) == 3
    assert any(
        item["code"] == "MODULE_SCALE_MISMATCH"
        for item in raised.value.issues
    )


def test_model_unavailable_does_not_create_fallback_graph():
    adapter = FakeAdapter(
        CourseKnowledgeGraphGenerationError(
            "GRAPH_MODEL_UNAVAILABLE", "模型配置缺失"
        )
    )

    with pytest.raises(CourseKnowledgeGraphGenerationError) as raised:
        generate_course_knowledge_graph_draft(
            _build(), owner_user_id="teacher-1", model_adapter=adapter
        )

    assert raised.value.code == "GRAPH_MODEL_UNAVAILABLE"
    assert len(adapter.messages) == 1


def test_textbook_outline_is_in_prompt_and_accounted_for():
    textbook = {
        "textbook_id": "book-1",
        "filename": "古诗鉴赏教材.pdf",
        "parse_result": {
            "summary": "教材介绍意象和语言分析。",
            "outline": [
                {"id": "chapter-imagery", "title": "意象分析"},
                {"id": "chapter-language", "title": "语言风格"},
            ],
        },
    }
    adapter = FakeAdapter(
        _valid_payload(
            modules=3,
            points=3,
            refs=["chapter-imagery", "chapter-language"],
        )
    )

    graph = generate_course_knowledge_graph_draft(
        _build(preset="small", textbooks=[textbook]),
        owner_user_id="teacher-1",
        model_adapter=adapter,
    )

    prompt = adapter.messages[0][0][1]["content"]
    assert "古诗鉴赏教材.pdf" in prompt
    assert "chapter-imagery" in prompt
    assert graph["data"]["validation"]["mapped_outline_count"] == 2


def test_unaccounted_textbook_outline_fails_schema_validation():
    textbook = {
        "textbook_id": "book-1",
        "filename": "教材.md",
        "outline": ["章节甲"],
    }
    payload = _valid_payload(modules=3, points=3)
    adapter = FakeAdapter(payload, payload, payload)

    with pytest.raises(CourseKnowledgeGraphGenerationError) as raised:
        generate_course_knowledge_graph_draft(
            _build(preset="small", textbooks=[textbook]),
            owner_user_id="teacher-1",
            model_adapter=adapter,
        )

    assert raised.value.code == "GRAPH_SCHEMA_INVALID"
    assert any(
        item["code"] == "TEXTBOOK_OUTLINE_UNACCOUNTED"
        for item in raised.value.issues
    )


def test_module_regeneration_preserves_unselected_module_ids():
    build = _build()
    build["graph_draft"] = generate_course_knowledge_graph_draft(
        build,
        owner_user_id="teacher-1",
        model_adapter=FakeAdapter(_valid_payload()),
    )
    replacement = _valid_payload()["root"]["children"][1]
    replacement["label"] = "诗歌语言与修辞证据"
    adapter = FakeAdapter({"root": replacement, "unmapped_outline_items": []})

    regenerated = regenerate_course_knowledge_graph_module(
        build,
        module_id="module-2",
        owner_user_id="teacher-1",
        model_adapter=adapter,
    )

    assert [item["id"] for item in regenerated["children"]] == [
        "module-1",
        "module-2",
        "module-3",
        "module-4",
    ]
    assert regenerated["children"][1]["label"] == "诗歌语言与修辞证据"
    assert regenerated["data"]["regenerated_module_id"] == "module-2"


def test_incremental_module_regeneration_cannot_replace_existing_module_structure():
    build = _build(preset="small")
    baseline = _valid_payload(modules=3, points=3)["root"]
    build["config"]["update_strategy"] = "incremental"
    build["baseline_graph"] = baseline
    build["baseline_graph_version"] = 2
    build["graph_draft"] = baseline
    replacement = {
        "root": {
            "id": "module-2",
            "label": "模型试图重命名模块",
            "type": "knowledge_module",
            "summary": "模块补充说明",
            "children": [
                {
                    "id": "point-2-new",
                    "label": "新增方法",
                    "type": "knowledge_point",
                    "summary": "新增方法说明",
                    "children": [],
                }
            ],
        },
        "unmapped_outline_items": [],
    }

    regenerated = regenerate_course_knowledge_graph_module(
        build,
        module_id="module-2",
        owner_user_id="teacher-1",
        model_adapter=FakeAdapter(replacement),
    )

    module = regenerated["children"][1]
    assert module["label"] == baseline["children"][1]["label"]
    assert [item["id"] for item in module["children"][:3]] == [
        "point-2-1",
        "point-2-2",
        "point-2-3",
    ]
    assert module["children"][-1]["id"] == "point-2-new"
