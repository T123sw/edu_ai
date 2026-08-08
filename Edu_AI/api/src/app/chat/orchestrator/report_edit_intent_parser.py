from __future__ import annotations

import re
from typing import Any


def _find_node_by_type(nodes: list[dict[str, Any]], node_type: str) -> dict[str, Any] | None:
    return next((node for node in nodes if str(node.get("node_type") or "").strip() == node_type), None)


def _find_node_by_order(nodes: list[dict[str, Any]], order_index: int) -> dict[str, Any] | None:
    return next((node for node in nodes if int(node.get("order_index") or 0) == order_index), None)


def _build_base_request(*, artifact_reference: dict[str, Any], question: str, target_type: str) -> dict[str, Any]:
    return {
        "artifact_reference": dict(artifact_reference),
        "target_type": target_type,
        "target_node_id": None,
        "target_node_label": None,
        "action_type": "rewrite",
        "instruction": str(question or "").strip(),
        "needs_disambiguation": False,
        "candidate_labels": [],
    }


def _is_artifact_question(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False

    edit_keywords = (
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
    )
    if any(keyword in normalized for keyword in edit_keywords):
        return False

    question_keywords = ("什么", "怎么", "为何", "为什么", "是否", "哪些", "几点", "？", "?")
    return any(keyword in normalized for keyword in question_keywords)


def _is_ambiguous_reference(text: str) -> bool:
    normalized = str(text or "").strip()
    ambiguous_markers = ("这一部分", "这部分", "这个部分", "这一段", "这里", "这个章节")
    return any(marker in normalized for marker in ambiguous_markers)


def parse_report_edit_intent(*, artifact_reference: dict[str, Any], question: str, structure_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    text = str(question or "").strip()
    normalized = text.lower()
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
            "action_type": "ask_about_artifact",
        }

    if _is_ambiguous_reference(text) and len(structure_nodes) > 1:
        return {
            **base_request,
            "needs_disambiguation": True,
            "candidate_labels": [
                str(node.get("title") or "").strip()
                for node in structure_nodes
                if str(node.get("title") or "").strip()
            ],
        }

    if "重新生成" in text and ("正式报告" in text or "报告" in text) and target_type == "outline":
        return {
            **base_request,
            "action_type": "regenerate",
        }

    numbered_match = re.search(r"(?<!\d)(\d+(?:\.\d+)+)(?!\d)", text)
    if numbered_match:
        section_number = numbered_match.group(1)
        target_node = next(
            (
                node
                for node in structure_nodes
                if re.match(
                    rf"^{re.escape(section_number)}(?:\s|[、.．:：]|$)",
                    str(node.get("title") or "").strip(),
                )
            ),
            None,
        )
        if target_node is not None:
            return {
                **base_request,
                "target_node_id": target_node.get("node_id"),
                "target_node_label": target_node.get("title"),
                "action_type": "delete" if "删除" in text else "rewrite",
            }

    if "摘要" in text:
        summary_node = _find_node_by_type(structure_nodes, "summary")
        if summary_node is not None:
            return {
                **base_request,
                "target_node_id": summary_node.get("node_id"),
                "target_node_label": summary_node.get("title"),
                "action_type": "compress" if ("压缩" in text or "缩到" in text or "精简" in text) else "rewrite",
            }

    if "结论" in text or "总结" in text:
        conclusion_node = _find_node_by_type(structure_nodes, "conclusion")
        if conclusion_node is not None:
            return {
                **base_request,
                "target_node_id": conclusion_node.get("node_id"),
                "target_node_label": conclusion_node.get("title"),
                "action_type": "rewrite",
            }

    match = re.search(r"第\s*([0-9一二三四五六七八九十]+)\s*部分", text)
    if match:
        raw = str(match.group(1) or "").strip()
        index_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        order_index = int(raw) if raw.isdigit() else index_map.get(raw, 0)
        target_node = _find_node_by_order(structure_nodes, order_index)
        if target_node is not None:
            return {
                **base_request,
                "target_node_id": target_node.get("node_id"),
                "target_node_label": target_node.get("title"),
                "action_type": "rewrite",
            }

    action_type = "rewrite"
    if "删除" in text:
        action_type = "delete"
    elif "扩写" in text:
        action_type = "expand"
    elif "压缩" in text or "精简" in text:
        action_type = "compress"
    elif "调整顺序" in text or "重排" in text:
        action_type = "reorder"

    fallback_node = structure_nodes[0] if structure_nodes else None
    return {
        **base_request,
        "target_node_id": fallback_node.get("node_id") if fallback_node else None,
        "target_node_label": fallback_node.get("title") if fallback_node else None,
        "action_type": action_type,
    }
