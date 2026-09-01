from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CapabilityPolicy(BaseModel):
    source_mode: Literal["course_auto", "selected_documents", "none"] = "none"
    allow_rag: bool = False
    allow_web: bool = False
    allow_image_search: bool = False
    allow_tools: bool = False
    selected_doc_ids: list[str] = Field(default_factory=list)
    max_tool_steps: int = 0

