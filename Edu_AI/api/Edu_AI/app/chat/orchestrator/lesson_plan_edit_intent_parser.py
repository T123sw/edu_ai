from __future__ import annotations

import re
from typing import Any


_QUESTION_MARKERS = ("什么", "怎么", "哪些", "吗", "？", "?")
_EDIT_KEYWORDS = ("修改", "重写", "润色", "压缩", "扩写", "调整", "补充", "优化", "改", "删")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "")


def _build_request(*, artifact_reference: dict[str, Any], question: str, intent_type: str, target_confidence: str, action_type: str) -> dict[str, Any]:
    artifact_type = str(artifact_reference.get("artifact_type") or "").strip()
    return {
        "artifact_reference": dict(artifact_reference),
        "intent_type": intent_type,
        "target_type": artifact_type,
        "target_confidence": target_confidence,
        "target_locator_type": None,
        "target_node_id": None,
        "target_node_label": None,
        "candidate_nodes": [],
        "candidate_labels": [],
        "matched_snippet": None,
        "action_type": action_type,
        "instruction": str(question or "").strip(),
    }


def _looks_like_question(text: str) -> bool:
    normalized = str(text or "").strip()
    if any(keyword in normalized for keyword in _EDIT_KEYWORDS):
        return False
    return any(marker in normalized for marker in _QUESTION_MARKERS)


def _find_exact_field_or_step_match(structure_nodes: list[dict[str, Any]], question: str) -> dict[str, Any] | None:
    normalized_question = _normalize_text(question)
    for node in structure_nodes:
        label = _normalize_text(node.get("node_label"))
        if label and label in normalized_question:
            return node
    return None


def _find_node_by_order(structure_nodes: list[dict[str, Any]], question: str) -> dict[str, Any] | None:
    match = re.search(r"第\s*([0-9一二三四五六七八九十]+)\s*个?(?:环节|步骤)", str(question or ""))
    if not match:
        return None

    raw = str(match.group(1) or "").strip()
    index_map = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    order_index = int(raw) if raw.isdigit() else index_map.get(raw, 0)
    if order_index <= 0:
        return None

    return next(
        (
            node
            for node in structure_nodes
            if str(node.get("node_type") or "").strip() == "step"
            and int(node.get("order_index") or 0) == order_index
        ),
        None,
    )


def _extract_candidate_anchor(question: str) -> str:
    text = str(question or "").strip()
    for token in ("把", "改一下", "修改", "重写", "润色", "优化", "一下", "部分", "这个", "这份", "教案", "大纲"):
        text = text.replace(token, " ")
    return _normalize_text(text)


def _find_candidate_matches(structure_nodes: list[dict[str, Any]], question: str) -> list[dict[str, Any]]:
    anchor = _extract_candidate_anchor(question)
    if len(anchor) < 2:
        return []
    return [
        node
        for node in structure_nodes
        if anchor in _normalize_text(node.get("node_label"))
    ]


def _build_exact_request(node: dict[str, Any], *, artifact_reference: dict[str, Any], question: str) -> dict[str, Any]:
    request = _build_request(
        artifact_reference=artifact_reference,
        question=question,
        intent_type="edit_artifact",
        target_confidence="exact",
        action_type="rewrite",
    )
    request["target_locator_type"] = "label"
    request["target_node_id"] = node.get("node_id")
    request["target_node_label"] = node.get("node_label")
    return request


def _build_candidate_request(nodes: list[dict[str, Any]], *, artifact_reference: dict[str, Any], question: str) -> dict[str, Any]:
    request = _build_request(
        artifact_reference=artifact_reference,
        question=question,
        intent_type="edit_artifact",
        target_confidence="candidate",
        action_type="rewrite",
    )
    request["candidate_nodes"] = [
        {"node_id": str(node.get("node_id") or "").strip(), "label": str(node.get("node_label") or "").strip()}
        for node in nodes
    ]
    request["candidate_labels"] = [item["label"] for item in request["candidate_nodes"] if item["label"]]
    return request


def parse_lesson_plan_edit_intent(*, artifact_reference: dict[str, Any], question: str, structure_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    if _looks_like_question(question):
        return _build_request(
            artifact_reference=artifact_reference,
            question=question,
            intent_type="ask_about_artifact",
            target_confidence="unclear",
            action_type="ask_about_artifact",
        )

    exact_node = _find_exact_field_or_step_match(structure_nodes, question)
    if exact_node is None:
        exact_node = _find_node_by_order(structure_nodes, question)
    if exact_node is not None:
        return _build_exact_request(exact_node, artifact_reference=artifact_reference, question=question)

    candidate_nodes = _find_candidate_matches(structure_nodes, question)
    if len(candidate_nodes) > 1:
        return _build_candidate_request(candidate_nodes, artifact_reference=artifact_reference, question=question)

    return _build_request(
        artifact_reference=artifact_reference,
        question=question,
        intent_type="edit_artifact",
        target_confidence="unclear",
        action_type="rewrite",
    )
