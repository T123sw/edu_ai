"""Pydantic models for AI lecture sessions — no HTTP or business dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateAiLectureSessionRequest(BaseModel):
    source_ppt_material_id: str = Field(..., min_length=1)
    title: Optional[str] = None


class PatchAiLectureSessionSnapshotRequest(BaseModel):
    ai_lecturer_course_id: Optional[str] = None
    outline: Optional[list[dict[str, Any]]] = None
    script: Optional[list[dict[str, Any]]] = None
    events: Optional[list[dict[str, Any]]] = None
    last_position: Optional[dict[str, int]] = None
    slide_image_urls: Optional[list[str]] = None
    slide_count: Optional[int] = None


class AiLectureRecordingRequest(BaseModel):
    livetalking_session_id: int = Field(..., ge=1)


@dataclass
class RecordingClientResult:
    ok: bool
    recording_path: Optional[str] = None
    message: str = ""
