from __future__ import annotations

from typing import Any, Callable, Optional

from .route_rules import decide_route

_WORKFLOW_LABELS = {
    "report": "报告",
    "ppt": "PPT课件",
    "lesson_plan": "教案",
    "quiz": "练习题",
}


class MainOrchestrator:
    def __init__(self, *, fast_runtime, workflow_registry, context_builder):
        self.fast_runtime = fast_runtime
        self.workflow_registry = workflow_registry
        self.context_builder = context_builder

    def dispatch(self, request):
        snapshot = self.context_builder.build(request)
        decision = decide_route(
            request=request,
            snapshot=snapshot,
            workflow_state=getattr(snapshot, "workflow_state", None),
        )
        if decision.path == "fast":
            return self.fast_runtime.run(request=request, snapshot=snapshot, decision=decision)

        workflow = self.workflow_registry[decision.workflow_name]
        return workflow.run(request=request, snapshot=snapshot, decision=decision)

    def dispatch_stream(self, request, *, on_workflow_complete: Optional[Callable] = None):
        snapshot = self.context_builder.build(request)
        decision = decide_route(
            request=request,
            snapshot=snapshot,
            workflow_state=getattr(snapshot, "workflow_state", None),
        )
        if decision.path == "fast":
            yield from self.fast_runtime.run_stream(request=request, snapshot=snapshot, decision=decision)
            return

        if decision.workflow_name not in self.workflow_registry:
            yield from self.fast_runtime.run_stream(
                request=request,
                snapshot=snapshot,
                decision=decision.__class__.fast(action="chat.reply", reason="workflow_unregistered_fallback"),
            )
            return

        from app.chat.tasks.background_runner import submit_workflow_task

        label = _WORKFLOW_LABELS.get(decision.workflow_name, "内容")
        task_id = submit_workflow_task(
            workflow=self.workflow_registry[decision.workflow_name],
            request=request,
            snapshot=snapshot,
            decision=decision,
            workflow_type=decision.workflow_name,
            on_complete=on_workflow_complete,
        )

        yield {
            "type": "status",
            "payload": {
                "stage": "task_queued",
                "label": f"{label}生成任务已提交，正在后台处理...",
                "workflow": {"type": decision.workflow_name, "status": "running"},
            },
        }
        yield {
            "type": "task_submitted",
            "payload": {
                "task_id": task_id,
                "workflow_type": decision.workflow_name,
                "message": f"正在后台生成{label}，可通过任务ID查询进度",
            },
        }
