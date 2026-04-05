from __future__ import annotations

from app.chat.domain.route_decision import RouteDecision

from .workflow_interrupts import interrupt_reason, is_rewrite_command, should_interrupt_workflow


ACTION_TO_WORKFLOW = {
    "generate.report": "report",
    "generate.lesson_plan": "lesson_plan",
    "research.lookup": "research",
}


def decide_route(*, request, snapshot, workflow_state):
    if snapshot and getattr(snapshot, "active_artifact", None) and is_rewrite_command(request.question):
        return RouteDecision.fast(action="chat.rewrite", reason="active_artifact_rewrite")

    interrupted = bool(workflow_state and should_interrupt_workflow(request.question))
    if interrupted and request.action_hint in ACTION_TO_WORKFLOW:
        return RouteDecision(
            path="workflow",
            action=request.action_hint,
            workflow_name=ACTION_TO_WORKFLOW[request.action_hint],
            reason=f"explicit_{ACTION_TO_WORKFLOW[request.action_hint]}",
        )

    if interrupted:
        return RouteDecision.fast(action="chat.reply", reason="interrupt_to_chat")

    if workflow_state and not should_interrupt_workflow(request.question) and not request.action_hint:
        return RouteDecision(
            path="workflow",
            action=workflow_state.workflow_type,
            workflow_name=workflow_state.workflow_type,
            reason="resume_workflow",
        )

    if request.action_hint == "generate.lesson_plan":
        return RouteDecision(
            path="workflow",
            action="generate.lesson_plan",
            workflow_name="lesson_plan",
            reason="explicit_lesson_plan",
        )

    if request.action_hint == "research.lookup":
        return RouteDecision(
            path="workflow",
            action="research.lookup",
            workflow_name="research",
            reason="explicit_research",
        )

    if request.action_hint == "generate.report" or "报告" in request.question:
        return RouteDecision(
            path="workflow",
            action="generate.report",
            workflow_name="report",
            reason="explicit_report",
        )

    if request.action_hint == "chat.rewrite":
        return RouteDecision.fast(action="chat.rewrite", reason="explicit_rewrite")

    return RouteDecision.fast(action="chat.reply", reason="default_fast_path")
