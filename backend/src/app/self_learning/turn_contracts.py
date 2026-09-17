"""P3 public requests and validated model answers."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field
from .contracts import Contract, Identifier, Locator, ResourceRef


class ReadingSnapshot(Contract):
    resource_ref: ResourceRef
    locator: Locator | None = None
    selected_text: Annotated[str, Field(max_length=10000)] = ''


class AnswerRequest(Contract):
    request_id: UUID
    question: Annotated[str, Field(min_length=1, max_length=2000)]
    reading_context: ReadingSnapshot


class AnswerResult(Contract):
    answer_markdown: Annotated[str, Field(min_length=1, max_length=16000)]
    citation_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    suggested_action_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    # P4 introduces persisted observations with explicit provenance.
    observation: None = None


class AgentFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)
