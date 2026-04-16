from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .artifact_reference import ArtifactReferencePayload
from .capability_policy import CapabilityPolicy
from .conversation_reference import ConversationReferencePayload


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


class ChatInputImagePayload(BaseModel):
    image_id: str
    file_name: str
    mime_type: str
    storage_path: str
    relative_path: str
    image_url: str
    source: Literal["upload", "paste"] = "upload"


class ChatInputVideoPayload(BaseModel):
    video_id: str
    file_name: str
    mime_type: str
    storage_path: str
    relative_path: str
    video_url: str
    source: Literal["upload"] = "upload"


class ChatRequestV2(BaseModel):
    question: str
    conversation_id: str | None = None
    owner: str | None = None
    model_id: str | None = None
    course_id: str | None = None
    artifact_id: str | None = None
    artifact_reference: ArtifactReferencePayload | None = None
    conversation_reference: ConversationReferencePayload | None = None
    action_hint: str | None = None
    input_images: list[ChatInputImagePayload] = Field(default_factory=list)
    input_videos: list[ChatInputVideoPayload] = Field(default_factory=list)
    capability: CapabilityPolicy = Field(default_factory=CapabilityPolicy)

