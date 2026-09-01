from __future__ import annotations

import re
from typing import Any


def _node_type_from_title(title: str) -> str:
    normalized = str(title or "").strip()
    if "摘要" in normalized:
        return "summary"
    if "引言" in normalized or "前言" in normalized:
        return "intro"
    if "结论" in normalized or "总结" in normalized:
        return "conclusion"
    return "section"


def parse_report_nodes(*, artifact_id: str, version_id: str | None, artifact_type: str, content: Any) -> list[dict[str, Any]]:
    if str(artifact_type or "").strip() == "report_outline":
        nodes: list[dict[str, Any]] = []
        for index, chapter in enumerate(list(content or []), start=1):
            title = str((chapter or {}).get("chapter_title") or "").strip()
            if not title:
                continue
            nodes.append(
                {
                    "node_id": f"{artifact_id}:{index}",
                    "artifact_id": artifact_id,
                    "version_id": version_id,
                    "node_type": _node_type_from_title(title),
                    "title": title,
                    "order_index": index,
                    "content": chapter,
                    "path": str(index),
                }
            )
        return nodes

    text = str(content or "")
    headings = list(re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text))
    if len(headings) <= 1:
        return []

    nodes = []
    order_index = 0
    for index, match in enumerate(headings[1:], start=1):
        title = str(match.group(1) or "").strip()
        start = match.end()
        end = headings[index + 1].start() if index < len(headings) - 1 else len(text)
        body = text[start:end].strip()
        order_index += 1
        nodes.append(
            {
                "node_id": f"{artifact_id}:{order_index}",
                "artifact_id": artifact_id,
                "version_id": version_id,
                "node_type": _node_type_from_title(title),
                "title": title,
                "order_index": order_index,
                "content": body,
                "path": str(order_index),
                "heading_level": len(match.group(0)) - len(match.group(0).lstrip("#")),
            }
        )
    return nodes
