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
            "minimum_authoritative_sources_per_leaf": 0,
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


def _sufficient_documents():
    return [
        {
            "document_id": f"web-{index}",
            "scope_id": "leaf",
            "source_type": "web",
            "source_url": f"https://example.org/{index}",
            "content_hash": f"hash-{index}",
            "content_chars": 1200,
            "chunk_count": 2,
            "provenance_ok": True,
        }
        for index in range(3)
    ]


def test_missing_hard_deliverables_block_publication_and_cap_score():
    build = _build(minimum_web=1)
    build["intent_contract"] = {
        "deliverables": [
            {
                "requirement_id": "req-exercises",
                "type": "exercise_with_solution",
                "count": 3,
                "hardness": "hard",
            }
        ]
    }

    result = evaluate_course_knowledge_quality(build, _sufficient_documents())
    checks = {item["check_type"]: item for item in result["checks"]}

    assert result["passed"] is False
    assert result["quality_status"] == "failed"
    assert result["quality_score"] <= 59
    assert checks["intent_adherence"]["status"] == "failed"
    assert checks["intent_adherence"]["details"]["missing_deliverables"] == [
        {
            "requirement_id": "req-exercises",
            "type": "exercise_with_solution",
            "required": 3,
            "actual": 0,
        }
    ]


def test_structured_artifacts_and_required_domain_satisfy_intent_gate():
    build = _build(minimum_web=1)
    build["intent_contract"] = {
        "source_policy": {
            "required_domains": ["docs.kernel.org"],
            "minimum_authoritative_sources_per_topic": 1,
        },
        "deliverables": [
            {
                "requirement_id": "req-case",
                "type": "worked_case",
                "count": 1,
                "hardness": "hard",
            },
            {
                "requirement_id": "req-exercises",
                "type": "exercise_with_solution",
                "count": 3,
                "hardness": "hard",
            },
        ],
    }
    documents = _sufficient_documents()
    documents[0] = {
        **documents[0],
        "source_url": "https://docs.kernel.org/admin-guide/cgroup-v2.html",
        "learning_artifacts": [
            {"requirement_id": "req-case", "type": "worked_case", "count": 1},
            {"requirement_id": "req-exercises", "type": "exercise_with_solution", "count": 3},
        ],
    }

    result = evaluate_course_knowledge_quality(build, documents)
    checks = {item["check_type"]: item["status"] for item in result["checks"]}

    assert result["passed"] is True
    assert checks["required_source_policy"] == "passed"
    assert checks["intent_adherence"] == "passed"
    assert result["quality_score"] == 100


def test_topic_scoped_artifact_must_exist_for_every_execution_topic():
    build = _build(minimum_web=0)
    second = {
        "id": "leaf-2",
        "label": "二元方程",
        "data": {"type": "knowledge_point", "summary": "解二元方程"},
        "children": [],
    }
    build["graph_draft"]["children"][0]["children"].append(second)
    build["config"]["target_points_per_module"] = 2
    build["intent_contract"] = {
        "deliverables": [{
            "requirement_id": "req-case",
            "type": "worked_case",
            "count": 1,
            "hardness": "hard",
            "application": "topic",
        }]
    }
    documents = [
        {**item, "scope_id": scope_id}
        for scope_id in ("leaf", "leaf-2")
        for item in _sufficient_documents()
    ]
    documents[0]["learning_artifacts"] = [{
        "requirement_id": "req-case",
        "topic_id": "leaf",
        "type": "worked_case",
        "count": 1,
    }]

    result = evaluate_course_knowledge_quality(build, documents)
    missing = next(
        item for item in result["checks"] if item["check_type"] == "intent_adherence"
    )["details"]["missing_deliverables"]

    assert missing == [{
        "topic_id": "leaf-2",
        "requirement_id": "req-case",
        "type": "worked_case",
        "required": 1,
        "actual": 0,
    }]


def test_missing_preferred_domain_requires_teacher_decision_instead_of_false_100():
    build = _build(minimum_web=1)
    build["intent_contract"] = {
        "source_policy": {
            "preferred_domains": ["docs.kernel.org", "docs.docker.com"],
            "minimum_authoritative_sources_per_topic": 1,
        }
    }

    documents = _sufficient_documents()
    documents[0] = {
        **documents[0],
        "source_url": "https://docs.docker.com/engine/containers/resource_constraints/",
    }
    result = evaluate_course_knowledge_quality(build, documents)
    checks = {item["check_type"]: item for item in result["checks"]}

    assert result["passed"] is False
    assert result["quality_status"] == "needs_teacher_decision"
    assert result["quality_score"] < 100
    assert checks["preferred_source_policy"]["status"] == "needs_teacher_decision"
    assert checks["preferred_source_policy"]["details"]["coverage_by_domain"]["leaf"] == {
        "docs.kernel.org": 0,
        "docs.docker.com": 1,
    }


def test_each_preferred_domain_must_have_evidence_for_full_pass():
    build = _build(minimum_web=1)
    build["intent_contract"] = {
        "source_policy": {
            "preferred_domains": ["docs.kernel.org", "docs.docker.com"],
            "minimum_authoritative_sources_per_topic": 1,
        }
    }
    documents = _sufficient_documents()
    documents[0] = {
        **documents[0],
        "source_url": "https://docs.docker.com/engine/containers/resource_constraints/",
    }
    documents[1] = {
        **documents[1],
        "source_url": "https://docs.kernel.org/admin-guide/cgroup-v2.html",
    }

    result = evaluate_course_knowledge_quality(build, documents)
    checks = {item["check_type"]: item for item in result["checks"]}

    assert checks["preferred_source_policy"]["status"] == "passed"
    assert checks["preferred_source_policy"]["details"]["coverage_by_domain"]["leaf"] == {
        "docs.kernel.org": 1,
        "docs.docker.com": 1,
    }


def test_default_authoritative_coverage_rejects_only_open_web_quantity():
    build = _build(minimum_web=1)
    build["config"]["minimum_authoritative_sources_per_leaf"] = 1

    rejected = evaluate_course_knowledge_quality(build, _sufficient_documents())
    accepted_documents = _sufficient_documents()
    accepted_documents[0] = {
        **accepted_documents[0],
        "source_url": "https://university.example.edu/operating-systems/processes",
        "authority_tier": "authoritative_source",
    }
    accepted = evaluate_course_knowledge_quality(build, accepted_documents)

    rejected_checks = {item["check_type"]: item["status"] for item in rejected["checks"]}
    accepted_checks = {item["check_type"]: item["status"] for item in accepted["checks"]}
    assert rejected["passed"] is False
    assert rejected_checks["authoritative_source_coverage"] == "failed"
    assert accepted["passed"] is True
    assert accepted_checks["authoritative_source_coverage"] == "passed"
