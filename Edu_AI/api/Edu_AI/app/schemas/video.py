"""Pydantic models for video upload/search — no HTTP or business dependencies."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class VideoUploadResponse(BaseModel):
    job_id: str
    status: str
    message: str
    saved_video_path: str


class VideoJobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int
    message: Optional[str] = None
    result: Optional[dict[str, Any]] = None


class VideoSearchRequest(BaseModel):
    query: str = Field(..., description="查询文本")
    top_k: int = Field(default=5, ge=1, le=20)
    course_id: Optional[str] = Field(default=None, description="按课程过滤")


class VideoSearchHit(BaseModel):
    id: str
    score: float
    transcript: str
    course_id: Optional[str] = None
    source_original_path: Optional[str] = None
    source_chunk_path: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    stream_url: Optional[str] = None
    playback_url: Optional[str] = None


class VideoSearchResponse(BaseModel):
    query: str
    hits: list[VideoSearchHit]
