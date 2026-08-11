"""Hard quality gates for a graph-first course knowledge build."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

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
    coverage = {
        topic["topic_id"]: {
            "title": topic["title"],
            "textbook": 0,
            "web": 0,
            "ai": 0,
            "total": 0,
            "fetch_failed": 0,
            "unmapped_textbook_chunks": 0,
            "unmet": [],
        }
        for topic in topics
    }
    seen: set[tuple[str, str]] = set()
    for item in persisted:
        scope_id = str(item.get("scope_id") or "")
        document_id = str(item.get("document_id") or "")
        if scope_id not in coverage or not document_id or (scope_id, document_id) in seen:
            continue
        seen.add((scope_id, document_id))
        source_type = str(item.get("source_type") or "")
        bucket = "ai" if source_type == "model_generated" else source_type
        if bucket in {"web", "textbook"}:
            coverage[scope_id][bucket] += 1
        elif bucket == "ai":
            coverage[scope_id]["ai"] += 1
        coverage[scope_id]["total"] += 1
    textbook_metrics = dict(textbook_metrics or {})
    per_leaf_unmapped = dict(textbook_metrics.get("unmapped_by_leaf") or {})
    for topic_id, item in coverage.items():
        item["fetch_failed"] = int(
            dict(build.get("metrics") or {}).get("fetch_failed_by_leaf", {}).get(topic_id, 0)
        )
        item["unmapped_textbook_chunks"] = int(per_leaf_unmapped.get(topic_id, 0))
        if item["web"] < minimum_web:
            item["unmet"].append(f"网络资料 {item['web']}/{minimum_web}")
        if item["total"] < target_total:
            item["unmet"].append(f"总资料 {item['total']}/{target_total}")
        if item["ai"] > maximum_ai:
            item["unmet"].append(f"AI 资料 {item['ai']}/{maximum_ai}")

    graph_issues, _graph_metrics = validate_graph_draft_for_build(build, graph)
    schema_issues = [issue for issue in graph_issues if issue.get("code") not in _SCALE_CODES]
    scale_issues = [issue for issue in graph_issues if issue.get("code") in _SCALE_CODES]
    checks = [
        ("graph_schema", not schema_issues, {"issues": schema_issues}),
        ("graph_scale", not scale_issues, {"issues": scale_issues}),
        (
            "textbook_mapping",
            int(textbook_metrics.get("invalid_mapping_count") or 0) == 0,
            textbook_metrics,
        ),
        (
            "web_minimum",
            all(item["web"] >= minimum_web for item in coverage.values()),
            {"minimum_per_leaf": minimum_web, "coverage": coverage},
        ),
        (
            "material_coverage",
            bool(coverage) and all(item["total"] >= target_total for item in coverage.values()),
            {"target_per_leaf": target_total, "coverage": coverage},
        ),
        (
            "ai_limit",
            all(item["ai"] <= maximum_ai for item in coverage.values()),
            {"maximum_per_leaf": maximum_ai, "coverage": coverage},
        ),
        ("index_integrity", bool(index_integrity), {"persisted_count": len(persisted)}),
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
