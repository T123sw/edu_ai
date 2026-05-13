from __future__ import annotations

from pydantic import BaseModel, Field

from app.chat.domain.ppt_outline import PptOutline


class PptOutlineArtifact(BaseModel):
    artifact_id: str
    artifact_type: str = "ppt_outline"
    title: str
    content: PptOutline
    generation_state: dict = Field(default_factory=dict)


class PptContentMarkdownArtifact(BaseModel):
    artifact_id: str
    artifact_type: str = "ppt_content_markdown"
    title: str
    content: str
    generation_state: dict = Field(default_factory=dict)

