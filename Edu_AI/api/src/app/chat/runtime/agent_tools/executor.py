from __future__ import annotations

import time

from app.chat.runtime.agent_tools.registry import get_tool_handler
from app.chat.runtime.agent_tools.result import error_result, summarize_args
from app.chat.runtime.agent_tools.tool_meta import NEVER_CACHE


def execute_tool(name: str, args: dict, ctx) -> dict:
    if ctx.step_count >= ctx.max_steps:
        return error_result(name, "budget_exceeded", "已达最大工具调用次数")
    if not _capability_allows(
        name,
        ctx.capability,
        actor_role=str(getattr(ctx.request, "actor_role", "teacher") or "teacher"),
    ):
        return error_result(name, "permission_denied", "capability 不允许此工具")
    if name not in NEVER_CACHE and ctx.already_called(name, args):
        return ctx.get_cached_result(name, args)

    t0 = time.perf_counter()
    result = _reject_task_domain_mismatch(name, args)
    if result is None:
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
    if result.get("error"):
        trace_step["error"] = str(result["error"])
    payload = result.get("payload") or {}
    if isinstance(payload, dict) and payload.get("task_id"):
        trace_step["task_id"] = str(payload["task_id"])
        trace_step["workflow_type"] = str(payload.get("workflow_type") or "")
    if name in {"rag_search", "web_search"}:
        trace_step["evidence_count"] = len(payload.get("sources") or [])
    ctx.trace["agent_steps"].append(trace_step)
    ctx.step_count += 1
    if name not in NEVER_CACHE:
        ctx.cache_result(name, args, result)
    return result


def _capability_allows(name: str, capability, *, actor_role: str = "teacher") -> bool:
    role = "student" if str(actor_role or "").strip().lower() == "student" else "teacher"
    if role == "student" and name == "get_course_learning_progress":
        return False
    if role == "teacher" and name == "get_my_learning_progress":
        return False
    if role == "student" and name in {"generate_lesson_plan", "generate_blog"}:
        return False
    if role == "teacher" and name in {"generate_flashcard", "generate_game"}:
        return False
    if name == "rag_search" and not getattr(capability, "allow_rag", False):
        return False
    if name == "web_search" and not getattr(capability, "allow_web", False):
        return False
    if name == "image_search" and not getattr(capability, "allow_image_search", False):
        return False
    return True


def _reject_task_domain_mismatch(name: str, args: dict) -> dict | None:
    task_id = str(args.get("task_id") or "").strip()
    if (
        name in {"get_my_learning_progress", "get_course_learning_progress"}
        and task_id
        and not task_id.startswith("lt_")
    ):
        return error_result(
            name,
            "task_domain_mismatch",
            "课程学习工具只接受 lt_ 学习任务",
        )
    if name == "query_generation_job_status" and task_id and not task_id.startswith("job_"):
        return error_result(
            name,
            "task_domain_mismatch",
            "后台生成状态工具只接受规范 job_ 生成任务",
        )
    if name == "cancel_task" and task_id.startswith("lt_"):
        return error_result(
            name,
            "task_domain_mismatch",
            "后台生成任务工具不能处理课程学习任务",
        )
    return None
