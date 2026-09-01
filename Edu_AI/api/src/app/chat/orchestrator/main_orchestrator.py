from __future__ import annotations

from typing import Any, Callable, Optional

from core.config import Config
from .route_rules import decide_route

_WORKFLOW_LABELS = {
    "report": "报告",
    "lesson_plan": "教案",
    "quiz": "练习题",
}

_HINT_TO_WORKFLOW = {
    "generate.report":      "report",
    "generate.lesson_plan": "lesson_plan",
    "generate.quiz":        "quiz",
    "research.lookup":      "research",
}


class MainOrchestrator:
    def __init__(self, *, fast_runtime, workflow_registry, context_builder,
                 react_agent=None):
        self.fast_runtime = fast_runtime
        self.workflow_registry = workflow_registry
        self.context_builder = context_builder
        self.react_agent = react_agent

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
        action_hint = str(getattr(request, "action_hint", "") or "")

        # Level 1: action_hint explicitly set → full workflow path (unchanged behaviour)
        if action_hint and action_hint in _HINT_TO_WORKFLOW:
            workflow_name = _HINT_TO_WORKFLOW[action_hint]
            if workflow_name not in self.workflow_registry:
                yield from self.fast_runtime.run_stream(
                    request=request,
                    snapshot=snapshot,
                    decision=_fast(action="chat.reply", reason="workflow_unregistered"),
                )
                return
            yield from self._dispatch_workflow(request, snapshot, workflow_name, on_workflow_complete)
            return

        # Level 2: ReAct agent path
        if self.react_agent is not None and Config.USE_REACT_AGENT:
            yield from self.react_agent.run_stream(request=request, snapshot=snapshot)
            return

        # Fallback: legacy route_rules (USE_REACT_AGENT=false or no react_agent)
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
                decision=_fast(action="chat.reply", reason="workflow_unregistered_fallback"),
            )
            return
        yield from self._dispatch_workflow(request, snapshot, decision.workflow_name, on_workflow_complete)

    def _dispatch_workflow(self, request, snapshot, workflow_name: str, on_workflow_complete):
        from app.chat.tasks.background_runner import submit_workflow_task
        from app.chat.domain.route_decision import RouteDecision

        label = _WORKFLOW_LABELS.get(workflow_name, "内容")
        decision = RouteDecision(
            path="workflow",
            action=f"generate.{workflow_name}",
            workflow_name=workflow_name,
            reason="level1_action_hint",
        )
        task_id = submit_workflow_task(
            workflow=self.workflow_registry[workflow_name],
            request=request,
            snapshot=snapshot,
            decision=decision,
            workflow_type=workflow_name,
            on_complete=on_workflow_complete,
        )
        yield {
            "type": "status",
            "payload": {
                "stage": "task_queued",
                "label": f"{label}生成任务已提交，正在后台处理...",
                "workflow": {"type": workflow_name, "status": "running"},
            },
        }
        yield {
            "type": "task_submitted",
            "payload": {
                "task_id": task_id,
                "workflow_type": workflow_name,
                "message": f"正在后台生成{label}，可通过任务ID查询进度",
            },
        }


def _fast(*, action: str, reason: str):
    from app.chat.domain.route_decision import RouteDecision
    return RouteDecision.fast(action=action, reason=reason)
