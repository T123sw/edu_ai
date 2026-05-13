from __future__ import annotations


def fallback_route(*, question: str, active_task: str | None, active_artifact_type: str | None) -> dict:
    return {
        "action": "chat.reply",
        "confidence": 0.0,
        "reason": "fallback_disabled",
    }

