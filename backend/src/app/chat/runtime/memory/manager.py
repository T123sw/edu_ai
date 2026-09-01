"""Maintain working memory, a durable task ledger, and a bounded narrative summary."""
from __future__ import annotations

import json
from typing import Any


_TASK_INTENTS = {"generate_single", "prepare_bundle", "modify", "confirm"}
_SUMMARY_LIMIT = 1200
_LEDGER_LIMIT = 50


def update_agent_memory(
    existing: dict[str, Any] | None,
    *,
    user_message: str,
    task_contract: dict[str, Any] | None,
    state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the next memory snapshot without deriving facts from summary text."""
    memory = dict(existing or {})
    state = dict(state or {})
    contract = dict(task_contract or {})
    working = dict(memory.get("working_memory") or {})
    intent = str(contract.get("intent") or "")
    active_outline = dict(state.get("active_draft_outline") or {})

    topic = str(contract.get("topic") or "").strip()
    if active_outline.get("subject"):
        working["active_topic"] = str(active_outline["subject"]).strip()
    elif topic and (intent in _TASK_INTENTS or not working.get("active_topic")):
        working["active_topic"] = topic

    resources = list(contract.get("resource_types") or [])
    if resources and (intent in _TASK_INTENTS or not working.get("active_resource_types")):
        working["active_resource_types"] = list(dict.fromkeys(map(str, resources)))
    if intent:
        working["last_intent"] = intent

    constraints = dict(contract.get("constraints") or {})
    if contract.get("audience"):
        constraints.setdefault("audience", contract["audience"])
    if contract.get("lesson_duration") is not None:
        constraints.setdefault("lesson_duration", contract["lesson_duration"])
    if constraints:
        working["constraints"] = {
            **dict(working.get("constraints") or {}),
            **constraints,
        }

    source_mode = str(contract.get("source_mode") or "")
    if source_mode and (intent in _TASK_INTENTS or not working.get("source_mode")):
        working["source_mode"] = source_mode
        working["selected_document_ids"] = list(
            contract.get("selected_document_ids") or []
        )
    if active_outline:
        working["active_outline"] = {
            key: active_outline.get(key)
            for key in ("subject", "resource_type", "outline_markdown", "needs_visuals")
            if active_outline.get(key) not in (None, "")
        }
    if contract.get("confirmation_policy"):
        working["confirmation_policy"] = contract["confirmation_policy"]

    ledger = _merge_task_ledger(
        list(memory.get("task_ledger") or []),
        list(state.get("pending_tasks") or []),
        logical_task_id=str(state.get("logical_task_id") or ""),
        topic=str(working.get("active_topic") or ""),
    )
    summary = _append_summary(
        str(memory.get("conversation_summary") or ""),
        turn_count=int(memory.get("turn_count") or 0) + 1,
        user_message=user_message,
        intent=intent,
    )
    return {
        "schema_version": "2026-08-09.memory.v1",
        "turn_count": int(memory.get("turn_count") or 0) + 1,
        "working_memory": working,
        "task_ledger": ledger,
        "conversation_summary": summary,
    }


def build_agent_memory_context(memory: dict[str, Any] | None) -> str:
    """Build a privacy-minimal, fact-first system note for subsequent turns."""
    memory = dict(memory or {})
    if not memory:
        return ""
    working = dict(memory.get("working_memory") or {})
    ledger = list(memory.get("task_ledger") or [])[-8:]
    safe_working = {
        key: working.get(key)
        for key in (
            "active_topic", "active_resource_types", "constraints", "source_mode",
            "selected_document_ids", "confirmation_policy", "active_outline",
        )
        if working.get(key) not in (None, "", [], {})
    }
    safe_ledger = [
        {
            key: item.get(key)
            for key in ("task_id", "logical_task_id", "workflow_type", "status", "material_id")
            if item.get(key) not in (None, "")
        }
        for item in ledger if isinstance(item, dict)
    ]
    return (
        "【Agent 持久任务记忆】\n"
        f"轮次：{int(memory.get('turn_count') or 0)}\n"
        f"工作事实：{json.dumps(safe_working, ensure_ascii=False, sort_keys=True)}\n"
        f"任务账本：{json.dumps(safe_ledger, ensure_ascii=False, sort_keys=True)}\n"
        f"对话摘要：{str(memory.get('conversation_summary') or '')[-600:]}\n"
        "工作事实和任务账本优先于摘要；摘要不得覆盖确认点、来源、任务或材料事实。"
    )


def _merge_task_ledger(
    existing: list[dict],
    pending: list[dict],
    *,
    logical_task_id: str,
    topic: str,
) -> list[dict]:
    order: list[str] = []
    by_id: dict[str, dict] = {}
    for raw in [*existing, *pending]:
        if not isinstance(raw, dict):
            continue
        task_id = str(raw.get("task_id") or "").strip()
        if not task_id:
            continue
        if task_id not in by_id:
            order.append(task_id)
        prior = by_id.get(task_id, {})
        by_id[task_id] = {
            **prior,
            **{
                key: value for key, value in raw.items()
                if key in {"task_id", "workflow_type", "status", "material_id", "result_ref"}
            },
            "logical_task_id": str(raw.get("logical_task_id") or logical_task_id or prior.get("logical_task_id") or ""),
            "topic": str(raw.get("topic") or topic or prior.get("topic") or ""),
            "status": str(raw.get("status") or prior.get("status") or "accepted"),
        }
    return [by_id[task_id] for task_id in order[-_LEDGER_LIMIT:]]


def _append_summary(existing: str, *, turn_count: int, user_message: str, intent: str) -> str:
    normalized = " ".join(str(user_message or "").split())[:180]
    entry = f"T{turn_count}({intent or 'unknown'}): {normalized}" if normalized else ""
    summary = " | ".join(part for part in (existing, entry) if part)
    if len(summary) <= _SUMMARY_LIMIT:
        return summary
    return summary[-_SUMMARY_LIMIT:].lstrip(" |")
