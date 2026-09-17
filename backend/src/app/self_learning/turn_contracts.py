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
    observation: 'TeachingObservation | None' = None


class TeachingObservation(Contract):
    kind: Literal['difficulty', 'open_question', 'helpful_explanation']
    text: str = Field(min_length=1, max_length=1200)
    source_message_ids: list[Identifier] = Field(min_length=1, max_length=8)
    objective_ids: list[Identifier] = Field(default_factory=list, max_length=8)


AnswerResult.model_rebuild()


from app.chat.bounded_completion import CompletionFailure as AgentFailure
