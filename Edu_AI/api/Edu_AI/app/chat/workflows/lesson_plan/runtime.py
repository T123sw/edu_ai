from __future__ import annotations

from typing import Any

from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.orchestrator.lesson_plan_context_organizer import LessonPlanContextOrganizer
from app.chat.orchestrator.lesson_plan_readiness_judge import LessonPlanReadinessJudge

from .assembler import LessonPlanAssembler


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalize_workflow_status(raw_status: Any) -> str:
    status = _clean(raw_status).lower()
    mapping = {
        "awaiting_human": "awaiting_confirm",
        "finished": "completed",
    }
    return mapping.get(status, status or "running")


def _is_button_like_question(question: str) -> bool:
    normalized = _clean(question).lower()
    if not normalized:
        return True
    return normalized in {
        "generate lesson plan",
        "lesson plan",
        "教案",
        "整理教案",
        "帮我出一份教案",
    }


def _is_affirmative_reply(text: str) -> bool:
    normalized = _clean(text).lower().strip("。！？,，；;: ")
    if not normalized:
        return False
    return normalized in {
        "可以",
        "继续",
        "确认",
        "确认并继续",
        "开始",
        "ok",
        "yes",
    }


def _normalize_outline_feedback(text: str) -> str:
    return _clean(text).strip("銆傦紒锛?锛岋紱;: ")


def _extract_outline_artifact_content(workflow_state: Any) -> Any:
    artifacts = list(getattr(workflow_state, "artifacts", []) or [])
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if _clean(artifact.get("artifact_type")) != "lesson_plan_outline":
            continue
        return artifact.get("content")
    return None


