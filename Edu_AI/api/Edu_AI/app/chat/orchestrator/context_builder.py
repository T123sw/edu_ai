from __future__ import annotations

from app.chat.domain.artifact_ref import ArtifactRef
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.domain.workflow_state import WorkflowState
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter


class ContextBuilder:
    def __init__(self, *, conversation_store=None, memory_reader=None):
        self.conversation_store = conversation_store or ConversationStoreAdapter()
        self.memory_reader = memory_reader

    def build(self, request) -> ConversationSnapshot:
        if not request.conversation_id:
            summary = ""
            if self.memory_reader and request.owner:
                memory = self.memory_reader.read(user_id=request.owner, conversation_id=None) or {}
                summary = str(memory.get("summary") or "")
            return ConversationSnapshot(
                conversation_id="",
                summary=summary,
                capability=request.capability,
            )

        raw_snapshot = self.conversation_store.load_snapshot(request.conversation_id)
        state = raw_snapshot.get("state") or {}
        workflow_state = None
        if state.get("workflow_state"):
            workflow_state = WorkflowState.model_validate(
                {
                    "workflow_id": str(state["workflow_state"].get("workflow_id") or ""),
                    "workflow_type": str(state["workflow_state"].get("workflow_type") or ""),
                    "status": str(state["workflow_state"].get("status") or "running"),
                    "stage": str(state["workflow_state"].get("stage") or "collecting"),
                    "required_slots": list(state["workflow_state"].get("required_slots") or []),
                    "filled_slots": dict(state["workflow_state"].get("filled_slots") or {}),
                    "artifacts": list(state["workflow_state"].get("artifacts") or []),
                    "resume_token": str(state["workflow_state"].get("resume_token") or ""),
                }
            )

        summary = ""
        if self.memory_reader and request.owner:
            memory = self.memory_reader.read(
                user_id=request.owner,
                conversation_id=request.conversation_id,
            ) or {}
            summary = str(memory.get("summary") or "")
        summary = str(((state.get("conversation_summary") or {}).get("summary_text")) or summary or "")
        conversation_memory = dict(state.get("conversation_memory") or {})
        active_context = dict(state.get("active_context") or {})
        referenced_artifact_ids = list(
            state.get("referenced_artifact_ids")
            or conversation_memory.get("referenced_artifact_ids")
            or []
        )

        active_artifact = None
        if state.get("active_artifact"):
            active_artifact = ArtifactRef.model_validate(
                {
                    "artifact_id": str(state["active_artifact"].get("artifact_id") or ""),
                    "artifact_type": str(state["active_artifact"].get("artifact_type") or ""),
                    "title": state["active_artifact"].get("title"),
                }
            )

        return ConversationSnapshot(
            conversation_id=request.conversation_id or "",
            recent_messages=list(raw_snapshot.get("messages") or []),
            summary=summary,
            conversation_memory=conversation_memory,
            active_context=active_context,
            referenced_artifact_ids=referenced_artifact_ids,
            active_task=state.get("active_task"),
            active_artifact=active_artifact,
            workflow_state=workflow_state,
            capability=request.capability,
        )
