from __future__ import annotations

from app.chat.runtime.agent_tools.result import error_result, ok_result
from app.services.job_store import JobStatus, cancel_job, get_job
from core.course_storage import storage_manager


def _target_task_id(args: dict, ctx) -> str:
    explicit = str(args.get("task_id") or "").strip()
    if explicit:
        return explicit
    pending = list(getattr(ctx, "pending_tasks", []) or [])
    return str((pending[-1] if pending else {}).get("task_id") or "")


def _handle_query_task_status(name: str, args: dict, ctx, *, canonical_only: bool) -> dict:
    task_ids = [
        str(item.get("task_id") or "")
        for item in list(getattr(ctx, "pending_tasks", []) or [])
    ]
    explicit = str(args.get("task_id") or "").strip()
    if explicit:
        task_ids = [explicit]
    if canonical_only:
        task_ids = [task_id for task_id in task_ids if task_id.startswith("job_")]

    tasks: list[dict] = []
    resolved_artifacts: list[dict] = []
    owner = str(getattr(getattr(ctx, "request", None), "owner", "") or "")
    for task_id in dict.fromkeys(task for task in task_ids if task):
        job = get_job(task_id)
        if not job:
            continue
        job_owner = str(getattr(job, "owner_user_id", "") or "")
        if not owner or not job_owner or job_owner != owner:
            continue
        status = getattr(job, "status", "unknown")
        status_value = str(getattr(status, "value", status))
        result_ref = getattr(job, "result_ref", None)
        artifact = _resolve_course_material(result_ref, owner)
        has_full_course_ref = bool(
            isinstance(result_ref, dict)
            and result_ref.get("course_id")
            and result_ref.get("material_type")
            and result_ref.get("material_id")
        )
        readable = status_value == JobStatus.SUCCEEDED.value and bool(result_ref)
        if status_value == JobStatus.SUCCEEDED.value and has_full_course_ref:
            readable = artifact is not None
        if artifact is not None:
            resolved_artifacts.append({
                "task_id": task_id,
                "resource_type": str(result_ref.get("material_type") or ""),
                "artifact": artifact,
            })
        tasks.append({
            "task_id": task_id,
            "status": status_value,
            "result_ref": result_ref,
            "artifact_readable": (
                readable if status_value == JobStatus.SUCCEEDED.value else None
            ),
            "error": getattr(job, "error_message", None),
        })
    if not tasks:
        return error_result(name, "task_not_found", "未找到可查询的教学任务")
    completed = [item for item in tasks if item["status"] == JobStatus.SUCCEEDED.value]
    if completed:
        ctx.artifact_readback = {
            "checked": len(completed),
            "readable": all(item["artifact_readable"] for item in completed),
        }
        if resolved_artifacts:
            ctx.artifact_readback["artifacts"] = resolved_artifacts
    return ok_result(
        name,
        f"已读取 {len(tasks)} 个任务状态",
        {
            "tasks": tasks,
            "artifact_readback": getattr(ctx, "artifact_readback", None),
        },
    )


def handle_query_generation_job_status(name: str, args: dict, ctx) -> dict:
    explicit = str(args.get("task_id") or "").strip()
    if explicit and not explicit.startswith("job_"):
        return error_result(
            name,
            "task_domain_mismatch",
            "后台生成状态工具只接受规范 job_ 生成任务",
        )
    return _handle_query_task_status(name, args, ctx, canonical_only=True)


def handle_query_task_status(name: str, args: dict, ctx) -> dict:
    """Legacy internal compatibility for non-agent callers and old tests."""
    return _handle_query_task_status(name, args, ctx, canonical_only=False)


def _resolve_course_material(result_ref, owner: str):
    if not isinstance(result_ref, dict):
        return None
    course_id = str(result_ref.get("course_id") or "").strip()
    material_type = str(result_ref.get("material_type") or "").strip()
    material_id = str(result_ref.get("material_id") or "").strip()
    if not (course_id and material_type and material_id):
        return None
    return storage_manager.get_generated_material(
        course_id,
        material_type,
        material_id,
        owner_user_id=owner or None,
    )


def handle_cancel_task(name: str, args: dict, ctx) -> dict:
    task_id = _target_task_id(args, ctx)
    owner = str(getattr(getattr(ctx, "request", None), "owner", "") or "")
    if not task_id:
        return error_result(name, "task_not_found", "未找到可取消的教学任务")
    try:
        job = cancel_job(task_id, owner_user_id=owner)
    except Exception as exc:
        return error_result(name, "cancel_failed", f"取消任务失败: {exc}")
    return ok_result(
        name,
        "已提交取消请求",
        {"task_id": task_id, "status": str(getattr(job, "status", ""))},
    )
