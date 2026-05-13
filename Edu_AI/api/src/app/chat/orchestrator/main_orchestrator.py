from __future__ import annotations

from .route_rules import decide_route


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

    def dispatch_stream(self, request):
        snapshot = self.context_builder.build(request)
        decision = decide_route(
            request=request,
            snapshot=snapshot,
            workflow_state=getattr(snapshot, "workflow_state", None),
        )
        if decision.path == "fast":
            yield from self.fast_runtime.run_stream(request=request, snapshot=snapshot, decision=decision)
            return

        yield {
            "type": "status",
            "payload": {
                "stage": "workflow_routing",
                "label": f"正在进入{decision.workflow_name or '工作流'}流程",
                "workflow": {"type": decision.workflow_name or "", "status": "running"},
            },
        }
        workflow = self.workflow_registry[decision.workflow_name]
        result = workflow.run(request=request, snapshot=snapshot, decision=decision)
        answer = str(((result.get("message") or {}).get("content")) or "")
        for index in range(0, len(answer), 24):
            yield {"type": "delta", "payload": {"content": answer[index:index + 24]}}
        yield {"type": "result", "payload": result}
