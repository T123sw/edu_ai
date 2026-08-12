from __future__ import annotations

from app.services.course_knowledge_quality_gate import evaluate_course_knowledge_quality


def _build(minimum_web=1):
    return {
        "config": {
            "graph_depth": 3,
            "target_module_count": 1,
            "target_points_per_module": 1,
            "target_materials_per_leaf": 3,
            "minimum_web_materials_per_leaf": minimum_web,
            "maximum_ai_materials_per_leaf": 2,
        },
        "graph_draft": {
            "id": "root",
            "label": "代数课程",
            "data": {"type": "course", "summary": "课程"},
            "children": [
                {
                    "id": "module",
                    "label": "方程模块",
                    "data": {"type": "knowledge_module", "summary": "模块"},
                    "children": [
                        {
                            "id": "leaf",
                            "label": "一元方程",
                            "data": {"type": "knowledge_point", "summary": "解方程"},
                            "children": [],
                        }
                    ],
                }
            ],
        },
        "textbooks": [],
        "metrics": {"fetch_failed_by_leaf": {"leaf": 2}},
    }


def test_ai_materials_do_not_satisfy_web_minimum():
    persisted = [
        {"document_id": f"ai-{index}", "scope_id": "leaf", "source_type": "model_generated"}
        for index in range(3)
    ]
    result = evaluate_course_knowledge_quality(_build(minimum_web=1), persisted)

    assert result["passed"] is False
    checks = {item["check_type"]: item["status"] for item in result["checks"]}
    assert checks["web_minimum"] == "failed"
    assert checks["ai_limit"] == "failed"
    assert result["leaf_coverage"]["leaf"]["web"] == 0
    assert result["leaf_coverage"]["leaf"]["ai"] == 3


def test_explicit_zero_web_minimum_allows_textbook_and_bounded_ai_mix():
    persisted = [
        {"document_id": "book", "scope_id": "leaf", "source_type": "textbook"},
        {"document_id": "ai-1", "scope_id": "leaf", "source_type": "model_generated"},
        {"document_id": "ai-2", "scope_id": "leaf", "source_type": "model_generated"},
    ]
    result = evaluate_course_knowledge_quality(_build(minimum_web=0), persisted)

    assert result["passed"] is True
    assert len(result["checks"]) == 8
    assert result["quality_score"] == 100
