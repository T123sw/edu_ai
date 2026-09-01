from __future__ import annotations

from typing import Any


def ok_result(tool: str, summary: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": True, "tool": tool, "summary": summary, "payload": payload or {}}


def error_result(tool: str, error: str, summary: str) -> dict[str, Any]:
    return {"ok": False, "tool": tool, "error": error, "summary": summary}


def summarize_args(args: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(value)[:100] for key, value in args.items()}
