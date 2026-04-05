from __future__ import annotations

from pydantic import BaseModel, Field

from .capability_policy import CapabilityPolicy


class MessagePayload(BaseModel):
    role: str
    content: str


class WorkflowPayload(BaseModel):
    type: str
    status: str
    stage: str | None = None


class ArtifactPayload(BaseModel):
    artifact_id: str
    artifact_type: str
    title: str | None = None
    content: str | None = None


class SseEvent(BaseModel):
    event: str
    data: dict | str


class ChatRequestV2(BaseModel):
    question: str
    conversation_id: str | None = None
    owner: str | None = None
    model_id: str | None = None
    course_id: str | None = None
    artifact_id: str | None = None
    action_hint: str | None = None
    capability: CapabilityPolicy = Field(default_factory=CapabilityPolicy)

