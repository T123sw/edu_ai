from __future__ import annotations

import json
from pathlib import Path


GRAPH_PATH = (
    Path(__file__).resolve().parents[2]
    / "evaluation"
    / "candidates"
    / "computational-thinking-knowledge-graph-v2.json"
)


def _walk(node):
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


def test_candidate_graph_is_course_oriented_atomic_and_unique() -> None:
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    nodes = list(_walk(graph))
    leaves = [node for node in nodes if not (node.get("children") or [])]
    ids = [node["id"] for node in nodes]
    labels = [node["label"] for node in leaves]

    assert graph["data"]["status"] == "shadow"
    assert len(leaves) == 49
    assert len(ids) == len(set(ids))
    assert len(labels) == len(set(labels))
    assert not ({"序", "序言", "前言", "参考文献", "纸质书", "小结", "练习"} & set(labels))
    assert all(node.get("data", {}).get("type") == "knowledge_point" for node in leaves)
    assert all(len(node.get("data", {}).get("keywords") or []) >= 3 for node in leaves)
