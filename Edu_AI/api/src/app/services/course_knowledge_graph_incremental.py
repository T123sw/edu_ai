from __future__ import annotations

from collections.abc import Mapping
from typing import Any


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
