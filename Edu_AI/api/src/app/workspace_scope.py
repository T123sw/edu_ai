from __future__ import annotations

from typing import Any, Optional


SCOPE_TYPE_COURSE = "course"
SCOPE_TYPE_KNOWLEDGE_POINT = "knowledge_point"


def normalize_workspace_scope(
    *,
    course_id: str,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
) -> dict[str, Any]:
    normalized_course_id = str(course_id or "").strip()
    if not normalized_course_id:
        raise ValueError("course_id is required")

    normalized_scope_type = str(scope_type or SCOPE_TYPE_COURSE).strip() or SCOPE_TYPE_COURSE
    if normalized_scope_type not in {SCOPE_TYPE_COURSE, SCOPE_TYPE_KNOWLEDGE_POINT}:
        raise ValueError("scope_type must be 'course' or 'knowledge_point'")

    normalized_scope_id = str(scope_id or "").strip() or None
    if normalized_scope_type == SCOPE_TYPE_KNOWLEDGE_POINT and not normalized_scope_id:
        raise ValueError("scope_id is required when scope_type=knowledge_point")
    if normalized_scope_type == SCOPE_TYPE_COURSE:
        normalized_scope_id = None

    return {
        "course_id": normalized_course_id,
        "scope_type": normalized_scope_type,
        "scope_id": normalized_scope_id,
    }


def _collect_descendants(node: dict[str, Any], bucket: set[str]) -> None:
    node_id = str(node.get("id") or "").strip()
    if node_id:
        bucket.add(node_id)

    for child in list(node.get("children") or []):
        if isinstance(child, dict):
            _collect_descendants(child, bucket)


def collect_scope_ids_for_query(
    graph_root: Optional[dict[str, Any]],
    *,
    scope_type: str,
    scope_id: Optional[str],
) -> set[str]:
    if scope_type == SCOPE_TYPE_COURSE:
        return set()

    target_id = str(scope_id or "").strip()
    if not target_id:
        return set()

    def find(node: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not isinstance(node, dict):
            return None
        if str(node.get("id") or "").strip() == target_id:
            return node
        for child in list(node.get("children") or []):
            found = find(child if isinstance(child, dict) else None)
            if found is not None:
                return found
        return None

    target = find(graph_root)
    if target is None:
        return {target_id}

    result: set[str] = set()
    _collect_descendants(target, result)
    return result
