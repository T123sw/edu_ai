"""Pure domain helpers for standard resources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import re
from typing import Any


class StandardKind(StrEnum):
    CLASSROOM = "classroom"
    STUDY_GUIDE = "study_guide"
    PRACTICE = "practice"


STANDARD_KINDS: tuple[StandardKind, ...] = (
    StandardKind.CLASSROOM,
    StandardKind.STUDY_GUIDE,
    StandardKind.PRACTICE,
)

_MATERIAL_TYPES = {
    StandardKind.CLASSROOM: "classroom",
    StandardKind.STUDY_GUIDE: "report",
    StandardKind.PRACTICE: "quiz",
}


@dataclass(frozen=True, slots=True)
class LeafNode:
    leaf_id: str
    title: str
    chapter_id: str | None
    chapter_title: str | None
    path_titles: tuple[str, ...]


def _node_title(node: dict[str, Any]) -> str:
    return str(node.get("label") or node.get("title") or node.get("name") or "").strip()


def _graph_root(graph: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(graph, dict) or not graph:
        return None
    root = graph.get("root")
    return root if isinstance(root, dict) else graph


def extract_leaf_nodes(graph: dict[str, Any] | None) -> list[LeafNode]:
    """Return leaf nodes in source order, carrying their top-level chapter."""

    root = _graph_root(graph)
    if root is None:
        return []
    leaves: list[LeafNode] = []

    def visit(
        node: dict[str, Any],
        *,
        path: tuple[str, ...],
        chapter: tuple[str, str] | None,
        depth: int,
    ) -> None:
        title = _node_title(node)
        node_id = str(node.get("id") or "").strip()
        next_path = (*path, title) if title else path
        next_chapter = chapter
        if depth == 1:
            next_chapter = (node_id, title)
        children = [item for item in (node.get("children") or []) if isinstance(item, dict)]
        if not children:
            if depth > 0 and node_id and title:
                leaves.append(
                    LeafNode(
                        leaf_id=node_id,
                        title=title,
                        chapter_id=next_chapter[0] if next_chapter else None,
                        chapter_title=next_chapter[1] if next_chapter else None,
                        path_titles=next_path,
                    )
                )
            return
        for child in children:
            visit(child, path=next_path, chapter=next_chapter, depth=depth + 1)

    visit(root, path=(), chapter=None, depth=0)
    return leaves


def standard_material_type(kind: StandardKind | str) -> str:
    return _MATERIAL_TYPES[StandardKind(kind)]


def stable_material_id(leaf_id: str, kind: StandardKind | str) -> str:
    normalized_leaf = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(leaf_id).strip()).strip("-")
    if not normalized_leaf:
        raise ValueError("leaf_id is required")
    if len(normalized_leaf) > 170:
        digest = hashlib.sha256(str(leaf_id).encode("utf-8")).hexdigest()[:16]
        normalized_leaf = f"{normalized_leaf[:150]}-{digest}"
    return f"standard-{normalized_leaf}-{StandardKind(kind).value}"
