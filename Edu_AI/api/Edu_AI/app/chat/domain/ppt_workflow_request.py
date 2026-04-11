from __future__ import annotations

from pydantic import BaseModel, Field


class PptWorkflowRequest(BaseModel):
    conversation_id: str = ""
    question: str = ""
    followup_rounds: int = 0

    topic: str = ""
    audience: str = ""
    objective: str = ""
    key_points: list[str] = Field(default_factory=list)
    source_basis: list[str] = Field(default_factory=list)
    style: str = ""
    theme: str = ""
    page_count: int | None = None

