"""Hard quality gates for a graph-first course knowledge build."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from app.services.course_knowledge_coverage import calculate_leaf_coverage
from app.services.course_knowledge_graph_generator import validate_graph_draft_for_build
from app.services.course_knowledge_source_discovery import execution_topics
from app.services.course_knowledge_source_policy import is_authoritative_source_domain


_SCALE_CODES = {"DEPTH_MISMATCH", "LEAF_DEPTH_MISMATCH", "MODULE_SCALE_MISMATCH", "LEAF_SCALE_MISMATCH"}


def _domain_matches(hostname: str, domains: Sequence[str]) -> bool:
    normalized = str(hostname or "").casefold().strip(".")
    return any(
        normalized == str(domain).casefold().strip(".")
        or normalized.endswith("." + str(domain).casefold().strip("."))
        for domain in domains
        if str(domain or "").strip()
    )


def _persisted_domain(item: Mapping[str, Any]) -> str:
    configured = str(item.get("source_domain") or "").strip()
    if configured:
        return configured.casefold()
    return str(urlsplit(str(item.get("final_url") or item.get("source_url") or "")).hostname or "").casefold()


def _is_authoritative_material(item: Mapping[str, Any]) -> bool:
    tier = str(item.get("authority_tier") or "")
    if tier in {
        "teacher_required_source",
        "teacher_preferred_source",
        "authoritative_source",
    }:
        return item.get("semantic_evidence_passed") is not False
    if item.get("source_type") == "textbook" and not item.get("is_online_textbook", False):
        # A teacher-uploaded textbook is a first-party course source.
        return item.get("semantic_evidence_passed") is not False
    return (
        item.get("semantic_evidence_passed") is not False
        and is_authoritative_source_domain(_persisted_domain(item))
    )


def _artifact_counts(persisted: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in persisted:
        artifact_type = str(item.get("learning_artifact_type") or item.get("artifact_type") or "").strip()
        if artifact_type:
            counts[artifact_type] = counts.get(artifact_type, 0) + max(
                1, int(item.get("artifact_count") or 1)
            )
        for artifact in item.get("learning_artifacts") or []:
            if not isinstance(artifact, Mapping):
                continue
            if str(artifact.get("validation_status") or "passed") != "passed":
                continue
            nested_type = str(artifact.get("type") or artifact.get("artifact_type") or "").strip()
            if nested_type:
                counts[nested_type] = counts.get(nested_type, 0) + max(
                    1, int(artifact.get("count") or 1)
                )
    return counts


def _artifact_requirement_counts(
    persisted: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for item in persisted:
        for artifact in item.get("learning_artifacts") or []:
            if not isinstance(artifact, Mapping):
                continue
            if str(artifact.get("validation_status") or "passed") != "passed":
                continue
            requirement_id = str(artifact.get("requirement_id") or "")
            artifact_type = str(artifact.get("type") or artifact.get("artifact_type") or "")
            if not requirement_id or not artifact_type:
                continue
            key = (requirement_id, artifact_type)
            counts[key] = counts.get(key, 0) + max(1, int(artifact.get("count") or 1))
    return counts


def _artifact_requirement_topic_counts(
    persisted: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], int]:
    counts: dict[tuple[str, str, str], int] = {}
    for item in persisted:
        for artifact in item.get("learning_artifacts") or []:
            if not isinstance(artifact, Mapping):
                continue
            if str(artifact.get("validation_status") or "passed") != "passed":
                continue
            requirement_id = str(artifact.get("requirement_id") or "")
            artifact_type = str(artifact.get("type") or artifact.get("artifact_type") or "")
            topic_id = str(artifact.get("topic_id") or item.get("scope_id") or "")
            if not requirement_id or not artifact_type or not topic_id:
                continue
            key = (topic_id, requirement_id, artifact_type)
            counts[key] = counts.get(key, 0) + max(1, int(artifact.get("count") or 1))
    return counts


def evaluate_course_knowledge_quality(
    build: Mapping[str, Any],
    persisted: Sequence[Mapping[str, Any]],
    *,
    textbook_metrics: Mapping[str, Any] | None = None,
    index_integrity: bool = True,
    publication_atomicity: bool = True,
) -> dict[str, Any]:
    graph = dict(build.get("graph_draft") or {})
    topics = execution_topics(build)
    config = dict(build.get("config") or {})
    target_total = max(1, int(config.get("target_materials_per_leaf") or 3))
    minimum_web = max(0, int(config.get("minimum_web_materials_per_leaf") or 0))
    maximum_ai = max(0, int(config.get("maximum_ai_materials_per_leaf") or 0))
    targets = {t["topic_id"]: int(t.get("target_units") or target_total) for t in topics}
    ai_limits = {t["topic_id"]: int(t.get("ai_limit", maximum_ai)) for t in topics}
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
            not in {"non_ai_search_exhausted", "teacher_required_artifact"}
            or (
                (item.get("fallback_audit") or {}).get("fallback_reason")
                == "non_ai_search_exhausted"
                and int((item.get("fallback_audit") or {}).get("non_ai_attempt_count") or 0) < 1
            )
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
            bool(coverage) and all(item["effective_units"] >= targets[key] for key, item in coverage.items()),
            {"target_per_leaf": target_total, "coverage": coverage},
        ),
        (
            "ai_fallback_policy",
            all(item["ai_units"] <= ai_limits[key] for key, item in coverage.items())
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
    minimum_default_authoritative = max(
        0,
        int(
            config.get(
                "minimum_authoritative_sources_per_leaf",
                1 if minimum_web > 0 else 0,
            )
        ),
    )
    if minimum_default_authoritative:
        authoritative_coverage = {
            topic["topic_id"]: sum(
                1
                for item in persisted
                if str(item.get("scope_id") or "") == topic["topic_id"]
                and _is_authoritative_material(item)
            )
            for topic in topics
        }
        normalized_checks.append(
            {
                "check_type": "authoritative_source_coverage",
                "status": "passed"
                if all(
                    value >= minimum_default_authoritative
                    for value in authoritative_coverage.values()
                )
                else "failed",
                "details": {
                    "minimum_per_topic": minimum_default_authoritative,
                    "coverage": authoritative_coverage,
                },
            }
        )
    intent = dict(build.get("intent_contract") or {})
    source_policy = dict(intent.get("source_policy") or {})
    required_domains = list(source_policy.get("required_domains") or [])
    preferred_domains = list(source_policy.get("preferred_domains") or [])
    minimum_authoritative = max(
        0, int(source_policy.get("minimum_authoritative_sources_per_topic") or 0)
    )
    if required_domains:
        required_coverage = {
            topic["topic_id"]: sum(
                1
                for item in persisted
                if str(item.get("scope_id") or "") == topic["topic_id"]
                and _domain_matches(_persisted_domain(item), required_domains)
            )
            for topic in topics
        }
        normalized_checks.append(
            {
                "check_type": "required_source_policy",
                "status": "passed"
                if all(value >= minimum_authoritative for value in required_coverage.values())
                else "failed",
                "details": {
                    "required_domains": required_domains,
                    "minimum_per_topic": minimum_authoritative,
                    "coverage": required_coverage,
                },
            }
        )
    elif preferred_domains:
        preferred_coverage = {
            topic["topic_id"]: sum(
                1
                for item in persisted
                if str(item.get("scope_id") or "") == topic["topic_id"]
                and _domain_matches(_persisted_domain(item), preferred_domains)
            )
            for topic in topics
        }
        preferred_coverage_by_domain = {
            topic["topic_id"]: {
                domain: sum(
                    1
                    for item in persisted
                    if str(item.get("scope_id") or "") == topic["topic_id"]
                    and _domain_matches(_persisted_domain(item), [domain])
                )
                for domain in preferred_domains
            }
            for topic in topics
        }
        all_preferred_domains_covered = all(
            all(count >= 1 for count in domains.values())
            for domains in preferred_coverage_by_domain.values()
        )
        normalized_checks.append(
            {
                "check_type": "preferred_source_policy",
                "status": "passed"
                if all(value >= minimum_authoritative for value in preferred_coverage.values())
                and all_preferred_domains_covered
                else "needs_teacher_decision",
                "details": {
                    "preferred_domains": preferred_domains,
                    "minimum_per_topic": minimum_authoritative,
                    "coverage": preferred_coverage,
                    "coverage_by_domain": preferred_coverage_by_domain,
                    "decision": "指定优先来源不足；教师需修改来源偏好或确认降级后才能发布。",
                },
            }
        )

    deliverables = [
        item
        for item in intent.get("deliverables") or []
        if isinstance(item, Mapping) and item.get("hardness", "hard") == "hard"
    ]
    if deliverables:
        actual_artifacts = _artifact_counts(persisted)
        requirement_artifacts = _artifact_requirement_counts(persisted)
        topic_artifacts = _artifact_requirement_topic_counts(persisted)
        missing = []
        for item in deliverables:
            requirement_id = str(item.get("requirement_id") or "")
            artifact_type = str(item.get("type") or "")
            required = int(item.get("count") or 0)
            if item.get("application") == "topic":
                for topic in topics:
                    topic_id = str(topic.get("topic_id") or "")
                    actual = topic_artifacts.get((topic_id, requirement_id, artifact_type), 0)
                    if actual < required:
                        missing.append({
                            "topic_id": topic_id,
                            "requirement_id": requirement_id,
                            "type": artifact_type,
                            "required": required,
                            "actual": actual,
                        })
            else:
                actual = requirement_artifacts.get((requirement_id, artifact_type), 0)
                if actual < required:
                    missing.append({
                        "requirement_id": requirement_id,
                        "type": artifact_type,
                        "required": required,
                        "actual": actual,
                    })
        normalized_checks.append(
            {
                "check_type": "intent_adherence",
                "status": "failed" if missing else "passed",
                "details": {"artifact_counts": actual_artifacts, "missing_deliverables": missing},
            }
        )

    passed = all(item["status"] == "passed" for item in normalized_checks)
    weights = {"passed": 1.0, "needs_teacher_decision": 0.5, "failed": 0.0}
    score = round(
        sum(weights.get(str(item["status"]), 0.0) for item in normalized_checks)
        / len(normalized_checks)
        * 100,
        2,
    )
    hard_intent_failed = any(
        item["check_type"] in {"required_source_policy", "intent_adherence"}
        and item["status"] == "failed"
        for item in normalized_checks
    )
    if hard_intent_failed:
        score = min(score, 59.0)
    return {
        "passed": passed,
        "quality_status": (
            "passed"
            if passed
            else "needs_teacher_decision"
            if any(item["status"] == "needs_teacher_decision" for item in normalized_checks)
            and not any(item["status"] == "failed" for item in normalized_checks)
            else "failed"
        ),
        "quality_score": score,
        "checks": normalized_checks,
        "leaf_coverage": coverage,
        "target_materials_per_leaf": target_total,
        "minimum_web_materials_per_leaf": minimum_web,
        "maximum_ai_materials_per_leaf": maximum_ai,
    }
