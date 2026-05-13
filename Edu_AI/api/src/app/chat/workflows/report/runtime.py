from __future__ import annotations

import json
from typing import Any

from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.generation_readiness_judge import GenerationReadinessJudge
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.orchestrator.report_context_organizer import ReportContextOrganizer
from core.config import Config

from .assembler import ReportAssembler


def _normalize_workflow_status(raw_status):
    status = str(raw_status or "running").strip().lower()
    mapping = {
        "awaiting_human": "awaiting_confirm",
        "finished": "completed",
    }
    return mapping.get(status, status or "running")


def _parse_env_toggle(raw: str) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes"}


_TRACE_ENABLED = _parse_env_toggle(getattr(Config, "UNIVERSAL_REPORT_TRACE", "0"))
_BUTTON_LIKE_QUESTIONS = {
    "generate report",
    "生成报告",
    "请生成报告",
    "帮我生成报告",
}
_AFFIRMATIVE_TOKENS = {
    "可以",
    "可以开始",
    "开始",
    "继续",
    "确认",
    "确认并继续",
    "好",
    "好的",
    "行",
    "没问题",
    "ok",
    "yes",
}


def _trim_preview(value: str, *, limit: int = 120) -> str:
    text = str(value or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _detect_entry_mode(request) -> str:
    action_hint = str(getattr(request, "action_hint", "") or "").strip()
    if action_hint == "generate.report":
        return "button"
    normalized_question = str(getattr(request, "question", "") or "").strip().lower()
    if normalized_question in _BUTTON_LIKE_QUESTIONS:
        return "button"
    return "reply"


def _is_affirmative_reply(text: str) -> bool:
    normalized = str(text or "").strip().lower().strip("。！？!?.,，；;:：")
    if not normalized:
        return False
    return normalized in _AFFIRMATIVE_TOKENS


def _build_soft_confirm_fallback_message(*, report_subject: str, report_focus: str) -> str:
    subject = str(report_subject or "").strip() or "当前主题"
    focus = str(report_focus or "").strip() or f"围绕“{subject}”形成一版结构化分析"
    return f"我将基于“{subject}”，重点围绕“{focus}”，结合当前对话内容先生成一版报告。可以直接开始吗？"


def _build_runtime_trace_payload(*, state: dict[str, Any]) -> dict[str, Any]:
    gathered_context = dict(state.get("gathered_context") or {})
    recent_messages = list(gathered_context.get("recent_messages") or [])
    evidence_points = list(gathered_context.get("evidence_points") or [])
    report_preparation_result = dict(state.get("report_preparation_result") or {})
    readiness_decision = dict(state.get("readiness_decision") or {})
    return {
        "conversation_id": str(state.get("conversation_id") or ""),
        "owner": state.get("owner"),
        "allow_rag": bool(state.get("allow_rag")),
        "allow_web": bool(state.get("allow_web")),
        "selected_doc_ids": list(state.get("selected_doc_ids") or []),
        "summary": str(gathered_context.get("summary") or ""),
        "current_topics": list(gathered_context.get("current_topics") or []),
        "user_goals": list(gathered_context.get("user_goals") or []),
        "confirmed_facts": list(gathered_context.get("confirmed_facts") or []),
        "constraints": dict(gathered_context.get("constraints") or {}),
        "teaching_issues": list(gathered_context.get("teaching_issues") or []),
        "student_signals": list(gathered_context.get("student_signals") or []),
        "evidence_points": evidence_points,
        "evidence_count": len(evidence_points),
        "slot_hints": dict(gathered_context.get("slot_hints") or {}),
        "context_digest": str(gathered_context.get("context_digest") or ""),
        "current_course_id": gathered_context.get("current_course_id"),
        "referenced_artifact_ids": list(gathered_context.get("referenced_artifact_ids") or []),
        "active_artifact": dict(gathered_context.get("active_artifact") or {}),
        "source_scope": dict(gathered_context.get("source_scope") or {}),
        "recent_message_count": len(recent_messages),
        "report_preparation_result": report_preparation_result,
        "readiness_decision": readiness_decision,
        "recent_message_preview": [
            {
                "role": str((message or {}).get("role") or ""),
                "content": _trim_preview((message or {}).get("content") or ""),
            }
            for message in recent_messages[-3:]
            if isinstance(message, dict)
        ],
    }


def _trace_context_injection(state: dict[str, Any]) -> None:
    if not _TRACE_ENABLED:
        return
    payload = _build_runtime_trace_payload(state=state)
    print("[报告工作流] report_context_injection")
    print(f"  - conversation_id={payload['conversation_id']}")
    print(
        "  - topics={topics} goals={goals} facts={facts} issues={issues} signals={signals} evidence={evidence}".format(
            topics=len(payload["current_topics"]),
            goals=len(payload["user_goals"]),
            facts=len(payload["confirmed_facts"]),
            issues=len(payload["teaching_issues"]),
            signals=len(payload["student_signals"]),
            evidence=payload["evidence_count"],
        )
    )
    if payload["report_preparation_result"]:
        print(
            "  - preparation_source={source} model={model}".format(
                source=str(payload["report_preparation_result"].get("preparation_source") or ""),
                model=str(payload["report_preparation_result"].get("preparation_model") or ""),
            )
        )
    print(f"  - recent_message_count={payload['recent_message_count']}")
    print(f"  - slot_hint_keys={list(payload['slot_hints'].keys())}")
    print(f"  - 数据: {json.dumps(payload, ensure_ascii=False)}")


def _build_report_slots(*, gathered_context: dict[str, Any], preparation_payload: dict[str, Any] | None = None, stored_filled_slots: dict[str, Any] | None = None) -> dict[str, Any]:
    slot_hints = dict((gathered_context or {}).get("slot_hints") or {})
    report_slots = {
        "core_topic": str(slot_hints.get("core_topic") or "").strip(),
        "focus_area": str(slot_hints.get("focus_area") or "").strip(),
        "length_requirement": str(slot_hints.get("length_requirement") or "").strip(),
        "depth_level": str(slot_hints.get("depth_level") or "").strip(),
        "format_style": str(slot_hints.get("format_style") or "").strip(),
        "dynamic_constraints": str(slot_hints.get("dynamic_constraints") or "").strip(),
    }
    filled = dict(stored_filled_slots or {})
    if str(filled.get("core_topic") or "").strip():
        report_slots["core_topic"] = str(filled.get("core_topic") or "").strip()
    if str(filled.get("focus_area") or "").strip():
        report_slots["focus_area"] = str(filled.get("focus_area") or "").strip()
    preparation = dict(preparation_payload or {})
    if str(preparation.get("report_subject") or "").strip():
        report_slots["core_topic"] = str(preparation.get("report_subject") or "").strip()
    if str(preparation.get("report_focus") or "").strip():
        report_slots["focus_area"] = str(preparation.get("report_focus") or "").strip()
    return report_slots


def _is_outline_continue_reply(text: str) -> bool:
    normalized = str(text or "").strip().lower().strip("。！？!?.,，；;:：")
    if not normalized:
        return False
    if normalized in {
        "确认并继续",
        "确认大纲并继续",
        "根据已确认的大纲开始生成报告",
        "按已确认的大纲开始生成报告",
        "根据大纲开始生成报告",
        "开始生成报告",
        "开始生成正文",
    }:
        return True
    return _is_affirmative_reply(normalized)


def _extract_outline_artifact_content(workflow_state: Any) -> list[dict[str, Any]]:
    artifacts = list(getattr(workflow_state, "artifacts", []) or [])
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("artifact_type") or "").strip() != "report_outline":
            continue
        content = artifact.get("content")
        if isinstance(content, list):
            return content
    return []


