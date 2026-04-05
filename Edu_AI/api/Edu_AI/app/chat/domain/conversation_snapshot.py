from __future__ import annotations

from pydantic import BaseModel, Field

from .artifact_ref import ArtifactRef
from .capability_policy import CapabilityPolicy
from .workflow_state import WorkflowState


class ConversationSnapshot(BaseModel):
    conversation_id: str = ""
    recent_messages: list[dict] = Field(default_factory=list)
    summary: str = ""
    conversation_memory: dict = Field(default_factory=dict)
    active_context: dict = Field(default_factory=dict)
    referenced_artifact_ids: list[str] = Field(default_factory=list)
    active_task: str | None = None
    active_artifact: ArtifactRef | None = None
    workflow_state: WorkflowState | None = None
    capability: CapabilityPolicy = Field(default_factory=CapabilityPolicy)
