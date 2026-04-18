from __future__ import annotations

from typing import Any


_LESSON_PLAN_FIELD_LABELS = {
    "objectives": "教学目标",
    "keyPoints": "教学重点",
    "hardPoints": "教学难点",
    "teachingAids": "教学准备",
    "boardPlan": "板书设计",
    "homework": "作业",
    "reflectionTips": "反思提示",
}

_LESSON_PLAN_OUTLINE_FIELD_KEYS = ("topic", "audience", "duration", "objective")


def _field_node(*, artifact_id: str, key: str, label: str, value: Any, order_index: int) -> dict[str, Any]:
    return {
        "node_id": f"{artifact_id}:{key}",
        "node_type": "field",
        "node_key": key,
        "node_label": label,
        "order_index": order_index,
        "content": value,
    }


def _step_node(*, artifact_id: str, index: int, step: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": f"{artifact_id}:process:{index}",
        "node_type": "step",
        "node_key": "process",
        "node_label": str(step.get("step") or f"step_{index}").strip(),
        "order_index": index,
        "content": dict(step),
    }


def _parse_lesson_plan_content(*, artifact_id: str, content: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    order_index = 1
    for key, label in _LESSON_PLAN_FIELD_LABELS.items():
        value = content.get(key)
        if value in (None, "", []):
            continue
        nodes.append(
            _field_node(
                artifact_id=artifact_id,
                key=key,
                label=label,
                value=value,
                order_index=order_index,
            )
        )
        order_index += 1

    for index, step in enumerate(list(content.get("process") or []), start=1):
        if not isinstance(step, dict):
            continue
        nodes.append(_step_node(artifact_id=artifact_id, index=index, step=step))

    return nodes


def _parse_lesson_plan_outline(*, artifact_id: str, content: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    basic_info = dict(content.get("basic_info") or {})
    order_index = 1

    for key in _LESSON_PLAN_OUTLINE_FIELD_KEYS:
        value = basic_info.get(key) if key in basic_info else content.get(key)
        if value in (None, "", []):
            continue
        nodes.append(
            _field_node(
                artifact_id=artifact_id,
                key=key,
                label=key,
                value=value,
                order_index=order_index,
            )
        )
        order_index += 1

    for index, step in enumerate(list(content.get("lesson_flow") or []), start=1):
        if not isinstance(step, dict):
            continue
        nodes.append(
            {
                "node_id": f"{artifact_id}:lesson_flow:{index}",
                "node_type": "step",
                "node_key": "lesson_flow",
                "node_label": str(step.get("step") or f"step_{index}").strip(),
                "order_index": index,
                "content": dict(step),
            }
        )

    return nodes


def parse_lesson_plan_nodes(*, artifact_id: str, artifact_type: str, content: Any) -> list[dict[str, Any]]:
    if artifact_type == "lesson_plan":
        return _parse_lesson_plan_content(artifact_id=artifact_id, content=dict(content or {}))
    if artifact_type == "lesson_plan_outline":
        return _parse_lesson_plan_outline(artifact_id=artifact_id, content=dict(content or {}))
    return []