def _build_soft_confirm_message(*, report_subject: str, report_focus: str) -> str:
    subject = str(report_subject or "").strip() or "当前主题"
    focus = str(report_focus or "").strip() or f"围绕“{subject}”形成一版结构化分析"
    return (
        f"我准备基于“{subject}”，重点围绕“{focus}”，"
        "先生成一版结构清晰的报告。"
        "如果这个方向可以，我就继续开始。"
    )


def _normalize_soft_confirm_message(*, message: str, report_subject: str, report_focus: str) -> str:
    raw = str(message or "").strip()
    if not raw:
        return _build_soft_confirm_message(
            report_subject=report_subject,
            report_focus=report_focus,
        )
    if any(marker in raw for marker in ("已识别用户请求", "提取了完整", "基于详细的对话历史", "report")):
        return _build_soft_confirm_message(
            report_subject=report_subject,
            report_focus=report_focus,
        )
    return raw


class ReportWorkflowRuntime:
    def __init__(
        self,
        *,
        engine=None,
        engine_factory=None,
        engine_resolver=None,
        generation_context_builder=None,
        report_assembler=None,
        report_context_organizer=None,
        generation_readiness_judge=None,
    ):
        self._engine = engine
        self._engine_factory = engine_factory
        self._engine_resolver = engine_resolver
        self.generation_context_builder = generation_context_builder or GenerationContextBuilder()
        self.report_assembler = report_assembler or ReportAssembler()
        self.report_context_organizer = report_context_organizer or ReportContextOrganizer()
        self.generation_readiness_judge = generation_readiness_judge or GenerationReadinessJudge()

    @property
    def engine(self):
        if self._engine is None and self._engine_factory is not None:
            self._engine = self._engine_factory()
        return self._engine

    def run(self, *, request, snapshot, decision):
        engine = self.engine
        if self._engine_resolver is not None:
            engine = self._engine_resolver(request=request, snapshot=snapshot, decision=decision)

        if engine is None:
            raise KeyError("report")
        capability = getattr(request, "capability", None)
        gathered_context = {}
        generation_context = GenerationContext(
            conversation_id=request.conversation_id or "",
            resource_type="report",
        )
        if snapshot is not None:
            generation_context = self.generation_context_builder.build_for_resource(
                request=request,
                snapshot=snapshot,
                resource_type="report",
            )
            gathered_context = self.report_assembler.from_generation_context(generation_context)
            gathered_context["active_task"] = getattr(snapshot, "active_task", None)
        workflow_state = getattr(snapshot, "workflow_state", None) if snapshot is not None else None
        if (
            workflow_state is not None
            and str(getattr(workflow_state, "workflow_type", "") or "").strip() == "report"
            and str(getattr(workflow_state, "status", "") or "").strip() == "awaiting_confirm"
        ):
            stored_filled_slots = dict(getattr(workflow_state, "filled_slots", {}) or {})
            workflow_stage = str(getattr(workflow_state, "stage", "") or "").strip()
            can_resume = (_is_affirmative_reply(request.question) and workflow_stage == "soft_confirm") or (
                _is_affirmative_reply(request.question)
                and workflow_stage == "critical_gap"
                and (
                    str(stored_filled_slots.get("core_topic") or "").strip()
                    or str(stored_filled_slots.get("focus_area") or "").strip()
                )
            )
            if can_resume:
                resume_preparation = {
                    "report_subject": str(stored_filled_slots.get("core_topic") or "").strip(),
                    "report_focus": str(stored_filled_slots.get("focus_area") or "").strip(),
                    "preparation_source": str(stored_filled_slots.get("__preparation_source") or "").strip(),
                    "preparation_model": str(stored_filled_slots.get("__preparation_model") or "").strip(),
                }
                resume_state = {
                    "user_input": request.question,
                    "report_state": workflow_state,
                    "conversation_id": request.conversation_id or "",
                    "owner": getattr(request, "owner", None),
                    "allow_rag": bool(getattr(capability, "allow_rag", False)),
                    "allow_web": bool(getattr(capability, "allow_web", False)),
                    "selected_doc_ids": list(getattr(capability, "selected_doc_ids", []) or []),
                    "gathered_context": gathered_context,
                    "report_preparation_result": resume_preparation,
                    "readiness_decision": {"action": "resume_after_soft_confirm", "missing_critical_fields": []},
                    "report_slots": _build_report_slots(
                        gathered_context=gathered_context,
                        stored_filled_slots=stored_filled_slots,
                    ),
                    "soft_confirmed": True,
                    "generation_ready": True,
                }
                _trace_context_injection(resume_state)
                raw = engine.invoke(resume_state)
                message_content = (
                    raw.get("reply")
                    or raw.get("final_response")
                    or raw.get("report_content")
                    or ""
                )
                workflow_status = _normalize_workflow_status(raw.get("status", "running"))
                workflow = {"type": "report", "status": workflow_status}
                if raw.get("phase"):
                    workflow["phase"] = raw.get("phase")
                artifacts = raw.get("artifacts")
                if artifacts is None:
                    artifacts = []
                    if raw.get("report_outline"):
                        artifacts.append(
                            {
                                "artifact_id": f"{request.conversation_id or 'report'}:outline",
                                "artifact_type": "report_outline",
                                "content": raw.get("report_outline"),
                            }
                        )
                    if raw.get("report_content"):
                        artifacts.append(
                            {
                                "artifact_id": f"{request.conversation_id or 'report'}:content",
                                "artifact_type": "report",
                                "content": raw.get("report_content"),
                            }
                        )
                return {
                    "message": {"role": "assistant", "content": message_content},
                    "conversation": {"conversation_id": request.conversation_id or ""},
                    "action": {"name": "generate.report"},
                    "artifacts": artifacts,
                    "workflow": workflow,
                    "sources": raw.get("sources", []),
                    "trace": {
                        "path": "workflow",
                        "workflow_name": "report",
                        "readiness_decision": {"action": "resume_after_soft_confirm", "missing_critical_fields": []},
                    },
                }
            can_resume = _is_outline_continue_reply(request.question) and workflow_stage == "outlining" and bool(
                _extract_outline_artifact_content(workflow_state)
            )
            if can_resume:
                outline_content = _extract_outline_artifact_content(workflow_state)
                resume_preparation = {
                    "report_subject": str(stored_filled_slots.get("core_topic") or "").strip(),
                    "report_focus": str(stored_filled_slots.get("focus_area") or "").strip(),
                    "preparation_source": str(stored_filled_slots.get("__preparation_source") or "").strip(),
                    "preparation_model": str(stored_filled_slots.get("__preparation_model") or "").strip(),
                }
                resume_state = {
                    "user_input": request.question,
                    "human_feedback": "确认",
                    "report_state": workflow_state,
                    "conversation_id": request.conversation_id or "",
                    "owner": getattr(request, "owner", None),
                    "allow_rag": bool(getattr(capability, "allow_rag", False)),
                    "allow_web": bool(getattr(capability, "allow_web", False)),
                    "selected_doc_ids": list(getattr(capability, "selected_doc_ids", []) or []),
                    "gathered_context": gathered_context,
                    "report_preparation_result": resume_preparation,
                    "readiness_decision": {"action": "resume_after_outline_confirm", "missing_critical_fields": []},
                    "report_slots": _build_report_slots(
                        gathered_context=gathered_context,
                        stored_filled_slots=stored_filled_slots,
                    ),
                    "report_outline": outline_content,
                    "soft_confirmed": True,
                    "generation_ready": True,
                }
                _trace_context_injection(resume_state)
                raw = engine.invoke(resume_state)
                message_content = (
                    raw.get("reply")
                    or raw.get("final_response")
                    or raw.get("report_content")
                    or ""
                )
                workflow_status = _normalize_workflow_status(raw.get("status", "running"))
                workflow = {"type": "report", "status": workflow_status}
                if raw.get("phase"):
                    workflow["phase"] = raw.get("phase")
                artifacts = raw.get("artifacts")
                if artifacts is None:
                    artifacts = []
                    if raw.get("report_outline"):
                        artifacts.append(
                            {
                                "artifact_id": f"{request.conversation_id or 'report'}:outline",
                                "artifact_type": "report_outline",
                                "content": raw.get("report_outline"),
                            }
                        )
                    if raw.get("report_content"):
                        artifacts.append(
                            {
                                "artifact_id": f"{request.conversation_id or 'report'}:content",
                                "artifact_type": "report",
                                "content": raw.get("report_content"),
                            }
                        )
                return {
                    "message": {"role": "assistant", "content": message_content},
                    "conversation": {"conversation_id": request.conversation_id or ""},
                    "action": {"name": "generate.report"},
                    "artifacts": artifacts,
                    "workflow": workflow,
                    "sources": raw.get("sources", []),
                    "trace": {
                        "path": "workflow",
                        "workflow_name": "report",
                        "readiness_decision": {"action": "resume_after_outline_confirm", "missing_critical_fields": []},
                    },
                }
        preparation = self.report_context_organizer.organize(
            context=generation_context,
            request_question=request.question,
        )
        entry_mode = _detect_entry_mode(request)
        readiness_decision = self.generation_readiness_judge.judge(preparation, entry_mode=entry_mode)
        readiness_action = str(readiness_decision.get("action") or "").strip()
        if readiness_action in {"strong_soft_confirm", "ask_critical_gap"}:
            trace_state = {
                "conversation_id": request.conversation_id or "",
                "owner": getattr(request, "owner", None),
                "allow_rag": bool(getattr(capability, "allow_rag", False)),
                "allow_web": bool(getattr(capability, "allow_web", False)),
                "selected_doc_ids": list(getattr(capability, "selected_doc_ids", []) or []),
                "gathered_context": gathered_context,
                "report_preparation_result": preparation.model_dump(exclude_none=True),
                "readiness_decision": readiness_decision,
            }
            _trace_context_injection(trace_state)
            workflow_phase = "soft_confirm" if readiness_action == "strong_soft_confirm" else "critical_gap"
            message_content = str(preparation.soft_confirm_message or "").strip()
            if readiness_action == "strong_soft_confirm":
                message_content = _normalize_soft_confirm_message(
                    message=message_content,
                    report_subject=str(preparation.report_subject or "").strip(),
                    report_focus=str(preparation.report_focus or "").strip(),
                )
            if readiness_action == "ask_critical_gap":
                followups = list(preparation.followup_candidates or [])
                message_content = str((followups[0] if followups else "") or "").strip()
                if not message_content:
                    missing = str(((readiness_decision.get("missing_critical_fields") or [""])[0]) or "").strip()
                    if missing == "report_subject":
                        message_content = "你希望这份报告围绕哪个主题来写？"
                    elif missing == "report_intent":
                        message_content = "你是想继续分析，还是现在直接生成报告？"
                    else:
                        message_content = "为了继续生成报告，我还需要你补充一个关键信息。"
            return {
                "message": {"role": "assistant", "content": message_content},
                "conversation": {"conversation_id": request.conversation_id or ""},
                "action": {"name": "generate.report"},
                "artifacts": [],
                "workflow": {"type": "report", "status": "awaiting_confirm", "phase": workflow_phase},
                "sources": [],
                "trace": {
                    "path": "workflow",
                    "workflow_name": "report",
                    "report_preparation_result": preparation.model_dump(exclude_none=True),
                    "readiness_decision": readiness_decision,
                },
            }
        state = {
            "user_input": request.question,
            "report_state": getattr(snapshot, "workflow_state", None) if snapshot is not None else None,
            "conversation_id": request.conversation_id or "",
            "owner": getattr(request, "owner", None),
            "allow_rag": bool(getattr(capability, "allow_rag", False)),
            "allow_web": bool(getattr(capability, "allow_web", False)),
            "selected_doc_ids": list(getattr(capability, "selected_doc_ids", []) or []),
            "gathered_context": gathered_context,
            "report_preparation_result": preparation.model_dump(exclude_none=True),
            "readiness_decision": readiness_decision,
        }
        if readiness_action in {"weak_soft_confirm", "direct_generate"}:
            state["report_slots"] = _build_report_slots(
                gathered_context=gathered_context,
                preparation_payload=preparation.model_dump(exclude_none=True),
            )
            state["soft_confirmed"] = True
            state["generation_ready"] = True
        _trace_context_injection(state)
        raw = engine.invoke(state)
        message_content = (
            raw.get("reply")
            or raw.get("final_response")
            or raw.get("report_content")
            or ""
        )
        workflow_status = _normalize_workflow_status(raw.get("status", "running"))
        workflow = {"type": "report", "status": workflow_status}
        if raw.get("phase"):
            workflow["phase"] = raw.get("phase")

        artifacts = raw.get("artifacts")
        if artifacts is None:
            artifacts = []
            if raw.get("report_outline"):
                artifacts.append(
                    {
                        "artifact_id": f"{request.conversation_id or 'report'}:outline",
                        "artifact_type": "report_outline",
                        "content": raw.get("report_outline"),
                    }
                )
            if raw.get("report_content"):
                artifacts.append(
                    {
                        "artifact_id": f"{request.conversation_id or 'report'}:content",
                        "artifact_type": "report",
                        "content": raw.get("report_content"),
                    }
                )
        return {
            "message": {"role": "assistant", "content": message_content},
            "conversation": {"conversation_id": request.conversation_id or ""},
            "action": {"name": "generate.report"},
            "artifacts": artifacts,
            "workflow": workflow,
            "sources": raw.get("sources", []),
            "trace": {
                "path": "workflow",
                "workflow_name": "report",
                "report_preparation_result": preparation.model_dump(exclude_none=True),
                "readiness_decision": readiness_decision,
            },
        }
