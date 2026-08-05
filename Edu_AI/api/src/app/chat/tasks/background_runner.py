from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from typing import Any, Callable, Optional

from app.chat.tasks.task_store import TaskStore, get_task_store
from app.chat.tasks.progress import set_progress_callback, clear_progress_callback
from app.services.job_store import (
    ACTIVE_JOB_STATUSES,
    JobKind,
    JobStatus,
    create_job,
    get_job,
    update_job,
)
from core.course_storage import (
    reset_generation_persistence_context,
    set_generation_persistence_context,
)


_WORKFLOW_JOB_KINDS = {
    "report": JobKind.GENERATE_REPORT,
    "report_direct": JobKind.GENERATE_REPORT,
    "lesson_plan": JobKind.GENERATE_LESSON_PLAN,
    "blog": JobKind.GENERATE_BLOG,
    "quiz": JobKind.GENERATE_QUIZ,
    "quiz_direct": JobKind.GENERATE_QUIZ,
    "ppt": JobKind.GENERATE_PPT,
    "flashcard": JobKind.GENERATE_FLASHCARD,
    "game": JobKind.GENERATE_GAME,
    "game_direct": JobKind.GENERATE_GAME,
}


def _inject_trace(result: Any, total_ms: int) -> Any:
    """Attach trace_id and total_ms to any result dict that carries a trace."""
    if not isinstance(result, dict):
        return result
    trace = dict(result.get("trace") or {})
    if not trace.get("trace_id"):
        trace["trace_id"] = str(uuid.uuid4())
    timings = dict(trace.get("timings") or {})
    timings["total_ms"] = total_ms
    trace["timings"] = timings
    return {**result, "trace": trace}


def _update_global_progress(task_id: str, progress: dict[str, Any]) -> None:
    job = get_job(task_id)
    if job is None or job.status not in ACTIVE_JOB_STATUSES:
        return
    raw_progress = progress.get("progress", progress.get("percent", job.progress))
    try:
        normalized_progress = max(0, min(99, int(float(raw_progress))))
    except (TypeError, ValueError):
        normalized_progress = job.progress
    step = str(
        progress.get("stage")
        or progress.get("step")
        or progress.get("status")
        or job.step
        or "running"
    )
    message = str(
        progress.get("message")
        or progress.get("label")
        or job.message
        or "正在后台生成"
    )
    update_job(
        task_id,
        status=JobStatus.RUNNING,
        step=step,
        progress=normalized_progress,
        message=message,
    )


def _result_ref(result: Any, course_id: Optional[str]) -> dict[str, Any]:
    reference: dict[str, Any] = {
        "resource_type": "course_material" if course_id else "generated_artifact",
    }
    if course_id:
        reference["course_id"] = course_id
    if not isinstance(result, dict):
        return reference
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = result.get("generated_files")
    first = artifacts[0] if isinstance(artifacts, list) and artifacts else None
    if isinstance(first, dict):
        material_id = first.get("material_id") or first.get("artifact_id") or first.get("id")
        material_type = first.get("material_type") or first.get("artifact_type") or first.get("type")
        if material_id:
            reference["material_id"] = str(material_id)
        if material_type:
            reference["material_type"] = str(material_type)
    return reference


def _update_task_progress(
    task_store: TaskStore, task_id: str, progress: dict[str, Any]
) -> None:
    task_store.update_progress(task_id, progress)
    _update_global_progress(task_id, progress)


def _mark_running(task_store: TaskStore, task_id: str) -> bool:
    task_store.mark_running(task_id)
    job = get_job(task_id)
    if job is None:
        return True
    if job.status not in ACTIVE_JOB_STATUSES:
        return False
    update_job(
        task_id,
        status=JobStatus.RUNNING,
        step="running",
        progress=max(job.progress, 1),
        message="正在后台生成",
    )
    return True


def _mark_complete(task_store: TaskStore, task_id: str, result: Any) -> None:
    job = get_job(task_id)
    if job is not None:
        update_job(
            task_id,
            status=JobStatus.SUCCEEDED,
            step="completed",
            progress=100,
            message="生成完成，结果已保存",
            result_ref=_result_ref(result, job.course_id),
        )
    task_store.mark_complete(task_id, result)


def _mark_failed(task_store: TaskStore, task_id: str, exc: Exception) -> None:
    error = str(exc)
    if get_job(task_id) is not None:
        update_job(
            task_id,
            status=JobStatus.FAILED,
            step="failed",
            message="生成失败",
            error_message=error,
        )
    task_store.mark_failed(task_id, error)


