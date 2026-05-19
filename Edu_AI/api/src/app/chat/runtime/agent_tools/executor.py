from __future__ import annotations

import time

from app.chat.runtime.agent_tools.registry import get_tool_handler
from app.chat.runtime.agent_tools.result import error_result, summarize_args


def execute_tool(name: str, args: dict, ctx) -> dict:
    if ctx.step_count >= ctx.max_steps:
        return error_result(name, "budget_exceeded", "已达最大工具调用次数")
    if not _capability_allows(name, ctx.capability):
        return error_result(name, "permission_denied", "capability 不允许此工具")
    if ctx.already_called(name, args):
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

    ctx.trace["agent_steps"].append(
        {
            "step": ctx.step_count,
            "tool": name,
            "args": summarize_args(args),
            "result_summary": result.get("summary", ""),
            "ok": result.get("ok", False),
            "duration_ms": elapsed_ms,
        }
    )
    ctx.step_count += 1
    ctx.cache_result(name, args, result)
    return result


def _capability_allows(name: str, capability) -> bool:
    if name == "rag_search" and not getattr(capability, "allow_rag", False):
        return False
    if name == "web_search" and not getattr(capability, "allow_web", False):
        return False
    return True
