from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


ARTIFACT_INTENT_PROMPT = """你是“生成物引用意图分类器”。
你的任务不是直接修改内容，而是判断当前这轮消息相对当前引用生成物的意图。

你只能输出 JSON，对象字段如下：
{
  "action": "discuss_current_artifact" | "edit_current_artifact" | "switch_artifact" | "exit_artifact_context",
  "confidence": "high" | "medium" | "low",
  "reason": "一句简短原因",
  "target_hint": {
    "artifact_type": "可选",
    "target_locator": "可选"
  }
}

判定原则：
1. 用户在解释、追问、分析当前引用生成物时，返回 discuss_current_artifact。
2. 用户要求改写、扩写、删减、调整结构、修改某一页/某一部分时，返回 edit_current_artifact。
3. 用户明确表示不要继续基于当前引用、要移除引用、要聊别的时，返回 exit_artifact_context。
4. 只有在输入上下文已经明确存在新的 artifact_reference 时，才允许返回 switch_artifact。
5. 如果你不确定，请降低 confidence，不要强行判定为 edit。
6. 不要输出 JSON 以外的任何内容。
"""

ALLOWED_ACTIONS = {
    "discuss_current_artifact",
    "edit_current_artifact",
    "switch_artifact",
    "exit_artifact_context",
}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


@dataclass(slots=True)
class ArtifactIntentDecision:
    action: str
    confidence: str
    reason: str = ""
    source: str = "fallback"
    clear_reference: bool = False
    target_hint: dict[str, Any] | None = None


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(exclude_none=True)
        return dict(dumped) if isinstance(dumped, dict) else {}
    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}
    return {}


def _extract_json_payload(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return dict(raw)

    text = str(getattr(raw, "content", raw) or "").strip()
    if not text:
        return None

    normalized = text
    if normalized.startswith("```"):
        normalized = normalized.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        payload = json.loads(normalized)
        return payload if isinstance(payload, dict) else None
    except Exception:
        pass

    start = normalized.find("{")
    end = normalized.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(normalized[start : end + 1])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _recent_message_hints(snapshot) -> list[dict[str, str]]:
    recent_messages = list(getattr(snapshot, "recent_messages", []) or [])
    hints: list[dict[str, str]] = []
    for item in recent_messages[-3:]:
        if isinstance(item, dict):
            role = str(item.get("role") or "").strip()
            content = str(item.get("content") or "").strip()
        else:
            role = str(getattr(item, "role", "") or "").strip()
            content = str(getattr(item, "content", "") or "").strip()
        if role or content:
            hints.append({"role": role, "content": content[:300]})
    return hints


def _build_prompt(*, question: str, request_reference, snapshot, has_new_reference: bool) -> str:
    payload = {
        "question": str(question or "").strip(),
        "request_reference": _as_dict(request_reference),
        "active_artifact": _as_dict(getattr(snapshot, "active_artifact", None)),
        "conversation_hint": _recent_message_hints(snapshot),
        "has_new_reference": bool(has_new_reference),
    }
    return f"{ARTIFACT_INTENT_PROMPT}\n\n输入上下文：\n{json.dumps(payload, ensure_ascii=False)}"


def classify_artifact_intent(*, question, request_reference, snapshot, llm, has_new_reference=False) -> ArtifactIntentDecision:
    has_active_artifact = bool(_as_dict(getattr(snapshot, "active_artifact", None)))
    if request_reference is None and not has_active_artifact:
        return ArtifactIntentDecision(action="no_artifact", confidence="low", source="no_artifact")

    if llm is None:
        return ArtifactIntentDecision(action="discuss_current_artifact", confidence="low", source="fallback_no_llm")

    prompt = _build_prompt(
        question=question,
        request_reference=request_reference,
        snapshot=snapshot,
        has_new_reference=has_new_reference,
    )

    try:
        raw = llm.invoke(prompt)
    except Exception as exc:
        return ArtifactIntentDecision(
            action="discuss_current_artifact",
            confidence="low",
            reason=str(exc),
            source="fallback_model_error",
        )

    payload = _extract_json_payload(raw)
    if payload is None:
        return ArtifactIntentDecision(action="discuss_current_artifact", confidence="low", source="fallback_invalid_json")

    action = str(payload.get("action") or "").strip()
    confidence = str(payload.get("confidence") or "").strip().lower()
    reason = str(payload.get("reason") or "").strip()
    target_hint = payload.get("target_hint")

    if action not in ALLOWED_ACTIONS or confidence not in ALLOWED_CONFIDENCE:
        return ArtifactIntentDecision(
            action="discuss_current_artifact",
            confidence="low",
            reason=reason,
            source="fallback_invalid_payload",
        )
    if action == "switch_artifact" and not has_new_reference:
        return ArtifactIntentDecision(
            action="discuss_current_artifact",
            confidence="low",
            reason=reason,
            source="fallback_invalid_switch",
        )
    if confidence != "high":
        return ArtifactIntentDecision(
            action="discuss_current_artifact",
            confidence=confidence,
            reason=reason,
            source="llm_low_confidence",
        )

    return ArtifactIntentDecision(
        action=action,
        confidence=confidence,
        reason=reason,
        source="llm_json",
        clear_reference=(action == "exit_artifact_context"),
        target_hint=target_hint if isinstance(target_hint, dict) else None,
    )
