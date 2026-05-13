from __future__ import annotations

from typing import Protocol


class MemoryReader(Protocol):
    def read(self, *, user_id: str, conversation_id: str | None): ...


class MemoryWriter(Protocol):
    def write(self, *, user_id: str, conversation_id: str, result: dict): ...


class ConversationSummarizer(Protocol):
    def summarize(self, *, conversation_id: str, messages: list[dict]) -> str: ...
