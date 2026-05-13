from __future__ import annotations

from pydantic import BaseModel


class ConversationReferencePayload(BaseModel):
    conversation_id: str
    title: str | None = None
    message_count: int | None = None