def _create_task(
    *,
    store: TaskStore,
    workflow_type: str,
    owner_user_id: Optional[str],
    course_id: Optional[str],
    scope_type: str,
    scope_id: Optional[str],
    input_summary: Optional[dict[str, Any]],
    on_complete: Optional[Callable],
) -> str:
    normalized_owner = str(owner_user_id or "").strip()
    kind = _WORKFLOW_JOB_KINDS.get(workflow_type)
    if not normalized_owner or kind is None:
        return store.create(workflow_type=workflow_type, on_complete=on_complete)
    normalized_summary = dict(input_summary or {})
    if not normalized_summary.get("config_snapshot_id"):
        serialized_summary = json.dumps(
            normalized_summary,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        normalized_summary["config_snapshot_id"] = (
            f"cfg_{hashlib.sha256(serialized_summary.encode('utf-8')).hexdigest()[:16]}"
        )
    job = create_job(
        kind=kind,
        owner_user_id=normalized_owner,
        course_id=course_id,
        scope_type=scope_type,
        scope_id=scope_id,
        input_summary=normalized_summary,
    )
    return store.create(
        task_id=job.edu_job_id,
        workflow_type=workflow_type,
        owner_user_id=normalized_owner,
        on_complete=on_complete,
    )


def _run_workflow_task(
    *,
    task_store: TaskStore,
    task_id: str,
    workflow: Any,
    request: Any,
    snapshot: Any,
    decision: Any,
) -> None:
    if not _mark_running(task_store, task_id):
        return
    set_progress_callback(lambda p: _update_task_progress(task_store, task_id, p))
    job = get_job(task_id)
    context_token = set_generation_persistence_context(
        owner_user_id=job.owner_user_id if job else None,
        source_job_id=task_id if job else None,
        config_snapshot_id=(
            str(job.input_summary.get("config_snapshot_id") or "").strip() or None
            if job
            else None
        ),
    )
    t_start = time.perf_counter()
    try:
        result = workflow.run(request=request, snapshot=snapshot, decision=decision)
        result = _inject_trace(result, round((time.perf_counter() - t_start) * 1000))
        _mark_complete(task_store, task_id, result)
    except Exception as exc:
        _mark_failed(task_store, task_id, exc)
    finally:
        reset_generation_persistence_context(context_token)
        clear_progress_callback()


def _run_callable_task(
    *,
    task_store: TaskStore,
    task_id: str,
    fn: Callable[[], Any],
) -> None:
    if not _mark_running(task_store, task_id):
        return
    set_progress_callback(lambda p: _update_task_progress(task_store, task_id, p))
    job = get_job(task_id)
    context_token = set_generation_persistence_context(
        owner_user_id=job.owner_user_id if job else None,
        source_job_id=task_id if job else None,
        config_snapshot_id=(
            str(job.input_summary.get("config_snapshot_id") or "").strip() or None
            if job
            else None
        ),
    )
    t_start = time.perf_counter()
    try:
        result = fn()
        result = _inject_trace(result, round((time.perf_counter() - t_start) * 1000))
        _mark_complete(task_store, task_id, result)
    except Exception as exc:
        _mark_failed(task_store, task_id, exc)
    finally:
        reset_generation_persistence_context(context_token)
        clear_progress_callback()


def submit_workflow_task(
    *,
    workflow: Any,
    request: Any,
    snapshot: Any,
    decision: Any,
    workflow_type: str = "",
    owner_user_id: Optional[str] = None,
    course_id: Optional[str] = None,
    scope_type: str = "course",
    scope_id: Optional[str] = None,
    input_summary: Optional[dict[str, Any]] = None,
    on_complete: Optional[Callable] = None,
) -> str:
    """Submit a workflow object (with .run(request, snapshot, decision)) as a background task."""
    store = get_task_store()
    request_owner = owner_user_id or getattr(request, "owner", None)
    request_course_id = course_id or getattr(request, "course_id", None)
    request_scope_type = getattr(request, "scope_type", None) or scope_type
    request_scope_id = scope_id or getattr(request, "scope_id", None)
    summary = dict(input_summary or {})
    if not summary:
        summary["title"] = str(
            getattr(request, "question", None)
            or getattr(request, "message", None)
            or workflow_type
        )[:160]
    task_id = _create_task(
        store=store,
        workflow_type=workflow_type,
        owner_user_id=request_owner,
        course_id=request_course_id,
        scope_type=request_scope_type,
        scope_id=request_scope_id,
        input_summary=summary,
        on_complete=on_complete,
    )
    threading.Thread(
        target=_run_workflow_task,
        kwargs=dict(
            task_store=store,
            task_id=task_id,
            workflow=workflow,
            request=request,
            snapshot=snapshot,
            decision=decision,
        ),
        daemon=True,
    ).start()
    return task_id


def submit_callable_task(
    *,
    fn: Callable[[], Any],
    workflow_type: str = "",
    owner_user_id: Optional[str] = None,
    course_id: Optional[str] = None,
    scope_type: str = "course",
    scope_id: Optional[str] = None,
    input_summary: Optional[dict[str, Any]] = None,
    on_complete: Optional[Callable] = None,
) -> str:
    """Submit any zero-argument callable as a background task.

    Equivalent to submit_workflow_task but accepts an arbitrary callable
    instead of a workflow object. Progress callback and trace injection are
    applied identically.
    """
    store = get_task_store()
    task_id = _create_task(
        store=store,
        workflow_type=workflow_type,
        owner_user_id=owner_user_id,
        course_id=course_id,
        scope_type=scope_type,
        scope_id=scope_id,
        input_summary=input_summary,
        on_complete=on_complete,
    )
    threading.Thread(
        target=_run_callable_task,
        kwargs=dict(task_store=store, task_id=task_id, fn=fn),
        daemon=True,
    ).start()
    return task_id
