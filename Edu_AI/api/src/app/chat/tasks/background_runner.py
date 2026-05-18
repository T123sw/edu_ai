from __future__ import annotations

import threading
from typing import Any, Callable, Optional

from app.chat.tasks.task_store import TaskStore, get_task_store


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
    try:
        result = workflow.run(request=request, snapshot=snapshot, decision=decision)
        task_store.mark_complete(task_id, result)
    except Exception as exc:
        task_store.mark_failed(task_id, str(exc))


def submit_workflow_task(
    *,
    workflow: Any,
    request: Any,
    snapshot: Any,
    decision: Any,
    workflow_type: str = "",
    on_complete: Optional[Callable] = None,
) -> str:
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
