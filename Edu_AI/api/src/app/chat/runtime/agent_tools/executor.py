from __future__ import annotations

import time

from app.chat.runtime.agent_tools.registry import get_tool_handler
from app.chat.runtime.agent_tools.result import error_result, summarize_args
from app.chat.runtime.agent_tools.tool_meta import NEVER_CACHE


def execute_tool(name: str, args: dict, ctx) -> dict:
    if ctx.step_count >= ctx.max_steps:
        return error_result(name, "budget_exceeded", "已达最大工具调用次数")
    if not _capability_allows(name, ctx.capability):
        return error_result(name, "permission_denied", "capability 不允许此工具")
    if name not in NEVER_CACHE and ctx.already_called(name, args):
        return ctx.get_cached_result(name, args)

    t0 = time.perf_counter()
    handler = get_tool_handler(name)
    if handler is None:
        result = error_result(name, "unknown_tool", f"未知工具: {name}")
    else:
        try:
            result = handler(name, args, ctx)
        except Exception as exc:
            result = error_result(name, str(exc), f"工具执行失败: {exc}")
    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    trace_step = {
        "step": ctx.step_count,
        "tool": name,
        "args": summarize_args(args),
        "result_summary": result.get("summary", ""),
        "ok": result.get("ok", False),
        "duration_ms": elapsed_ms,
    }
    if name in {"rag_search", "web_search"}:
        payload = result.get("payload") or {}
        trace_step["evidence_count"] = len(payload.get("sources") or [])
    ctx.trace["agent_steps"].append(trace_step)
    ctx.step_count += 1
    if name not in NEVER_CACHE:
        ctx.cache_result(name, args, result)
    return result


def _capability_allows(name: str, capability) -> bool:
    if name == "rag_search" and not getattr(capability, "allow_rag", False):
        return False
    if name == "web_search" and not getattr(capability, "allow_web", False):
        return False
    if name == "image_search" and not getattr(capability, "allow_image_search", False):
        return False
    return True
