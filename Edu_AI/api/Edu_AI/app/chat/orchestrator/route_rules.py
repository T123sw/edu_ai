from __future__ import annotations

from app.chat.domain.route_decision import RouteDecision

from .workflow_interrupts import interrupt_reason, is_rewrite_command, should_interrupt_workflow


ACTION_TO_WORKFLOW = {
    "generate.report": "report",
    "generate.lesson_plan": "lesson_plan",
    "research.lookup": "research",
}

_REPORT_CONTINUE_MARKERS = {
    "继续",
    "开始",
    "确认",
    "确认并继续",
    "开始生成",
    "开始生成报告",
    "开始生成正文",
    "根据大纲开始生成报告",
    "按已确认的大纲开始生成报告",
}


def _normalized_text(value: str) -> str:
    return str(value or "").strip().lower().strip("。！？!?.,，；;:：")


def _snapshot_active_context(snapshot) -> dict:
    return dict(getattr(snapshot, "active_context", {}) or {}) if snapshot is not None else {}


def _snapshot_memory(snapshot) -> dict:
    return dict(getattr(snapshot, "conversation_memory", {}) or {}) if snapshot is not None else {}


def _snapshot_active_artifact_type(snapshot) -> str:
    active_context = _snapshot_active_context(snapshot)
    active_artifact_type = str(active_context.get("active_artifact_type") or "").strip()
    if active_artifact_type:
        return active_artifact_type
    active_artifact = getattr(snapshot, "active_artifact", None) if snapshot is not None else None
    return str(getattr(active_artifact, "artifact_type", "") or "").strip()


def _is_report_followup(question: str, snapshot) -> bool:
    normalized = _normalized_text(question)
    if not normalized:
        return False

    active_context = _snapshot_active_context(snapshot)
    active_artifact_type = _snapshot_active_artifact_type(snapshot)
    memory = _snapshot_memory(snapshot)

    report_goal = any(
        "报告" in str(item or "")
        for item in list(memory.get("user_goals") or [])
        + list(memory.get("explicit_user_goals") or [])
        + [memory.get("derived_workflow_goal")]
    )
    report_context_active = (
        str(active_context.get("active_workflow_type") or "").strip() == "report"
        and str(active_context.get("active_workflow_status") or "").strip() in {"running", "awaiting_confirm"}
    )
    report_artifact_active = active_artifact_type in {"report_outline", "report"}

    if not (report_goal or report_context_active or report_artifact_active):
        return False

    if normalized in _REPORT_CONTINUE_MARKERS:
        return True
    if "大纲" in normalized and any(token in normalized for token in ("继续", "开始", "确认", "生成")):
        return True
    if "正文" in normalized and any(token in normalized for token in ("继续", "开始", "生成")):
        return True
    return False


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

    active_context = _snapshot_active_context(snapshot)
    if (
        not workflow_state
        and not request.action_hint
        and str(active_context.get("active_workflow_type") or "").strip() == "report"
        and str(active_context.get("active_workflow_status") or "").strip() in {"running", "awaiting_confirm"}
        and _is_report_followup(request.question, snapshot)
    ):
        return RouteDecision(
            path="workflow",
            action="generate.report",
            workflow_name="report",
            reason="resume_active_report_context",
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

    if _is_report_followup(request.question, snapshot):
        return RouteDecision(
            path="workflow",
            action="generate.report",
            workflow_name="report",
            reason="report_followup_from_context",
        )

    if request.action_hint == "chat.rewrite":
        return RouteDecision.fast(action="chat.rewrite", reason="explicit_rewrite")

    return RouteDecision.fast(action="chat.reply", reason="default_fast_path")
