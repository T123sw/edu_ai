"""Versioned full-resource Q&A contracts for study guides and practice sets."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ResourceQaAnchor(BaseModel):
    scene_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    question_id: str | None = None


class ResourceQaTurnRequest(BaseModel):
    client_turn_id: UUID
    question: str = Field(min_length=1, max_length=1000)
    resource_version: int = Field(ge=1)
    context_scope: Literal["full_resource"] = "full_resource"
    anchor: ResourceQaAnchor | None = None

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


class ResourceQaTurnResponse(BaseModel):
    turn_id: str
    client_turn_id: UUID
    question: str
    answer_text: str
    transition_text: str
    tts_status: Literal["ready", "failed"]
    audio_url: str | None = None
    created_at: str


class ResourceQaSessionResponse(BaseModel):
    session_id: str
    course_id: str
    resource_kind: Literal["study_guide", "practice"]
    resource_id: str
    resource_version: int
    owner_user_id: str
    status: Literal["ready"] = "ready"
    turns: list[ResourceQaTurnResponse] = Field(default_factory=list)


class ResourceQaTurnSubmissionResponse(BaseModel):
    session_id: str
    turn: ResourceQaTurnResponse
