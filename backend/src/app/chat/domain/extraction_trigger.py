from __future__ import annotations

from pydantic import BaseModel


class ExtractionTrigger(BaseModel):
    event: str
    conversation_id: str | None = None
    question: str = ""
    action_name: str | None = None
    workflow_type: str | None = None
