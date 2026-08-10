"""Public contracts for student Q&A inside an active AI classroom."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ClassroomQaCheckpoint(BaseModel):
    scene_id: str = Field(min_length=1)
    scene_index: int = Field(ge=0)
    action_index: int = Field(ge=0)
    action_id: str | None = None
    phase: Literal["executing_action", "between_actions"]
    page_revision: int = Field(ge=0)


class ClassroomQaTurnRequest(BaseModel):
    client_turn_id: UUID
    question: str = Field(min_length=1, max_length=1000)
    checkpoint: ClassroomQaCheckpoint

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


class ClassroomQaTurnResponse(BaseModel):
    turn_id: str
    client_turn_id: UUID
    question: str
    answer_text: str
    transition_text: str
    tts_status: Literal["ready", "failed"]
    audio_url: str | None = None
    created_at: str


class ClassroomQaSessionResponse(BaseModel):
    session_id: str
    course_id: str
    classroom_id: str
    owner_user_id: str
    status: Literal["ready"] = "ready"
    turns: list[ClassroomQaTurnResponse] = Field(default_factory=list)


class ClassroomQaTurnSubmissionResponse(BaseModel):
    session_id: str
    turn: ClassroomQaTurnResponse
