from __future__ import annotations

import re

from app.chat.debug_logging import append_debug_log
from app.chat.domain.route_decision import RouteDecision

from .workflow_interrupts import is_rewrite_command, should_interrupt_workflow


ACTION_TO_WORKFLOW = {
    "generate.report": "report",
    "generate.ppt": "ppt",
    "generate.lesson_plan": "lesson_plan",
    "generate.quiz": "quiz",
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

_PPT_CONTINUE_MARKERS = {
    "继续",
    "开始",
    "确认",
    "确认并继续",
    "确认并生成",
    "开始生成",
    "开始生成ppt",
    "开始生成课件",
    "按这个大纲生成",
    "就按这个生成",
}

_LESSON_PLAN_CONTINUE_MARKERS = {
    "继续",
    "确认",
    "确认并继续",
    "继续并生成",
    "按这个大纲继续",
    "按照大纲继续",
}

_QUIZ_CONTINUE_MARKERS = {
    "continue",
    "start",
    "confirm",
    "yes",
    "可以",
    "继续",
    "开始",
    "确认",
}

_LESSON_PLAN_REQUEST_MARKERS = {
    "教案",
    "教学设计",
    "lesson plan",
}

_QUIZ_REQUEST_MARKERS = {
    "quiz",
    "practice",
    "exercise",
    "test",
    "习题",
    "练习",
    "练习题",
    "测试",
    "测试题",
    "出题",
}

_QUIZ_SLOT_MARKERS = {
    "选择题",
    "填空题",
    "简答题",
    "判断题",
    "题量",
    "题型",
    "主题",
    "难度",
    "基础",
    "中等",
    "提高",
    "简单",
    "困难",
}


def _normalized_text(value: str) -> str:
    return str(value or "").strip().lower().strip("。！？?.!,，；;:")


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
    if isinstance(active_artifact, dict):
        return str(active_artifact.get("artifact_type") or "").strip()
    return str(getattr(active_artifact, "artifact_type", "") or "").strip()


def _log_ppt_route(*, request, snapshot, reason: str, workflow_state=None) -> None:
    append_debug_log(
        "ppt_workflow",
        event="route_decision",
        conversation_id=str(getattr(request, "conversation_id", "") or ""),
        question=str(getattr(request, "question", "") or ""),
        action_hint=str(getattr(request, "action_hint", "") or ""),
        reason=reason,
        workflow_type=str(getattr(workflow_state, "workflow_type", "") or ""),
        workflow_stage=str(getattr(workflow_state, "stage", "") or ""),
        active_workflow_type=str(_snapshot_active_context(snapshot).get("active_workflow_type") or ""),
        active_workflow_status=str(_snapshot_active_context(snapshot).get("active_workflow_status") or ""),
        active_artifact_type=_snapshot_active_artifact_type(snapshot),
    )


def _is_explicit_lesson_plan_request(question: str) -> bool:
    normalized = _normalized_text(question)
    if not normalized:
        return False
    return any(marker in normalized for marker in _LESSON_PLAN_REQUEST_MARKERS)


def _is_explicit_quiz_request(question: str) -> bool:
    normalized = _normalized_text(question)
    if not normalized:
        return False
    return any(marker in normalized for marker in _QUIZ_REQUEST_MARKERS)


def _looks_like_quiz_slot_answer(question: str) -> bool:
    text = str(question or "").strip()
    if not text:
        return False
    if bool(re.search(r"\d+", text)):
        return True
    return any(marker in text for marker in _QUIZ_SLOT_MARKERS)


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


def _is_ppt_followup(question: str, snapshot) -> bool:
    normalized = _normalized_text(question)
    if not normalized:
        return False

    active_context = _snapshot_active_context(snapshot)
    active_artifact_type = _snapshot_active_artifact_type(snapshot)
    memory = _snapshot_memory(snapshot)

    ppt_goal = any(
        any(marker in str(item or "").lower() for marker in ("ppt", "课件"))
        for item in list(memory.get("user_goals") or [])
        + list(memory.get("explicit_user_goals") or [])
        + [memory.get("derived_workflow_goal")]
    )
    ppt_context_active = (
        str(active_context.get("active_workflow_type") or "").strip() == "ppt"
        and str(active_context.get("active_workflow_status") or "").strip() in {"running", "awaiting_confirm"}
    )
    ppt_artifact_active = active_artifact_type in {"ppt_outline", "ppt_content_markdown", "ppt_deck"}

    if not (ppt_goal or ppt_context_active or ppt_artifact_active):
        return False

    if normalized in _PPT_CONTINUE_MARKERS:
        return True
    if "大纲" in normalized and any(token in normalized for token in ("继续", "开始", "确认", "生成")):
        return True
    if any(token in normalized for token in ("生成ppt", "生成课件", "导出ppt", "导出课件")):
        return True
    return False


def _is_lesson_plan_followup(question: str, snapshot) -> bool:
    normalized = _normalized_text(question)
    if not normalized:
        return False

    active_context = _snapshot_active_context(snapshot)
    active_artifact_type = _snapshot_active_artifact_type(snapshot)
    memory = _snapshot_memory(snapshot)

    lesson_plan_goal = any(
        any(marker in str(item or "").lower() for marker in ("教案", "lesson plan"))
        for item in list(memory.get("user_goals") or [])
        + list(memory.get("explicit_user_goals") or [])
        + [memory.get("derived_workflow_goal")]
    )
    lesson_plan_context_active = (
        str(active_context.get("active_workflow_type") or "").strip() == "lesson_plan"
        and str(active_context.get("active_workflow_status") or "").strip() in {"running", "awaiting_confirm"}
    )
    lesson_plan_artifact_active = active_artifact_type in {"lesson_plan_outline", "lesson_plan"}

    if not (lesson_plan_goal or lesson_plan_context_active or lesson_plan_artifact_active):
        return False

    if normalized in _LESSON_PLAN_CONTINUE_MARKERS:
        return True
    if "大纲" in normalized and any(token in normalized for token in ("继续", "确认", "开始", "生成")):
        return True
    if lesson_plan_artifact_active and any(token in normalized for token in ("继续", "确认", "开始", "生成")):
        return True
    return False


def _is_quiz_followup(question: str, snapshot) -> bool:
    normalized = _normalized_text(question)
    if not normalized:
        return False

    active_context = _snapshot_active_context(snapshot)
    active_artifact_type = _snapshot_active_artifact_type(snapshot)
    memory = _snapshot_memory(snapshot)

    quiz_goal = any(
        any(marker in str(item or "").lower() for marker in ("quiz", "practice", "exercise", "test"))
        or any(marker in str(item or "") for marker in ("习题", "练习", "练习题", "测试", "测试题"))
        for item in list(memory.get("user_goals") or [])
        + list(memory.get("explicit_user_goals") or [])
        + [memory.get("derived_workflow_goal")]
    )
    quiz_context_active = (
        str(active_context.get("active_workflow_type") or "").strip() == "quiz"
        and str(active_context.get("active_workflow_status") or "").strip() in {"running", "awaiting_confirm"}
    )
    quiz_artifact_active = active_artifact_type == "quiz"

    if not (quiz_goal or quiz_context_active or quiz_artifact_active):
        return False

    if normalized in _QUIZ_CONTINUE_MARKERS:
        return True
    if any(token in normalized for token in ("generate quiz", "start quiz", "生成习题", "生成练习题", "开始出题")):
        return True
    if quiz_context_active and _looks_like_quiz_slot_answer(question):
        return True
    if quiz_artifact_active and any(token in normalized for token in ("continue", "confirm", "start", "可以", "继续", "开始", "确认")):
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
        if str(getattr(workflow_state, "workflow_type", "") or "").strip() == "ppt":
            _log_ppt_route(request=request, snapshot=snapshot, reason="resume_workflow", workflow_state=workflow_state)
        return RouteDecision(
            path="workflow",
            action=workflow_state.workflow_type,
            workflow_name=workflow_state.workflow_type,
            reason="resume_workflow",
        )

    active_context = _snapshot_active_context(snapshot)
    active_workflow_type = str(active_context.get("active_workflow_type") or "").strip()
    active_workflow_status = str(active_context.get("active_workflow_status") or "").strip()

    if (
        not workflow_state
        and not request.action_hint
        and active_workflow_type == "report"
        and active_workflow_status in {"running", "awaiting_confirm"}
        and _is_report_followup(request.question, snapshot)
    ):
        return RouteDecision(
            path="workflow",
            action="generate.report",
            workflow_name="report",
            reason="resume_active_report_context",
        )

    if (
        not workflow_state
        and not request.action_hint
        and active_workflow_type == "ppt"
        and active_workflow_status in {"running", "awaiting_confirm"}
        and _is_ppt_followup(request.question, snapshot)
    ):
        _log_ppt_route(request=request, snapshot=snapshot, reason="resume_active_ppt_context", workflow_state=workflow_state)
        return RouteDecision(
            path="workflow",
            action="generate.ppt",
            workflow_name="ppt",
            reason="resume_active_ppt_context",
        )

    if (
        not workflow_state
        and not request.action_hint
        and active_workflow_type == "quiz"
        and active_workflow_status in {"running", "awaiting_confirm"}
        and _is_quiz_followup(request.question, snapshot)
    ):
        return RouteDecision(
            path="workflow",
            action="generate.quiz",
            workflow_name="quiz",
            reason="resume_active_quiz_context",
        )

    if request.action_hint == "generate.lesson_plan" or _is_explicit_lesson_plan_request(request.question):
        return RouteDecision(
            path="workflow",
            action="generate.lesson_plan",
            workflow_name="lesson_plan",
            reason="explicit_lesson_plan",
        )

    if request.action_hint == "generate.quiz" or _is_explicit_quiz_request(request.question):
        return RouteDecision(
            path="workflow",
            action="generate.quiz",
            workflow_name="quiz",
            reason="explicit_quiz",
        )

    if request.action_hint == "research.lookup":
        return RouteDecision(
            path="workflow",
            action="research.lookup",
            workflow_name="research",
            reason="explicit_research",
        )

    if request.action_hint == "generate.report" or "报告" in str(request.question or ""):
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

    question_text = str(request.question or "")
    if request.action_hint == "generate.ppt" or any(token in question_text.lower() for token in ("ppt", "课件")):
        _log_ppt_route(request=request, snapshot=snapshot, reason="explicit_ppt", workflow_state=workflow_state)
        return RouteDecision(
            path="workflow",
            action="generate.ppt",
            workflow_name="ppt",
            reason="explicit_ppt",
        )

    if _is_ppt_followup(request.question, snapshot):
        _log_ppt_route(request=request, snapshot=snapshot, reason="ppt_followup_from_context", workflow_state=workflow_state)
        return RouteDecision(
            path="workflow",
            action="generate.ppt",
            workflow_name="ppt",
            reason="ppt_followup_from_context",
        )

    if _is_lesson_plan_followup(request.question, snapshot):
        if (
            not workflow_state
            and not request.action_hint
            and active_workflow_type == "lesson_plan"
            and active_workflow_status in {"running", "awaiting_confirm"}
        ):
            return RouteDecision(
                path="workflow",
                action="generate.lesson_plan",
                workflow_name="lesson_plan",
                reason="resume_active_lesson_plan_context",
            )
        return RouteDecision(
            path="workflow",
            action="generate.lesson_plan",
            workflow_name="lesson_plan",
            reason="lesson_plan_followup_from_context",
        )

    if _is_quiz_followup(request.question, snapshot):
        return RouteDecision(
            path="workflow",
            action="generate.quiz",
            workflow_name="quiz",
            reason="quiz_followup_from_context",
        )

    if request.action_hint == "chat.rewrite":
        return RouteDecision.fast(action="chat.rewrite", reason="explicit_rewrite")

    return RouteDecision.fast(action="chat.reply", reason="default_fast_path")
