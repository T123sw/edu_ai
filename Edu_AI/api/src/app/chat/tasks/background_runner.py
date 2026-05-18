from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable, Optional

from app.chat.tasks.task_store import TaskStore, get_task_store
from app.chat.tasks.progress import set_progress_callback, clear_progress_callback


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


def _run_workflow_task(
    *,
    task_store: TaskStore,
    task_id: str,
    workflow: Any,
    request: Any,
    snapshot: Any,
    decision: Any,
) -> None:
    task_store.mark_running(task_id)
    set_progress_callback(lambda p: task_store.update_progress(task_id, p))
    t_start = time.perf_counter()
    try:
        result = workflow.run(request=request, snapshot=snapshot, decision=decision)
        result = _inject_trace(result, round((time.perf_counter() - t_start) * 1000))
        task_store.mark_complete(task_id, result)
    except Exception as exc:
        task_store.mark_failed(task_id, str(exc))
    finally:
        clear_progress_callback()


def _run_callable_task(
    *,
    task_store: TaskStore,
    task_id: str,
    fn: Callable[[], Any],
) -> None:
    task_store.mark_running(task_id)
    set_progress_callback(lambda p: task_store.update_progress(task_id, p))
    t_start = time.perf_counter()
    try:
        result = fn()
        result = _inject_trace(result, round((time.perf_counter() - t_start) * 1000))
        task_store.mark_complete(task_id, result)
    except Exception as exc:
        task_store.mark_failed(task_id, str(exc))
    finally:
        clear_progress_callback()


def submit_workflow_task(
    *,
    workflow: Any,
    request: Any,
    snapshot: Any,
    decision: Any,
    workflow_type: str = "",
    on_complete: Optional[Callable] = None,
) -> str:
    """Submit a workflow object (with .run(request, snapshot, decision)) as a background task."""
    store = get_task_store()
    task_id = store.create(workflow_type=workflow_type, on_complete=on_complete)
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
    on_complete: Optional[Callable] = None,
) -> str:
    """Submit any zero-argument callable as a background task.

    Equivalent to submit_workflow_task but accepts an arbitrary callable
    instead of a workflow object. Progress callback and trace injection are
    applied identically.
    """
    store = get_task_store()
    task_id = store.create(workflow_type=workflow_type, on_complete=on_complete)
    threading.Thread(
        target=_run_callable_task,
        kwargs=dict(task_store=store, task_id=task_id, fn=fn),
        daemon=True,
    ).start()
    return task_id
