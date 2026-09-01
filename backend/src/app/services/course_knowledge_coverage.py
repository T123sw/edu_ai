"""Effective coverage accounting for course knowledge materials."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


TEXTBOOK_MIN_CHARS = 800
TEXTBOOK_LONG_CHARS = 4000
TEXTBOOK_MAX_UNITS_PER_ARTIFACT = 2
WEB_MIN_CHARS = 600
AI_MIN_CHARS = 600
MINIMUM_MAPPING_CONFIDENCE = 0.25


def _content_chars(item: Mapping[str, Any]) -> int | None:
    value = item.get("content_chars")
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def calculate_leaf_coverage(
    topics: Sequence[Mapping[str, Any]],
    persisted: Sequence[Mapping[str, Any]],
    *,
    target_units: int,
    minimum_external_sources: int,
    maximum_ai: int,
) -> dict[str, dict[str, Any]]:
    """Calculate useful coverage, excluding weak, duplicate, or untraceable material."""
    coverage = {
        str(topic.get("topic_id") or ""): {
            "title": str(topic.get("title") or ""),
            "textbook_units": 0,
            "web_units": 0,
            "ai_units": 0,
            "effective_units": 0,
            "external_sources": 0,
            "rejected_materials": 0,
            "unmet": [],
        }
        for topic in topics
        if str(topic.get("topic_id") or "")
    }
    seen_hashes: dict[str, set[str]] = {topic_id: set() for topic_id in coverage}
    textbook_units: dict[str, dict[str, int]] = {topic_id: {} for topic_id in coverage}
    external_ids: dict[str, set[str]] = {topic_id: set() for topic_id in coverage}

    for item in persisted:
        topic_id = str(item.get("scope_id") or "")
        document_id = str(item.get("document_id") or "")
        if topic_id not in coverage or not document_id:
            continue
        content_hash = str(item.get("content_hash") or document_id)
        if content_hash in seen_hashes[topic_id]:
            coverage[topic_id]["rejected_materials"] += 1
            continue
        seen_hashes[topic_id].add(content_hash)

        source_type = str(item.get("source_type") or "")
        chars = _content_chars(item)
        provenance_ok = item.get("provenance_ok") is not False
        index_ok = "chunk_count" not in item or int(item.get("chunk_count") or 0) > 0
        accepted_units = 0
        bucket = ""

        if not index_ok:
            pass
        elif source_type == "textbook":
            confidence = float(item.get("mapping_confidence", 1.0) or 0)
            if provenance_ok and confidence >= MINIMUM_MAPPING_CONFIDENCE and (
                chars is None or chars >= TEXTBOOK_MIN_CHARS
            ):
                artifact_id = str(item.get("source_artifact_id") or item.get("textbook_id") or document_id)
                proposed = 2 if chars is not None and chars >= TEXTBOOK_LONG_CHARS else 1
                used = textbook_units[topic_id].get(artifact_id, 0)
                accepted_units = min(proposed, TEXTBOOK_MAX_UNITS_PER_ARTIFACT - used)
                textbook_units[topic_id][artifact_id] = used + accepted_units
                bucket = "textbook_units"
                if accepted_units and item.get("is_online_textbook") is not False:
                    external_ids[topic_id].add(f"textbook:{artifact_id}")
        elif source_type == "web":
            if provenance_ok and (chars is None or chars >= WEB_MIN_CHARS):
                accepted_units = 1
                bucket = "web_units"
                external_id = str(item.get("final_url") or item.get("source_url") or document_id)
                external_ids[topic_id].add(f"web:{external_id}")
        elif source_type == "model_generated":
            if chars is None or chars >= AI_MIN_CHARS:
                accepted_units = 1
                bucket = "ai_units"

        if accepted_units <= 0:
            coverage[topic_id]["rejected_materials"] += 1
            continue
        coverage[topic_id][bucket] += accepted_units
        coverage[topic_id]["effective_units"] += accepted_units

    target_units = max(1, int(target_units))
    minimum_external_sources = max(0, int(minimum_external_sources))
    maximum_ai = max(0, int(maximum_ai))
    for topic_id, item in coverage.items():
        item["external_sources"] = len(external_ids[topic_id])
        if item["effective_units"] < target_units:
            item["unmet"].append(f"有效覆盖 {item['effective_units']}/{target_units}")
        if item["external_sources"] < minimum_external_sources:
            item["unmet"].append(
                f"外部来源 {item['external_sources']}/{minimum_external_sources}"
            )
        if item["ai_units"] > maximum_ai:
            item["unmet"].append(f"AI 资料 {item['ai_units']}/{maximum_ai}")
    return coverage
