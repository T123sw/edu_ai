"""Map staged textbook chunks onto confirmed graph leaves."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.services.course_knowledge_source_discovery import confirmed_graph_topics


MINIMUM_MAPPING_CONFIDENCE = 0.25


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _terms(value: str) -> set[str]:
    normalized = _clean(value).casefold()
    result = set(re.findall(r"[a-z0-9+#.-]{2,}", normalized))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    result.update(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
    return {item for item in result if item}


def map_textbook_chunks_to_graph(build: Mapping[str, Any]) -> dict[str, Any]:
    graph = dict(build.get("graph_draft") or {})
    topics = confirmed_graph_topics(graph)
    refs_by_leaf: dict[str, set[str]] = {}

    def visit(node: Mapping[str, Any]) -> None:
        children = [item for item in node.get("children") or [] if isinstance(item, Mapping)]
        if not children:
            refs_by_leaf[str(node.get("id") or "")] = {
                _clean(item).casefold()
                for item in (node.get("data") or {}).get("source_outline_refs") or []
                if _clean(item)
            }
        for child in children:
            visit(child)

    visit(graph)
    topic_terms = {
        topic["topic_id"]: _terms(f"{topic['title']} {topic['objective']} {topic['graph_path']}")
        for topic in topics
    }
    mappings: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    textbooks = [
        *(build.get("textbooks") or []),
        *(build.get("online_textbooks") or []),
    ]
    for textbook in textbooks:
        if textbook.get("status") != "ready":
            continue
        textbook_id = str(textbook.get("textbook_id") or "")
        for chunk in (textbook.get("parse_result") or {}).get("chunks") or []:
            chapter_keys = {
                _clean(chunk.get("chapter_id")).casefold(),
                _clean(chunk.get("chapter_title")).casefold(),
            } - {""}
            exact_leaf = next(
                (
                    topic["topic_id"]
                    for topic in topics
                    if refs_by_leaf.get(topic["topic_id"], set()) & chapter_keys
                ),
                None,
            )
            if exact_leaf:
                leaf_id = exact_leaf
                method = "outline_anchor"
                confidence = 1.0
            else:
                chunk_terms = _terms(
                    f"{chunk.get('chapter_title')} {_clean(chunk.get('content'))[:3000]}"
                )
                chapter_title = _clean(chunk.get("chapter_title")).casefold()
                scores = {
                    topic["topic_id"]: (
                        0.9
                        if _clean(topic["title"]).casefold() in chapter_title
                        else (
                            len(topic_terms[topic["topic_id"]] & chunk_terms)
                            / len(topic_terms[topic["topic_id"]])
                            if topic_terms[topic["topic_id"]]
                            else 0.0
                        )
                    )
                    for topic in topics
                }
                ranked_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
                leaf_id, confidence = ranked_scores[0] if ranked_scores else ("", 0.0)
                second_confidence = ranked_scores[1][1] if len(ranked_scores) > 1 else 0.0
                if (
                    confidence >= MINIMUM_MAPPING_CONFIDENCE
                    and second_confidence > 0
                    and confidence - second_confidence < 0.05
                ):
                    leaf_id = ""
                    method = "ambiguous"
                else:
                    method = "semantic_overlap"
            record = {
                "textbook_id": textbook_id,
                "filename": textbook.get("filename"),
                "chunk_id": chunk.get("chunk_id"),
                "chapter_id": chunk.get("chapter_id"),
                "chapter_title": chunk.get("chapter_title"),
                "page": chunk.get("page"),
                "content": chunk.get("content"),
                "content_chars": len(_clean(chunk.get("content"))),
                "content_hash": chunk.get("content_hash"),
                "knowledge_node_id": leaf_id or None,
                "mapping_method": method,
                "mapping_confidence": round(float(confidence), 4),
                "source_url": textbook.get("source_url"),
            }
            if leaf_id and confidence >= MINIMUM_MAPPING_CONFIDENCE:
                mappings.append(record)
            else:
                record["knowledge_node_id"] = None
                unmapped.append(record)
    return {
        "mappings": mappings,
        "unmapped": unmapped,
        "metrics": {
            "mapped_chunk_count": len(mappings),
            "unmapped_chunk_count": len(unmapped),
            "ambiguous_mapping_count": sum(
                item.get("mapping_method") == "ambiguous" for item in unmapped
            ),
            "invalid_mapping_count": 0,
        },
    }
