"""Stable Agent-side idempotency keys for irreversible generation submissions."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def ensure_logical_task_id(ctx: Any) -> str:
    existing = str(getattr(ctx, "logical_task_id", "") or "").strip()
    if existing:
        return existing
    request = getattr(ctx, "request", None)
    contract = dict(getattr(ctx, "task_contract", {}) or {})
    seed = {
        "owner": str(getattr(request, "owner", "") or ""),
        "course": str(getattr(request, "course_id", "") or ""),
        "conversation": str(getattr(request, "conversation_id", "") or ""),
        "contract": contract,
    }
    digest = hashlib.sha256(
        json.dumps(seed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    value = f"task-{digest}"
    setattr(ctx, "logical_task_id", value)
    return value


def generation_idempotency_key(ctx: Any, resource_type: str, args: dict) -> str:
    request = getattr(ctx, "request", None)
    contract = dict(getattr(ctx, "task_contract", {}) or {})
    payload = {
        "owner": str(getattr(request, "owner", "") or ""),
        "course": str(getattr(request, "course_id", "") or ""),
        "conversation": str(getattr(request, "conversation_id", "") or ""),
        "logical_task_id": ensure_logical_task_id(ctx),
        "resource_type": resource_type,
        "contract": contract,
        "args": dict(args or {}),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]
    return f"agent-{resource_type}-{digest}"
