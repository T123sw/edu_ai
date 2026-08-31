from __future__ import annotations

import copy
import hashlib
import re
import unicodedata
from collections.abc import Mapping
from typing import Any


def normalize_graph_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip().casefold()


def summarize_course_knowledge_graph(
    graph: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not graph:
        return None

    node_count = 0
    leaf_count = 0
    modules: list[dict[str, Any]] = []

    def visit(node: Mapping[str, Any]) -> None:
        nonlocal node_count, leaf_count
        node_count += 1
        children = [
            child for child in node.get("children") or [] if isinstance(child, Mapping)
        ]
        if not children:
            leaf_count += 1
        for child in children:
            visit(child)

    visit(graph)
    for child in graph.get("children") or []:
        if not isinstance(child, Mapping):
            continue
        modules.append(
            {
                "id": str(child.get("id") or ""),
                "label": str(child.get("label") or ""),
                "child_count": len(child.get("children") or []),
            }
        )
    return {
        "root_id": str(graph.get("id") or ""),
        "root_label": str(graph.get("label") or ""),
        "node_count": node_count,
        "leaf_count": leaf_count,
        "modules": modules,
    }


def _union_strings(left: Any, right: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in list(left or []) + list(right or []):
        value = str(item or "").strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _merge_summary(existing: Any, candidate: Any) -> str:
    old = str(existing or "").strip()
    new = str(candidate or "").strip()
    if not old:
        return new
    normalized_old = normalize_graph_name(old)
    normalized_new = normalize_graph_name(new)
    if not normalized_new or normalized_new in normalized_old:
        return old
    return f"{old}\n\n{new}"


def _deterministic_new_id(
    parent_id: str,
    preferred_id: str,
    label: str,
    used_ids: set[str],
) -> str:
    seed = f"{parent_id}\0{preferred_id}\0{normalize_graph_name(label)}"
    attempt = 0
    while True:
        suffix = hashlib.sha256(f"{seed}\0{attempt}".encode("utf-8")).hexdigest()[:16]
        candidate = f"incremental-{suffix}"
        if candidate not in used_ids:
            return candidate
        attempt += 1


def _mark_existing(node: dict[str, Any]) -> None:
    data = dict(node.get("data") or {})
    data["review_state"] = "existing"
    node["data"] = data
    for child in node.get("children") or []:
        if isinstance(child, dict):
            _mark_existing(child)


def _clone_new_subtree(
    incoming: Mapping[str, Any],
    *,
    parent_id: str,
    used_ids: set[str],
) -> dict[str, Any]:
    cloned = copy.deepcopy(dict(incoming))
    preferred_id = str(cloned.get("id") or "").strip()
    id_conflict = not preferred_id or preferred_id in used_ids
    if id_conflict:
        preferred_id = _deterministic_new_id(
            parent_id,
            preferred_id,
            str(cloned.get("label") or ""),
            used_ids,
        )
    cloned["id"] = preferred_id
    used_ids.add(preferred_id)
    data = dict(cloned.get("data") or {})
    if data.get("needs_parent"):
        data["review_state"] = "needs_parent"
    elif id_conflict:
        data["review_state"] = "needs_review"
    else:
        data["review_state"] = "new"
    cloned["data"] = data
    cloned["children"] = [
        _clone_new_subtree(child, parent_id=preferred_id, used_ids=used_ids)
        for child in cloned.get("children") or []
        if isinstance(child, Mapping)
    ]
    return cloned


def merge_incremental_graph(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(dict(baseline))
    used_ids: set[str] = set()

    def collect_ids(node: Mapping[str, Any]) -> None:
        used_ids.add(str(node.get("id") or ""))
        for child in node.get("children") or []:
            if isinstance(child, Mapping):
                collect_ids(child)

    collect_ids(result)
    _mark_existing(result)

    def merge_node(target: dict[str, Any], incoming: Mapping[str, Any]) -> None:
        target_data = dict(target.get("data") or {})
        incoming_data = dict(incoming.get("data") or {})
        target_data["summary"] = _merge_summary(
            target_data.get("summary"), incoming_data.get("summary")
        )
        target_data["source_outline_refs"] = _union_strings(
            target_data.get("source_outline_refs"),
            incoming_data.get("source_outline_refs"),
        )
        target_data["document_ids"] = _union_strings(
            target_data.get("document_ids"), incoming_data.get("document_ids")
        )
        target["data"] = target_data
        existing_children = [
            child for child in target.get("children") or [] if isinstance(child, dict)
        ]
        target["children"] = existing_children
        by_id = {str(child.get("id") or ""): child for child in existing_children}
        by_name = {
            normalize_graph_name(child.get("label")): child
            for child in existing_children
            if normalize_graph_name(child.get("label"))
        }
        for incoming_child in incoming.get("children") or []:
            if not isinstance(incoming_child, Mapping):
                continue
            preferred_id = str(incoming_child.get("id") or "").strip()
            matched = by_id.get(preferred_id)
            if matched is None:
                matched = by_name.get(normalize_graph_name(incoming_child.get("label")))
            if matched is not None:
                merge_node(matched, incoming_child)
                continue
            new_child = _clone_new_subtree(
                incoming_child,
                parent_id=str(target.get("id") or ""),
                used_ids=used_ids,
            )
            target["children"].append(new_child)
            by_id[str(new_child.get("id") or "")] = new_child
            normalized_name = normalize_graph_name(new_child.get("label"))
            if normalized_name:
                by_name[normalized_name] = new_child

    merge_node(result, candidate)
    return result


def baseline_graph_issues(
    baseline: Mapping[str, Any] | None,
    graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not baseline:
        return []
    issues: list[dict[str, Any]] = []
    current: dict[str, tuple[Mapping[str, Any], str | None]] = {}

    def index(node: Mapping[str, Any], parent_id: str | None) -> None:
        node_id = str(node.get("id") or "")
        current.setdefault(node_id, (node, parent_id))
        for child in node.get("children") or []:
            if isinstance(child, Mapping):
                index(child, node_id)

    index(graph, None)

    def issue(code: str, node_id: str, message: str) -> None:
        issues.append(
            {"code": code, "node_id": node_id, "path": node_id, "message": message}
        )

    def visit(node: Mapping[str, Any], parent_id: str | None) -> None:
        node_id = str(node.get("id") or "")
        loaded = current.get(node_id)
        if loaded is None:
            issue(
                "BASELINE_NODE_MISSING",
                node_id,
                f"已有节点已丢失：{node.get('label')}",
            )
            return
        actual, actual_parent = loaded
        if str(actual.get("label") or "") != str(node.get("label") or ""):
            issue(
                "BASELINE_NODE_RENAMED",
                node_id,
                f"已有节点名称不可修改：{node.get('label')}",
            )
        expected_type = str((node.get("data") or {}).get("type") or "")
        actual_type = str((actual.get("data") or {}).get("type") or "")
        if actual_type != expected_type:
            issue(
                "BASELINE_NODE_TYPE_CHANGED",
                node_id,
                f"已有节点类型不可修改：{node.get('label')}",
            )
        if actual_parent != parent_id:
            issue(
                "BASELINE_NODE_MOVED",
                node_id,
                f"已有节点不可移动：{node.get('label')}",
            )
        for child in node.get("children") or []:
            if isinstance(child, Mapping):
                visit(child, node_id)
        expected_children = [
            str(child.get("id") or "")
            for child in node.get("children") or []
            if isinstance(child, Mapping)
        ]
        actual_children = [
            str(child.get("id") or "")
            for child in actual.get("children") or []
            if isinstance(child, Mapping)
        ]
        if actual_children[: len(expected_children)] != expected_children:
            issue(
                "BASELINE_CHILD_ORDER_CHANGED",
                node_id,
                f"已有子节点顺序不可修改：{node.get('label')}",
            )

    visit(baseline, None)
    return issues


def incremental_graph_issues(
    baseline: Mapping[str, Any] | None,
    graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues = baseline_graph_issues(baseline, graph)
    seen: set[str] = set()

    def visit(node: Mapping[str, Any]) -> None:
        node_id = str(node.get("id") or "")
        if node_id in seen:
            issues.append(
                {
                    "code": "DUPLICATE_ID",
                    "node_id": node_id,
                    "path": node_id,
                    "message": f"节点 ID 重复：{node_id}",
                }
            )
        seen.add(node_id)
        data = dict(node.get("data") or {})
        if data.get("review_state") == "needs_parent" or data.get("needs_parent"):
            issues.append(
                {
                    "code": "NEW_NODE_PARENT_UNRESOLVED",
                    "node_id": node_id,
                    "path": node_id,
                    "message": f"新增节点尚未选择父节点：{node.get('label')}",
                }
            )
        for child in node.get("children") or []:
            if isinstance(child, Mapping):
                visit(child)

    visit(graph)
    return issues
