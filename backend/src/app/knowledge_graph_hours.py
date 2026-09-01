"""Knowledge graph teaching-hour allocation helpers."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable, Dict, Iterable, List, Tuple


class KnowledgeGraphHourAllocationError(ValueError):
    """Raised when a graph hour allocation request cannot be completed."""


@dataclass(frozen=True)
class LeafNodeInfo:
    node_id: str
    label: str
    summary: str
    node_type: str
    depth: int
    path: List[str]
    order: int


def _ensure_dict_node(node: Any) -> Dict[str, Any]:
    if not isinstance(node, dict):
        raise KnowledgeGraphHourAllocationError("knowledge graph root must be an object")
    if not str(node.get("id") or "").strip():
        raise KnowledgeGraphHourAllocationError("knowledge graph node is missing id")
    if not str(node.get("label") or "").strip():
        raise KnowledgeGraphHourAllocationError("knowledge graph node is missing label")
    return node


def _children(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    children = node.get("children")
    if children is None:
        return []
    if not isinstance(children, list):
        return []
    return [child for child in children if isinstance(child, dict)]


def collect_leaf_nodes(root: Dict[str, Any]) -> List[LeafNodeInfo]:
    root = _ensure_dict_node(root)
    leaves: List[LeafNodeInfo] = []

    def visit(node: Dict[str, Any], path: List[str], depth: int) -> None:
        node = _ensure_dict_node(node)
        label = str(node.get("label") or "").strip()
        node_path = [*path, label]
        child_nodes = _children(node)
        if not child_nodes:
            data = node.get("data") if isinstance(node.get("data"), dict) else {}
            leaves.append(
                LeafNodeInfo(
                    node_id=str(node.get("id") or "").strip(),
                    label=label,
                    summary=str(data.get("summary") or "").strip(),
                    node_type=str(data.get("type") or "").strip() or "concept",
                    depth=depth,
                    path=node_path,
                    order=len(leaves),
                )
            )
            return
        for child in child_nodes:
            visit(child, node_path, depth + 1)

    visit(root, [], 0)
    if not leaves:
        raise KnowledgeGraphHourAllocationError("knowledge graph has no leaf nodes")
    return leaves


def validate_total_hours_to_tenths(value: Any) -> int:
    if value is None:
        raise KnowledgeGraphHourAllocationError("total_hours is required")
    text = str(value).strip()
    if not re.fullmatch(r"\d+(?:\.\d)?", text):
        raise KnowledgeGraphHourAllocationError("total_hours must be non-negative with at most one decimal place")
    try:
        decimal_value = Decimal(text)
    except InvalidOperation as exc:
        raise KnowledgeGraphHourAllocationError("total_hours must be a valid number") from exc
    if decimal_value < 0:
        raise KnowledgeGraphHourAllocationError("total_hours must be non-negative")
    return int((decimal_value * Decimal("10")).to_integral_value(rounding=ROUND_HALF_UP))


def _hours_to_tenths(value: Any) -> int:
    try:
        decimal_value = Decimal(str(value).strip())
    except Exception:
        return 0
    if decimal_value < 0:
        return 0
    return int((decimal_value * Decimal("10")).to_integral_value(rounding=ROUND_HALF_UP))


def _tenths_to_hours(value: int) -> float | int:
    if value % 10 == 0:
        return value // 10
    return float(Decimal(value) / Decimal("10"))


def parse_llm_allocations(raw: str) -> Dict[str, float]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        payload = json.loads(text)
    except Exception as exc:
        raise KnowledgeGraphHourAllocationError("LLM allocation output is not parseable JSON") from exc

    allocations = payload.get("allocations") if isinstance(payload, dict) else payload
    if not isinstance(allocations, list):
        raise KnowledgeGraphHourAllocationError("LLM allocation output must include an allocations list")

    result: Dict[str, float] = {}
    for item in allocations:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("node_id") or "").strip()
        if not node_id:
            continue
        tenths = _hours_to_tenths(item.get("hours"))
        result[node_id] = float(Decimal(tenths) / Decimal("10"))

    if not result:
        raise KnowledgeGraphHourAllocationError("LLM allocation output did not include any usable node allocations")
    return result


def _build_prompt(leaves: Iterable[LeafNodeInfo], total_hours: float | int) -> str:
    leaf_payload = [
        {
            "id": leaf.node_id,
            "label": leaf.label,
            "summary": leaf.summary,
            "type": leaf.node_type,
            "depth": leaf.depth,
            "path": " > ".join(leaf.path),
        }
        for leaf in leaves
    ]
    return (
        "You are helping a teacher allocate course teaching hours across the LEAF nodes of a knowledge graph.\n"
        "Allocate the requested total hours only to the listed leaf nodes. Parent nodes are calculated by the system.\n"
        "Use non-negative hours with at most one decimal place. A less important leaf may receive 0 hours.\n"
        "Prefer more hours for prerequisite, central, difficult, or practice-heavy concepts.\n"
        "Return strict JSON only in this shape: {\"allocations\":[{\"node_id\":\"...\",\"hours\":1.5,\"reason\":\"...\"}]}.\n"
        f"Total hours: {total_hours}\n"
        f"Leaf nodes: {json.dumps(leaf_payload, ensure_ascii=False)}"
    )


def _normalize_allocations(leaves: List[LeafNodeInfo], requested_hours: Any, allocations: Dict[str, Any]) -> Tuple[Dict[str, int], bool]:
    target = validate_total_hours_to_tenths(requested_hours)
    known_ids = {leaf.node_id for leaf in leaves}
    original: Dict[str, int] = {leaf.node_id: _hours_to_tenths(allocations.get(leaf.node_id, 0)) for leaf in leaves}
    current = sum(original.values())
    normalized = current != target or any(node_id not in known_ids for node_id in allocations)
    result = dict(original)

    if target == 0:
        return {leaf.node_id: 0 for leaf in leaves}, True

    if current < target:
        ordered = sorted(leaves, key=lambda leaf: (-original[leaf.node_id], leaf.depth, leaf.order))
        result[ordered[0].node_id] += target - current
        normalized = True
    elif current > target:
        extra = current - target
        while extra > 0:
            candidates = [leaf for leaf in leaves if result[leaf.node_id] > 0]
            if not candidates:
                break
            leaf = sorted(candidates, key=lambda item: (-result[item.node_id], item.order))[0]
            result[leaf.node_id] -= 1
            extra -= 1
        normalized = True

    return result, normalized


def _apply_leaf_hours(node: Dict[str, Any], leaf_hours: Dict[str, int]) -> None:
    children = _children(node)
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    node["data"] = data
    if not children:
        data["hours"] = _tenths_to_hours(leaf_hours.get(str(node.get("id") or ""), 0))
        return
    for child in children:
        _apply_leaf_hours(child, leaf_hours)


def rollup_hours(node: Dict[str, Any]) -> int:
    node = _ensure_dict_node(node)
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    node["data"] = data
    children = _children(node)
    if not children:
        return _hours_to_tenths(data.get("hours", 0))

    total = 0
    for child in children:
        total += rollup_hours(child)
    data["hours"] = _tenths_to_hours(total)
    return total


def allocate_graph_hours_from_llm(
    graph: Dict[str, Any],
    total_hours: Any,
    llm_call: Callable[[str], str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    leaves = collect_leaf_nodes(graph)
    target_tenths = validate_total_hours_to_tenths(total_hours)
    display_total = _tenths_to_hours(target_tenths)
    prompt = _build_prompt(leaves, display_total)
    raw = llm_call(prompt)
    parsed = parse_llm_allocations(raw)
    leaf_hours, normalized = _normalize_allocations(leaves, display_total, parsed)

    updated = copy.deepcopy(graph)
    _apply_leaf_hours(updated, leaf_hours)
    rollup_hours(updated)
    return updated, {
        "total_hours": _tenths_to_hours(target_tenths),
        "leaf_count": len(leaves),
        "source": "llm",
        "normalized": bool(normalized),
    }
