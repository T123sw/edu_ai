from __future__ import annotations

import re
from typing import Any


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def _find_node_by_type(nodes: list[dict[str, Any]], node_type: str) -> dict[str, Any] | None:
    return next((node for node in nodes if str(node.get("node_type") or "").strip() == node_type), None)


def _find_node_by_order(nodes: list[dict[str, Any]], order_index: int) -> dict[str, Any] | None:
    return next((node for node in nodes if int(node.get("order_index") or 0) == order_index), None)


def _find_node_by_title(nodes: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
    normalized_title = _normalize_text(title)
    if not normalized_title:
        return None
    return next((node for node in nodes if _normalize_text(str(node.get("title") or "")) == normalized_title), None)


def _find_node_by_title_mention(nodes: list[dict[str, Any]], text: str) -> dict[str, Any] | None:
    normalized_text = _normalize_text(text)
    ranked_nodes = sorted(
        nodes,
        key=lambda node: len(_normalize_text(str(node.get("title") or ""))),
        reverse=True,
    )
    for node in ranked_nodes:
        normalized_title = _normalize_text(str(node.get("title") or ""))
        if normalized_title and normalized_title in normalized_text:
            return node
    return None


def _find_nodes_by_snippet(nodes: list[dict[str, Any]], snippet: str) -> list[dict[str, Any]]:
    normalized_snippet = _normalize_text(snippet)
    if not normalized_snippet:
        return []
    return [
        node
        for node in nodes
        if normalized_snippet in _normalize_text(str(node.get("content") or ""))
    ]


def _extract_quoted_snippet(text: str) -> str:
    match = re.search(r"[\"'\u201c\u201d\u2018\u2019\u300c\u300d\u300e\u300f](.+?)[\"'\u201c\u201d\u2018\u2019\u300c\u300d\u300e\u300f]", str(text or ""))
    return str(match.group(1) or "").strip() if match else ""


def _build_base_request(*, artifact_reference: dict[str, Any], question: str, target_type: str) -> dict[str, Any]:
    return {
        "artifact_reference": dict(artifact_reference),
        "intent_type": "edit_artifact",
        "target_type": target_type,
        "target_confidence": "unclear",
        "target_locator_type": None,
        "target_node_id": None,
        "target_node_label": None,
        "matched_snippet": None,
        "action_type": "rewrite",
        "instruction": str(question or "").strip(),
        "needs_disambiguation": False,
        "candidate_labels": [],
        "candidate_nodes": [],
    }


def _is_artifact_question(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False

    edit_keywords = (
        "\u4fee\u6539",
        "\u91cd\u5199",
        "\u538b\u7f29",
        "\u7f29\u5230",
        "\u7cbe\u7b80",
        "\u6269\u5199",
        "\u8c03\u6574\u987a\u5e8f",
        "\u91cd\u6392",
        "\u91cd\u65b0\u751f\u6210",
        "\u6539\u5199",
        "\u6da6\u8272",
        "\u6539",
    )
    if any(keyword in normalized for keyword in edit_keywords):
        return False

    question_keywords = (
        "\u4ec0\u4e48",
        "\u600e\u4e48",
        "\u4e3a\u4f55",
        "\u4e3a\u4ec0\u4e48",
        "\u662f\u5426",
        "\u54ea\u4e9b",
        "\u51e0\u70b9",
        "\uff1f",
        "?",
    )
    return any(keyword in normalized for keyword in question_keywords)


def _is_ambiguous_reference(text: str) -> bool:
    normalized = str(text or "").strip()
    ambiguous_markers = (
        "\u8fd9\u4e00\u90e8\u5206",
        "\u8fd9\u90e8\u5206",
        "\u8fd9\u4e2a\u90e8\u5206",
        "\u8fd9\u4e00\u6bb5",
        "\u8fd9\u91cc",
        "\u8fd9\u4e2a\u7ae0\u8282",
    )
    return any(marker in normalized for marker in ambiguous_markers)


def _detect_action_type(text: str, *, target_type: str) -> str:
    if "\u91cd\u65b0\u751f\u6210" in text and ("\u6b63\u5f0f\u62a5\u544a" in text or "\u62a5\u544a" in text) and target_type == "outline":
        return "regenerate"
    if any(keyword in text for keyword in ("\u6269\u5199", "\u5c55\u5f00")):
        return "expand"
    if any(keyword in text for keyword in ("\u538b\u7f29", "\u7cbe\u7b80", "\u7f29\u5230", "\u6539\u77ed")):
        return "compress"
    if any(keyword in text for keyword in ("\u8c03\u6574\u987a\u5e8f", "\u91cd\u6392")):
        return "reorder"
    return "rewrite"


def _candidate_labels(nodes: list[dict[str, Any]]) -> list[str]:
    return [
        str(node.get("title") or "").strip()
        for node in nodes
        if str(node.get("title") or "").strip()
    ]


def _candidate_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "node_id": str(node.get("node_id") or "").strip(),
            "label": str(node.get("title") or "").strip(),
        }
        for node in nodes
        if str(node.get("node_id") or "").strip() and str(node.get("title") or "").strip()
    ]


def _build_candidate_request(base_request: dict[str, Any], nodes: list[dict[str, Any]], *, matched_snippet: str | None = None) -> dict[str, Any]:
    return {
        **base_request,
        "target_confidence": "candidate",
        "matched_snippet": matched_snippet,
        "needs_disambiguation": True,
        "candidate_labels": _candidate_labels(nodes),
        "candidate_nodes": _candidate_nodes(nodes),
    }