def _build_lesson_plan_slots(*, gathered_context: dict[str, Any], preparation_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    slot_hints = dict((gathered_context or {}).get("slot_hints") or {})
    preparation = dict(preparation_payload or {})
    return {
        "topic": _clean(slot_hints.get("topic") or preparation.get("topic")),
        "audience": _clean(slot_hints.get("audience") or preparation.get("audience")),
        "duration": _clean(slot_hints.get("duration") or preparation.get("duration")),
        "objective": _clean(slot_hints.get("objective") or preparation.get("objective")),
        "lesson_type": _clean(slot_hints.get("lesson_type") or preparation.get("lesson_type")),
    }


def _detect_entry_mode(request) -> str:
    action_hint = _clean(getattr(request, "action_hint", ""))
    if action_hint == "generate.lesson_plan":
        return "button"
    if _is_button_like_question(_clean(getattr(request, "question", ""))):
        return "button"
    return "reply"


class LessonPlanWorkflowRuntime:
    def __init__(
        self,
        *,
        engine=None,
        engine_factory=None,
        engine_resolver=None,
        generation_context_builder=None,
        lesson_plan_assembler=None,
        lesson_plan_context_organizer=None,
        lesson_plan_readiness_judge=None,
    ):
        self._engine = engine
        self._engine_factory = engine_factory
        self._engine_resolver = engine_resolver
        self.generation_context_builder = generation_context_builder or GenerationContextBuilder()
        self.lesson_plan_assembler = lesson_plan_assembler or LessonPlanAssembler()
        self.lesson_plan_context_organizer = lesson_plan_context_organizer or LessonPlanContextOrganizer()
        self.lesson_plan_readiness_judge = lesson_plan_readiness_judge or LessonPlanReadinessJudge()

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
            raise KeyError("lesson_plan")

        capability = getattr(request, "capability", None)
        generation_context = GenerationContext(
            conversation_id=_clean(getattr(snapshot, "conversation_id", "") or getattr(request, "conversation_id", "") or ""),
            resource_type="lesson_plan",
        )
        gathered_context: dict[str, Any] = {}
        if snapshot is not None:
            generation_context = self.generation_context_builder.build_for_resource(
                request=request,
                snapshot=snapshot,
                resource_type="lesson_plan",
            )
            gathered_context = self.lesson_plan_assembler.from_generation_context(generation_context)

        preparation = self.lesson_plan_context_organizer.organize(
            context=generation_context,
            request_question=request.question,
        )
        readiness_decision = self.lesson_plan_readiness_judge.judge(
            preparation,
            entry_mode=_detect_entry_mode(request),
        )

        state = {
            "user_input": request.question,
            "lesson_plan_state": getattr(snapshot, "workflow_state", None) if snapshot is not None else None,
            "conversation_id": _clean(getattr(request, "conversation_id", "") or ""),
            "owner": getattr(request, "owner", None),
            "allow_rag": bool(getattr(capability, "allow_rag", False)),
            "allow_web": bool(getattr(capability, "allow_web", False)),
            "selected_doc_ids": list(getattr(capability, "selected_doc_ids", []) or []),
            "gathered_context": gathered_context,
            "lesson_plan_preparation_result": preparation.model_dump(exclude_none=True),
            "readiness_decision": readiness_decision,
        }
        state["lesson_plan_slots"] = _build_lesson_plan_slots(
            gathered_context=gathered_context,
            preparation_payload=preparation.model_dump(exclude_none=True),
        )

        workflow_state = getattr(snapshot, "workflow_state", None) if snapshot is not None else None
        active_context = dict(getattr(snapshot, "active_context", {}) or {}) if snapshot is not None else {}
        active_artifact_type = _clean(active_context.get("active_artifact_type"))
        can_resume_outline = (
            workflow_state is not None
            and _clean(getattr(workflow_state, "workflow_type", "")) == "lesson_plan"
            and _clean(getattr(workflow_state, "status", "")) == "awaiting_confirm"
            and _clean(getattr(workflow_state, "stage", "")) in {"outlining", "outline_confirm", "soft_confirm"}
            and (
                _is_affirmative_reply(getattr(request, "question", ""))
                or active_artifact_type == "lesson_plan_outline"
            )
        )
        if can_resume_outline:
            outline_content = _extract_outline_artifact_content(workflow_state)
            if outline_content is not None:
                state["lesson_plan_outline"] = outline_content
            feedback = _normalize_outline_feedback(getattr(request, "question", ""))
            state["human_feedback"] = "确认" if _is_affirmative_reply(feedback) else feedback
            state["soft_confirmed"] = True
            state["generation_ready"] = True
        elif readiness_decision.get("action") in {"strong_soft_confirm", "weak_soft_confirm"}:
            state["soft_confirmed"] = True
            state["generation_ready"] = True

        raw = engine.invoke(state)
        message_content = (
            raw.get("reply")
            or raw.get("final_response")
            or raw.get("lesson_plan_content")
            or ""
        )
        workflow_status = _normalize_workflow_status(raw.get("status", "running"))
        workflow = {"type": "lesson_plan", "status": workflow_status}
        if raw.get("phase"):
            workflow["phase"] = raw.get("phase")

        artifacts = list(raw.get("artifacts") or [])
        outline_payload = raw.get("lesson_plan_outline")
        if outline_payload is None:
            outline_payload = state.get("lesson_plan_outline")
        if outline_payload is not None and not any(
            _clean((artifact or {}).get("artifact_type")) == "lesson_plan_outline"
            for artifact in artifacts
            if isinstance(artifact, dict)
        ):
            artifacts.append(
                {
                    "artifact_id": f"{_clean(getattr(request, 'conversation_id', '') or 'lesson_plan')}:outline",
                    "artifact_type": "lesson_plan_outline",
                    "content": outline_payload,
                }
            )
        if raw.get("lesson_plan_content") is not None and not any(
            _clean((artifact or {}).get("artifact_type")) == "lesson_plan"
            for artifact in artifacts
            if isinstance(artifact, dict)
        ):
            artifacts.append(
                {
                    "artifact_id": f"{_clean(getattr(request, 'conversation_id', '') or 'lesson_plan')}:content",
                    "artifact_type": "lesson_plan",
                    "content": raw.get("lesson_plan_content"),
                }
            )

        return {
            "message": {"role": "assistant", "content": message_content},
            "conversation": {"conversation_id": _clean(getattr(request, "conversation_id", "") or "")},
            "action": {"name": "generate.lesson_plan"},
            "artifacts": artifacts,
            "workflow": workflow,
            "sources": raw.get("sources", []),
            "trace": {
                "path": "workflow",
                "workflow_name": "lesson_plan",
                "lesson_plan_preparation_result": preparation.model_dump(exclude_none=True),
                "readiness_decision": readiness_decision,
            },
        }
