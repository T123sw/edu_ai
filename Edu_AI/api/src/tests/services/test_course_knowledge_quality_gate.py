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
    assert checks["non_ai_coverage"] == "failed"
    assert checks["ai_fallback_policy"] == "failed"
    assert result["leaf_coverage"]["leaf"]["web_units"] == 0
    assert result["leaf_coverage"]["leaf"]["ai_units"] == 3


def test_explicit_zero_web_minimum_allows_textbook_and_bounded_ai_mix():
    persisted = [
        {"document_id": "book", "scope_id": "leaf", "source_type": "textbook"},
        {"document_id": "ai-1", "scope_id": "leaf", "source_type": "model_generated"},
        {"document_id": "ai-2", "scope_id": "leaf", "source_type": "model_generated"},
    ]
    result = evaluate_course_knowledge_quality(_build(minimum_web=0), persisted)

    assert result["passed"] is True
    assert len(result["checks"]) == 9
    assert result["quality_score"] == 100


def test_physical_document_count_does_not_replace_effective_coverage():
    persisted = [
        {
            "document_id": "book",
            "scope_id": "leaf",
            "source_type": "textbook",
            "source_artifact_id": "online-book",
            "content_hash": "book-hash",
            "content_chars": 5000,
            "mapping_confidence": 0.9,
            "provenance_ok": True,
            "chunk_count": 4,
        },
        {
            "document_id": "web-short",
            "scope_id": "leaf",
            "source_type": "web",
            "content_hash": "web-hash",
            "content_chars": 300,
            "provenance_ok": True,
            "chunk_count": 1,
        },
        {
            "document_id": "web-empty-index",
            "scope_id": "leaf",
            "source_type": "web",
            "content_hash": "web-empty-hash",
            "content_chars": 1000,
            "provenance_ok": True,
            "chunk_count": 0,
        },
    ]

    result = evaluate_course_knowledge_quality(_build(minimum_web=1), persisted)

    checks = {item["check_type"]: item["status"] for item in result["checks"]}
    assert checks["content_sufficiency"] == "failed"
    assert checks["non_ai_coverage"] == "passed"
    assert checks["index_integrity"] == "failed"
    assert result["leaf_coverage"]["leaf"]["effective_units"] == 2


def test_long_textbook_without_independent_external_source_fails_non_ai_gate():
    result = evaluate_course_knowledge_quality(
        _build(minimum_web=1),
        [{
            "document_id": "uploaded-book",
            "scope_id": "leaf",
            "source_type": "textbook",
            "source_artifact_id": "uploaded-book",
            "content_hash": "book-hash",
            "content_chars": 5000,
            "mapping_confidence": 0.9,
            "provenance_ok": True,
            "is_online_textbook": False,
            "chunk_count": 3,
        }],
    )

    checks = {item["check_type"]: item["status"] for item in result["checks"]}
    assert checks["non_ai_coverage"] == "failed"
    assert result["leaf_coverage"]["leaf"]["external_sources"] == 0


def test_textbook_first_ai_requires_non_ai_exhaustion_audit():
    build = _build(minimum_web=0)
    build["config"]["prefer_complete_textbooks"] = True
    persisted = [
        {"document_id": "book", "scope_id": "leaf", "source_type": "textbook"},
        {"document_id": "ai-1", "scope_id": "leaf", "source_type": "model_generated"},
        {"document_id": "ai-2", "scope_id": "leaf", "source_type": "model_generated"},
    ]

    missing_audit = evaluate_course_knowledge_quality(build, persisted)
    audited = evaluate_course_knowledge_quality(
        build,
        [
            persisted[0],
            *[
                {
                    **item,
                    "fallback_audit": {
                        "fallback_reason": "non_ai_search_exhausted",
                        "non_ai_attempt_count": 2,
                        "pre_ai_coverage": {"effective_units": 1},
                    },
                }
                for item in persisted[1:]
            ],
        ],
    )

    missing_checks = {item["check_type"]: item["status"] for item in missing_audit["checks"]}
    audited_checks = {item["check_type"]: item["status"] for item in audited["checks"]}
    assert missing_checks["ai_fallback_policy"] == "failed"
    assert audited_checks["ai_fallback_policy"] == "passed"