def _extract_candidate_anchor(text: str) -> str:
    normalized = str(text or "").strip()
    noisy_tokens = (
        "帮我",
        "请",
        "把",
        "将",
        "修改",
        "重写",
        "压缩",
        "缩到",
        "精简",
        "扩写",
        "调整顺序",
        "重排",
        "重新生成",
        "改写",
        "润色",
        "优化",
        "强化",
        "改成",
        "改",
        "报告",
        "大纲",
        "这一部分",
        "这部分",
        "那部分",
        "这一节",
        "这一段",
        "一下",
        "一点",
        "再",
        "更",
    )
    for token in noisy_tokens:
        normalized = normalized.replace(token, " ")
    normalized = re.sub(r"[，。！？、,.!?:：\s]+", "", normalized)
    return normalized


def _find_nodes_by_anchor(nodes: list[dict[str, Any]], anchor: str) -> list[dict[str, Any]]:
    normalized_anchor = _normalize_text(anchor)
    if len(normalized_anchor) < 2:
        return []
    return [
        node
        for node in nodes
        if normalized_anchor in _normalize_text(str(node.get("title") or ""))
    ]


def _match_precise_locator(*, text: str, nodes: list[dict[str, Any]], base_request: dict[str, Any], action_type: str) -> dict[str, Any] | None:
    quoted = _extract_quoted_snippet(text)
    if quoted:
        title_node = _find_node_by_title(nodes, quoted)
        if title_node is not None:
            return {
                **base_request,
                "target_confidence": "exact",
                "target_locator_type": "title",
                "target_node_id": title_node.get("node_id"),
                "target_node_label": title_node.get("title"),
                "action_type": action_type,
            }

        snippet_matches = _find_nodes_by_snippet(nodes, quoted)
        if len(snippet_matches) == 1:
            target_node = snippet_matches[0]
            return {
                **base_request,
                "target_confidence": "exact",
                "target_locator_type": "snippet",
                "target_node_id": target_node.get("node_id"),
                "target_node_label": target_node.get("title"),
                "matched_snippet": quoted,
                "action_type": action_type,
            }

        if len(snippet_matches) > 1:
            return _build_candidate_request(base_request, snippet_matches, matched_snippet=quoted)

    mentioned_title_node = _find_node_by_title_mention(nodes, text)
    if mentioned_title_node is not None:
        return {
            **base_request,
            "target_confidence": "exact",
            "target_locator_type": "title",
            "target_node_id": mentioned_title_node.get("node_id"),
            "target_node_label": mentioned_title_node.get("title"),
            "action_type": action_type,
        }

    return None


def parse_report_edit_intent(*, artifact_reference: dict[str, Any], question: str, structure_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    text = str(question or "").strip()
    artifact_type = str(artifact_reference.get("artifact_type") or "").strip()
    target_type = "outline" if artifact_type == "report_outline" else "report"
    base_request = _build_base_request(
        artifact_reference=artifact_reference,
        question=text,
        target_type=target_type,
    )

    if _is_artifact_question(text):
        return {
            **base_request,
            "intent_type": "ask_about_artifact",
            "target_confidence": "unclear",
            "action_type": "ask_about_artifact",
        }

    action_type = _detect_action_type(text, target_type=target_type)
    if action_type == "regenerate":
        return {
            **base_request,
            "target_confidence": "exact",
            "action_type": "regenerate",
        }

    precise_match = _match_precise_locator(
        text=text,
        nodes=structure_nodes,
        base_request=base_request,
        action_type=action_type,
    )
    if precise_match is not None:
        return precise_match

    if "\u6458\u8981" in text:
        summary_node = _find_node_by_type(structure_nodes, "summary")
        if summary_node is not None:
            return {
                **base_request,
                "target_confidence": "exact",
                "target_locator_type": "node_type",
                "target_node_id": summary_node.get("node_id"),
                "target_node_label": summary_node.get("title"),
                "action_type": action_type,
            }

    if "\u7ed3\u8bba" in text or "\u603b\u7ed3" in text:
        conclusion_node = _find_node_by_type(structure_nodes, "conclusion")
        if conclusion_node is not None:
            return {
                **base_request,
                "target_confidence": "exact",
                "target_locator_type": "node_type",
                "target_node_id": conclusion_node.get("node_id"),
                "target_node_label": conclusion_node.get("title"),
                "action_type": action_type,
            }

    match = re.search(r"\u7b2c\s*([0-9\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341]+)\s*\u90e8\u5206", text)
    if match:
        raw = str(match.group(1) or "").strip()
        index_map = {
            "\u4e00": 1,
            "\u4e8c": 2,
            "\u4e09": 3,
            "\u56db": 4,
            "\u4e94": 5,
            "\u516d": 6,
            "\u4e03": 7,
            "\u516b": 8,
            "\u4e5d": 9,
            "\u5341": 10,
        }
        order_index = int(raw) if raw.isdigit() else index_map.get(raw, 0)
        target_node = _find_node_by_order(structure_nodes, order_index)
        if target_node is not None:
            return {
                **base_request,
                "target_confidence": "exact",
                "target_locator_type": "order",
                "target_node_id": target_node.get("node_id"),
                "target_node_label": target_node.get("title"),
                "action_type": action_type,
            }

    candidate_anchor = _extract_candidate_anchor(text)
    candidate_matches = _find_nodes_by_anchor(structure_nodes, candidate_anchor)
    if len(candidate_matches) > 1:
        request = _build_candidate_request(base_request, candidate_matches)
        request["action_type"] = action_type
        return request

    if _is_ambiguous_reference(text) and len(structure_nodes) > 1 and candidate_matches:
        request = _build_candidate_request(base_request, candidate_matches)
        request["action_type"] = action_type
        return request

    return {
        **base_request,
        "action_type": action_type,
    }
