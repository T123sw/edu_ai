from __future__ import annotations

from app.chat.runtime.agent_tools.result import error_result, ok_result


def _learning_context(ctx) -> dict:
    snapshot = getattr(ctx, "snapshot", None)
    return dict(getattr(snapshot, "learning_context", {}) or {})


def handle_get_my_learning_progress(name: str, args: dict, ctx) -> dict:
    role = str(getattr(getattr(ctx, "request", None), "actor_role", "") or "").lower()
    context = _learning_context(ctx)
    if role != "student" or context.get("projection") != "student":
        return error_result(name, "permission_denied", "学生学习进度只能由学生本人读取")

    task_id = str(args.get("task_id") or "").strip()
    pending_tasks = list(context.get("pending_tasks") or [])
    completed_tasks = list(context.get("completed_tasks") or [])
    if task_id:
        pending_tasks = [item for item in pending_tasks if item.get("task_id") == task_id]
        completed_tasks = [item for item in completed_tasks if item.get("task_id") == task_id]
    tasks = pending_tasks + completed_tasks
    return ok_result(
        name,
        f"已读取 {len(tasks)} 条本人课程学习记录",
        {
            "pending_tasks": pending_tasks,
            "completed_tasks": completed_tasks,
            "tasks": tasks,
            "as_of": context.get("as_of"),
        },
    )


def handle_get_course_learning_progress(name: str, args: dict, ctx) -> dict:
    role = str(
        getattr(getattr(ctx, "request", None), "actor_role", "teacher") or "teacher"
    ).lower()
    context = _learning_context(ctx)
    if role == "student" or context.get("projection") != "teacher":
        return error_result(name, "permission_denied", "课程学习汇总仅课程教师可读取")

    task_id = str(args.get("task_id") or "").strip()
    summaries = list(context.get("task_summaries") or [])
    if task_id:
        summaries = [item for item in summaries if item.get("task_id") == task_id]
    return ok_result(
        name,
        f"已读取 {len(summaries)} 个课程学习任务汇总",
        {"task_summaries": summaries, "as_of": context.get("as_of")},
    )
