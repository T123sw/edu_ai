from __future__ import annotations

import json
import re
from typing import Any

from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.orchestrator.quiz_context_organizer import QuizContextOrganizer
from app.chat.orchestrator.quiz_readiness_judge import QuizReadinessJudge
from app.chat.workflows.quiz.assembler import QuizAssembler
from app.chat.workflows.quiz.generator import QuizGenerator
from core.config import Config


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _trace_enabled() -> bool:
    return str(getattr(Config, "QUIZ_WORKFLOW_TRACE", "1") or "").strip().lower() in {"1", "true", "yes"}


def _preview(value: Any, *, limit: int = 180) -> str:
    text = str(value or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _trace_event(event: str, payload: dict[str, Any]) -> None:
    if not _trace_enabled():
        return
    print(f"[习题工作流] {event}")
    print(f"  - 数据: {json.dumps(payload, ensure_ascii=False, default=str)}")


def _workflow_state_dict(workflow_state: Any) -> dict[str, Any]:
    if workflow_state is None:
        return {}
    if hasattr(workflow_state, "model_dump"):
        return workflow_state.model_dump()
    if isinstance(workflow_state, dict):
        return dict(workflow_state)
    return {
        "workflow_type": _clean(getattr(workflow_state, "workflow_type", "")),
        "status": _clean(getattr(workflow_state, "status", "")),
        "stage": _clean(getattr(workflow_state, "stage", "")),
        "required_slots": list(getattr(workflow_state, "required_slots", []) or []),
        "filled_slots": dict(getattr(workflow_state, "filled_slots", {}) or {}),
    }


def _generation_context_trace_payload(context: GenerationContext) -> dict[str, Any]:
    recent_messages = list(context.recent_relevant_messages or [])
    return {
        "conversation_id": context.conversation_id,
        "resource_type": context.resource_type,
        "summary": _preview(context.summary_text, limit=260),
        "current_topics": list(context.current_topics or []),
        "user_goals": list(context.user_goals or []),
        "confirmed_facts": list(context.confirmed_facts or []),
        "constraints": dict(context.constraints or {}),
        "teaching_issues": list(context.teaching_issues or []),
        "student_signals": list(context.student_signals or []),
        "evidence_points": list(context.evidence_points or []),
        "source_scope": dict(context.source_scope or {}),
        "recent_message_count": len(recent_messages),
        "recent_message_preview": [
            {
                "role": _clean((message or {}).get("role")),
                "content": _preview((message or {}).get("content")),
            }
            for message in recent_messages[-4:]
            if isinstance(message, dict)
        ],
    }


def _detect_entry_mode(request) -> str:
    if _clean(getattr(request, "action_hint", "")) == "generate.quiz":
        return "button"
    return "reply"


def _is_affirmative_reply(text: str) -> bool:
    normalized = _clean(text).lower().strip(".,!?;:，。！？；：")
    return normalized in {"yes", "ok", "continue", "start", "confirm", "可以", "继续", "开始", "确认", "好的", "行"}


class QuizWorkflowRuntime:
    def __init__(
        self,
        *,
        generation_context_builder=None,
        quiz_assembler=None,
        quiz_context_organizer=None,
        quiz_readiness_judge=None,
        quiz_generator=None,
    ):
        self.generation_context_builder = generation_context_builder or GenerationContextBuilder()
        self.quiz_assembler = quiz_assembler or QuizAssembler()
        self.quiz_context_organizer = quiz_context_organizer or QuizContextOrganizer()
        self.quiz_readiness_judge = quiz_readiness_judge or QuizReadinessJudge()
        self.quiz_generator = quiz_generator or QuizGenerator()

    def _stored_slots(self, snapshot) -> dict[str, str]:
        workflow_state = getattr(snapshot, "workflow_state", None) if snapshot is not None else None
        workflow_dict = _workflow_state_dict(workflow_state)
        return {
            str(key): str(value)
            for key, value in dict((workflow_dict or {}).get("filled_slots") or {}).items()
            if value not in (None, "")
        }

    def _filled_slots(self, preparation: dict[str, Any]) -> dict[str, str]:
        return {
            "topic": _clean(preparation.get("topic")),
            "question_count": str(preparation.get("question_count") or ""),
            "question_types": "|".join(list(preparation.get("question_types") or [])),
            "difficulty": _clean(preparation.get("difficulty")),
            "include_answers": str(bool(preparation.get("include_answers", True))).lower(),
            "include_explanations": str(bool(preparation.get("include_explanations", True))).lower(),
        }

    def _apply_stored_slots_for_confirmed_generation(
        self,
        preparation: dict[str, Any],
        stored_slots: dict[str, str],
    ) -> dict[str, Any]:
        merged = dict(preparation or {})
        stored_topic = _clean(stored_slots.get("topic"))
        if stored_topic:
            merged["topic"] = stored_topic

        stored_count = _clean(stored_slots.get("question_count") or stored_slots.get("count"))
        if stored_count.isdigit():
            merged["question_count"] = int(stored_count)

        stored_types = _clean(stored_slots.get("question_types") or stored_slots.get("question_type"))
        if stored_types:
            merged["question_types"] = [
                item.strip()
                for item in re.split(r"[|,，、/]+", stored_types)
                if item.strip()
            ]

        stored_difficulty = _clean(stored_slots.get("difficulty"))
        if stored_difficulty:
            merged["difficulty"] = stored_difficulty

        for key in ("include_answers", "include_explanations"):
            raw = _clean(stored_slots.get(key)).lower()
            if raw in {"true", "1", "yes"}:
                merged[key] = True
            elif raw in {"false", "0", "no"}:
                merged[key] = False
        return merged

    def _finalize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        workflow = dict(response.get("workflow") or {})
        _trace_event(
            "workflow_response",
            {
                "message": _preview((response.get("message") or {}).get("content")),
                "workflow": workflow,
                "filled_slots": dict(workflow.get("filled_slots") or {}),
                "artifact_count": len(list(response.get("artifacts") or [])),
            },
        )
        return response

    def run(self, *, request, snapshot, decision):
        capability = getattr(request, "capability", None)
        workflow_state = getattr(snapshot, "workflow_state", None) if snapshot is not None else None
        workflow_dict = _workflow_state_dict(workflow_state)
        active_context = dict(getattr(snapshot, "active_context", {}) or {}) if snapshot is not None else {}

        _trace_event(
            "workflow_start",
            {
                "conversation_id": _clean(getattr(request, "conversation_id", "")),
                "question": _clean(getattr(request, "question", "")),
                "action_hint": _clean(getattr(request, "action_hint", "")),
                "decision": {
                    "path": _clean(getattr(decision, "path", "")),
                    "action": _clean(getattr(decision, "action", "")),
                    "workflow_name": _clean(getattr(decision, "workflow_name", "")),
                    "reason": _clean(getattr(decision, "reason", "")),
                },
                "workflow_state": workflow_dict,
                "active_context": active_context,
            },
        )

        generation_context = GenerationContext(
            conversation_id=_clean(getattr(request, "conversation_id", "")),
            resource_type="quiz",
        )
        if snapshot is not None:
            generation_context = self.generation_context_builder.build_for_resource(
                request=request,
                snapshot=snapshot,
                resource_type="quiz",
            )

        stored_slots = self._stored_slots(snapshot)
        _trace_event("generation_context", _generation_context_trace_payload(generation_context))
        _trace_event("stored_slots_before_organize", {"stored_slots": stored_slots})

        preparation = self.quiz_context_organizer.organize(
            context=generation_context,
            request_question=request.question,
            stored_slots=stored_slots,
        )
        should_generate = _clean(workflow_dict.get("stage")) == "soft_confirm" and _is_affirmative_reply(request.question)

        preparation_payload = preparation.model_dump(exclude_none=True)
        if should_generate:
            preparation_payload = self._apply_stored_slots_for_confirmed_generation(preparation_payload, stored_slots)
        _trace_event("quiz_preparation_result", preparation_payload)

        if should_generate:
            readiness = {"action": "confirmed_generate", "missing_critical_fields": [], "asked_fields": []}
            _trace_event("readiness_decision", readiness)
            artifact = self.quiz_generator.generate(
                preparation=preparation_payload,
                context_summary=generation_context.summary_text,
                conversation_id=_clean(getattr(request, "conversation_id", "")),
                owner=getattr(request, "owner", None),
                allow_rag=bool(getattr(capability, "allow_rag", False)),
                selected_doc_ids=list(getattr(capability, "selected_doc_ids", []) or []),
            )
            return self._finalize_response(
                {
                    "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
                    "conversation": {"conversation_id": _clean(getattr(request, "conversation_id", ""))},
                    "action": {"name": "generate.quiz"},
                    "artifacts": [artifact],
                    "workflow": {
                        "type": "quiz",
                        "status": "completed",
                        "stage": "generating",
                        "required_slots": [],
                        "filled_slots": self._filled_slots(preparation_payload),
                    },
                    "sources": [],
                    "trace": {
                        "path": "workflow",
                        "workflow_name": "quiz",
                        "quiz_preparation_result": preparation_payload,
                        "readiness_decision": readiness,
                    },
                }
            )

        readiness = self.quiz_readiness_judge.judge(preparation, entry_mode=_detect_entry_mode(request))
        _trace_event("readiness_decision", readiness)

        if readiness["action"] == "ask_critical_gap":
            return self._finalize_response(
                {
                    "message": {"role": "assistant", "content": readiness["question"]},
                    "conversation": {"conversation_id": _clean(getattr(request, "conversation_id", ""))},
                    "action": {"name": "generate.quiz"},
                    "artifacts": [],
                    "workflow": {
                        "type": "quiz",
                        "status": "awaiting_confirm",
                        "stage": "critical_gap",
                        "required_slots": readiness["missing_critical_fields"],
                        "filled_slots": self._filled_slots(preparation_payload),
                    },
                    "sources": [],
                    "trace": {
                        "path": "workflow",
                        "workflow_name": "quiz",
                        "quiz_preparation_result": preparation_payload,
                        "readiness_decision": readiness,
                    },
                }
            )

        if readiness["action"] in {"no_quiz_intent", "ask_generation_basis"}:
            return self._finalize_response(
                {
                    "message": {"role": "assistant", "content": readiness.get("question") or "请说明你希望生成什么样的习题。"},
                    "conversation": {"conversation_id": _clean(getattr(request, "conversation_id", ""))},
                    "action": {"name": "generate.quiz"},
                    "artifacts": [],
                    "workflow": {
                        "type": "quiz",
                        "status": "awaiting_confirm",
                        "stage": "critical_gap",
                        "required_slots": list(readiness.get("missing_critical_fields") or []),
                        "filled_slots": self._filled_slots(preparation_payload),
                    },
                    "sources": [],
                    "trace": {
                        "path": "workflow",
                        "workflow_name": "quiz",
                        "quiz_preparation_result": preparation_payload,
                        "readiness_decision": readiness,
                    },
                }
            )

        return self._finalize_response(
            {
                "message": {"role": "assistant", "content": readiness["soft_confirm_message"]},
                "conversation": {"conversation_id": _clean(getattr(request, "conversation_id", ""))},
                "action": {"name": "generate.quiz"},
                "artifacts": [],
                "workflow": {
                    "type": "quiz",
                    "status": "awaiting_confirm",
                    "stage": "soft_confirm",
                    "required_slots": [],
                    "filled_slots": self._filled_slots(preparation_payload),
                },
                "sources": [],
                "trace": {
                    "path": "workflow",
                    "workflow_name": "quiz",
                    "quiz_preparation_result": preparation_payload,
                    "readiness_decision": readiness,
                },
            }
        )

        artifact = self.quiz_generator.generate(
            preparation=preparation_payload,
            context_summary=generation_context.summary_text,
            conversation_id=_clean(getattr(request, "conversation_id", "")),
            owner=getattr(request, "owner", None),
            allow_rag=bool(getattr(capability, "allow_rag", False)),
            selected_doc_ids=list(getattr(capability, "selected_doc_ids", []) or []),
        )
        return self._finalize_response(
            {
                "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
                "conversation": {"conversation_id": _clean(getattr(request, "conversation_id", ""))},
                "action": {"name": "generate.quiz"},
                "artifacts": [artifact],
                "workflow": {
                    "type": "quiz",
                    "status": "completed",
                    "stage": "generating",
                    "required_slots": [],
                    "filled_slots": self._filled_slots(preparation_payload),
                },
                "sources": [],
                "trace": {
                    "path": "workflow",
                    "workflow_name": "quiz",
                    "quiz_preparation_result": preparation_payload,
                    "readiness_decision": readiness,
                },
            }
        )
