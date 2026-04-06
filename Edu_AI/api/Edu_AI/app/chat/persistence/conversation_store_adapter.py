from __future__ import annotations

from app.chat.domain.extraction_trigger import ExtractionTrigger
from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor
from app.chat.orchestrator.llm_enhancement_router import LLMEnhancementRouter
from core.conversation_storage import conversation_storage


class ConversationStoreAdapter:
    def __init__(self, *, storage=None, memory_extractor=None, enhancement_router=None, enhancement_trace_enabled: bool = False):
        self.storage = storage or conversation_storage
        self.memory_extractor = memory_extractor or ConversationMemoryExtractor()
        self.enhancement_router = enhancement_router or LLMEnhancementRouter()
        self.enhancement_trace_enabled = bool(enhancement_trace_enabled)

    def load_snapshot(self, conversation_id: str):
        return {
            "messages": self.storage.get_messages(conversation_id, limit=20),
            "state": self.storage.get_state(conversation_id),
        }

    def append_message(self, conversation_id: str, role: str, content: str, *, sources=None, message_kind: str | None = None):
        self.storage.append_message(conversation_id, role, content, sources=sources, message_kind=message_kind)

    def update_workflow_state(self, conversation_id: str, workflow_state: dict):
        self.storage.update_state(conversation_id, {"workflow_state": workflow_state})

    @staticmethod
    def _normalize_artifact_reference(value) -> dict:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            return dict(value.model_dump(exclude_none=True))
        if isinstance(value, dict):
            return dict(value)
        return {}

    @staticmethod
    def _build_extraction_trigger(*, conversation_id: str, request, result: dict) -> ExtractionTrigger:
        workflow_type = str(((result.get("workflow") or {}).get("type")) or "").strip()
        action_name = str(((result.get("action") or {}).get("name")) or "").strip()
        if workflow_type:
            event = f"workflow.{workflow_type}.requested"
        else:
            event = "reply.completed"
        return ExtractionTrigger(
            event=event,
            conversation_id=conversation_id,
            question=str(getattr(request, "question", "") or ""),
            action_name=action_name or None,
            workflow_type=workflow_type or None,
        )

    def build_memory_state_patch_with_observation(self, *, conversation_id: str, request, result: dict, existing_state: dict, recent_messages: list[dict]) -> tuple[dict, dict]:
        rule_patch = self.memory_extractor.build_state_patch(
            request=request,
            result=result,
            existing_state=existing_state,
            recent_messages=recent_messages,
        )
        trigger = self._build_extraction_trigger(
            conversation_id=conversation_id,
            request=request,
            result=result,
        )
        return self.enhancement_router.apply_with_observation(
            trigger=trigger,
            existing_state=existing_state,
            rule_patch=rule_patch,
            context={
                "resource_type": str(((result.get("workflow") or {}).get("type")) or "chat"),
                "action_name": str(((result.get("action") or {}).get("name")) or "").strip(),
                "recent_messages": recent_messages,
            },
        )

    def build_memory_state_patch(self, *, conversation_id: str, request, result: dict, existing_state: dict, recent_messages: list[dict]) -> dict:
        patch, _ = self.build_memory_state_patch_with_observation(
            conversation_id=conversation_id,
            request=request,
            result=result,
            existing_state=existing_state,
            recent_messages=recent_messages,
        )
        return patch

    @staticmethod
    def _build_active_context_patch(*, request, workflow: dict | None, workflow_status: str, artifacts: list[dict]):
        capability = getattr(request, "capability", None)
        selected_doc_ids = list(getattr(capability, "selected_doc_ids", []) or [])
        artifact_reference = ConversationStoreAdapter._normalize_artifact_reference(
            getattr(request, "artifact_reference", None)
        )
        first_artifact = artifacts[0] if artifacts else {}
        active_artifact_id = str(first_artifact.get("artifact_id") or artifact_reference.get("artifact_id") or "")
        active_artifact_type = str(first_artifact.get("artifact_type") or artifact_reference.get("artifact_type") or "")
        return {
            "active_workflow_type": (workflow or {}).get("type") or "",
            "active_workflow_status": workflow_status or str((workflow or {}).get("status") or ""),
            "active_artifact_id": active_artifact_id,
            "active_artifact_type": active_artifact_type,
            "active_reference_mode": "artifact_edit" if artifact_reference else "",
            "current_course_id": getattr(request, "course_id", None),
            "pinned_doc_ids": selected_doc_ids,
        }

    @staticmethod
    def _build_workflow_filled_slots(*, result: dict) -> dict[str, str]:
        trace = dict(result.get("trace") or {})
        preparation = dict(trace.get("report_preparation_result") or {})
        filled_slots: dict[str, str] = {}
        subject = str(preparation.get("report_subject") or "").strip()
        focus = str(preparation.get("report_focus") or "").strip()
        source = str(preparation.get("preparation_source") or "").strip()
        model = str(preparation.get("preparation_model") or "").strip()
        if subject:
            filled_slots["core_topic"] = subject
        if focus:
            filled_slots["focus_area"] = focus
        if source:
            filled_slots["__preparation_source"] = source
        if model:
            filled_slots["__preparation_model"] = model
        return filled_slots

    def write_v2_result(self, conversation_id: str, request, result: dict):
        self.storage.ensure_conversation(
            conversation_id,
            request.question,
            owner=getattr(request, "owner", None),
        )
        existing_state = self.storage.get_state(conversation_id)
        workflow = result.get("workflow") or None
        action_name = str(((result.get("action") or {}).get("name")) or "").strip()
        artifacts = result.get("artifacts") or []
        user_message_kind = self.memory_extractor.classify_message_kind(
            role="user",
            text=request.question,
            workflow_type=str((workflow or {}).get("type") or ""),
            action_name=action_name,
            artifacts=artifacts,
        )
        self.append_message(conversation_id, "user", request.question, message_kind=user_message_kind)
        answer = str(((result.get("message") or {}).get("content")) or "").strip()
        if answer:
            assistant_message_kind = self.memory_extractor.classify_message_kind(
                role="assistant",
                text=answer,
                workflow_type=str((workflow or {}).get("type") or ""),
                action_name=action_name,
                artifacts=artifacts,
            )
            self.append_message(
                conversation_id,
                "assistant",
                answer,
                sources=result.get("sources") or None,
                message_kind=assistant_message_kind,
            )
        recent_messages = self.storage.get_messages(conversation_id, limit=8)

        state_patch = {}
        workflow_status = str((workflow or {}).get("status") or "").strip()
        if workflow_status == "interrupted":
            state_patch["active_task"] = ""
        elif action_name:
            state_patch["active_task"] = action_name

        if workflow:
            state_patch["workflow_state"] = {
                "workflow_id": conversation_id,
                "workflow_type": workflow.get("type") or "",
                "status": workflow.get("status") or "running",
                "stage": workflow.get("phase") or workflow.get("stage") or "",
                "filled_slots": self._build_workflow_filled_slots(result=result),
                "artifacts": result.get("artifacts") or [],
            }

        artifacts = result.get("artifacts") or []
        artifact_reference = self._normalize_artifact_reference(getattr(request, "artifact_reference", None))
        if artifacts:
            first = artifacts[0]
            state_patch["active_artifact"] = {
                "artifact_id": first.get("artifact_id") or "",
                "artifact_type": first.get("artifact_type") or "",
                "title": first.get("title"),
            }
        elif artifact_reference:
            state_patch["active_artifact"] = {
                "artifact_id": artifact_reference.get("artifact_id") or "",
                "artifact_type": artifact_reference.get("artifact_type") or "",
                "title": artifact_reference.get("title"),
            }
        if workflow or artifacts or getattr(request, "course_id", None) or getattr(getattr(request, "capability", None), "selected_doc_ids", None):
            state_patch["active_context"] = self._build_active_context_patch(
                request=request,
                workflow=workflow,
                workflow_status=workflow_status,
                artifacts=artifacts,
            )
        elif artifact_reference:
            state_patch["active_context"] = self._build_active_context_patch(
                request=request,
                workflow=workflow,
                workflow_status=workflow_status,
                artifacts=artifacts,
            )
        capability = getattr(request, "capability", None)
        if capability is not None:
            state_patch["capability_policy"] = {
                "allow_rag": bool(getattr(capability, "allow_rag", False)),
                "allow_web": bool(getattr(capability, "allow_web", False)),
                "selected_doc_ids": list(getattr(capability, "selected_doc_ids", []) or []),
            }
        if artifacts:
            state_patch["referenced_artifact_ids"] = [
                str(artifact.get("artifact_id") or "")
                for artifact in artifacts
                if artifact.get("artifact_id")
            ]
        elif artifact_reference.get("artifact_id"):
            state_patch["referenced_artifact_ids"] = [str(artifact_reference.get("artifact_id") or "")]
        if artifact_reference:
            state_patch["artifact_reference"] = dict(artifact_reference)
        extraction_patch, enhancement_observation = self.build_memory_state_patch_with_observation(
            conversation_id=conversation_id,
            request=request,
            result=result,
            existing_state=existing_state,
            recent_messages=recent_messages,
        )
        state_patch.update(extraction_patch)
        if self.enhancement_trace_enabled:
            state_patch["llm_enhancement_trace"] = enhancement_observation
            trace = dict(result.get("trace") or {})
            trace["llm_enhancement"] = enhancement_observation
            result["trace"] = trace

        if state_patch:
            self.storage.update_state(conversation_id, state_patch)
