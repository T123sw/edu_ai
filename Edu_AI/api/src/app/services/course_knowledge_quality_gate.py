"""Hard quality gates for a graph-first course knowledge build."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.course_knowledge_coverage import calculate_leaf_coverage
from app.services.course_knowledge_graph_generator import validate_graph_draft_for_build
from app.services.course_knowledge_source_discovery import confirmed_graph_topics


_SCALE_CODES = {"DEPTH_MISMATCH", "LEAF_DEPTH_MISMATCH", "MODULE_SCALE_MISMATCH", "LEAF_SCALE_MISMATCH"}


def evaluate_course_knowledge_quality(
    build: Mapping[str, Any],
    persisted: Sequence[Mapping[str, Any]],
    *,
    textbook_metrics: Mapping[str, Any] | None = None,
    index_integrity: bool = True,
    publication_atomicity: bool = True,
) -> dict[str, Any]:
    graph = dict(build.get("graph_draft") or {})
    topics = confirmed_graph_topics(graph)
    config = dict(build.get("config") or {})
    target_total = max(1, int(config.get("target_materials_per_leaf") or 3))
    minimum_web = max(0, int(config.get("minimum_web_materials_per_leaf") or 0))
    maximum_ai = max(0, int(config.get("maximum_ai_materials_per_leaf") or 0))
    coverage = calculate_leaf_coverage(
        topics,
        persisted,
        target_units=target_total,
        minimum_external_sources=minimum_web,
        maximum_ai=maximum_ai,
    )
    textbook_metrics = dict(textbook_metrics or {})
    per_leaf_unmapped = dict(textbook_metrics.get("unmapped_by_leaf") or {})
    for topic_id, item in coverage.items():
        item["fetch_failed"] = int(
            dict(build.get("metrics") or {}).get("fetch_failed_by_leaf", {}).get(topic_id, 0)
        )
        item["unmapped_textbook_chunks"] = int(per_leaf_unmapped.get(topic_id, 0))

    graph_issues, _graph_metrics = validate_graph_draft_for_build(build, graph)
    schema_issues = [issue for issue in graph_issues if issue.get("code") not in _SCALE_CODES]
    scale_issues = [issue for issue in graph_issues if issue.get("code") in _SCALE_CODES]
    ai_documents = [item for item in persisted if item.get("source_type") == "model_generated"]
    require_fallback_audit = bool(config.get("prefer_complete_textbooks", False))
    unaudited_ai = [
        str(item.get("document_id") or "")
        for item in ai_documents
        if require_fallback_audit
        and (
            (item.get("fallback_audit") or {}).get("fallback_reason")
            != "non_ai_search_exhausted"
            or int((item.get("fallback_audit") or {}).get("non_ai_attempt_count") or 0) < 1
            or not isinstance((item.get("fallback_audit") or {}).get("pre_ai_coverage"), Mapping)
        )
    ]
    checks = [
        ("graph_schema", not schema_issues, {"issues": schema_issues}),
        ("graph_scale", not scale_issues, {"issues": scale_issues}),
        (
            "textbook_mapping_quality",
            int(textbook_metrics.get("invalid_mapping_count") or 0) == 0,
            textbook_metrics,
        ),
        (
            "non_ai_coverage",
            all(item["external_sources"] >= minimum_web for item in coverage.values()),
            {"minimum_per_leaf": minimum_web, "coverage": coverage},
        ),
        (
            "content_sufficiency",
            bool(coverage) and all(item["effective_units"] >= target_total for item in coverage.values()),
            {"target_per_leaf": target_total, "coverage": coverage},
        ),
        (
            "ai_fallback_policy",
            all(item["ai_units"] <= maximum_ai for item in coverage.values())
            and not unaudited_ai,
            {
                "maximum_per_leaf": maximum_ai,
                "coverage": coverage,
                "unaudited_document_ids": unaudited_ai,
            },
        ),
        (
            "provenance_integrity",
            all(
                item.get("provenance_ok") is not False
                for item in persisted
                if item.get("source_type") in {"web", "textbook"}
            ),
            {"persisted_count": len(persisted)},
        ),
        (
            "index_integrity",
            bool(index_integrity)
            and all(
                "chunk_count" not in item or int(item.get("chunk_count") or 0) > 0
                for item in persisted
                if item.get("scope_id")
            ),
            {"persisted_count": len(persisted)},
        ),
        ("publication_atomicity", bool(publication_atomicity), {}),
    ]
    normalized_checks = [
        {"check_type": name, "status": "passed" if passed else "failed", "details": details}
        for name, passed, details in checks
    ]
    passed = all(item["status"] == "passed" for item in normalized_checks)
    score = round(sum(item["status"] == "passed" for item in normalized_checks) / len(normalized_checks) * 100, 2)
    return {
        "passed": passed,
        "quality_score": score,
        "checks": normalized_checks,
        "leaf_coverage": coverage,
        "target_materials_per_leaf": target_total,
        "minimum_web_materials_per_leaf": minimum_web,
        "maximum_ai_materials_per_leaf": maximum_ai,
    }
