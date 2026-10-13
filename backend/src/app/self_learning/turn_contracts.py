"""P3 public requests and validated model answers."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field, model_validator
from .contracts import Contract, Identifier, Locator, ResourceRef


class LecturePosition(Contract):
    scene_id: Identifier
    action_id: Identifier
    speech_action_id: Identifier | None = None
    sentence_index: int | None = Field(default=None, ge=0, le=10000)
    sentence_alignment: Literal['estimated', 'sentence'] | None = None
    speech_completed: bool = False
    highlighted_element_ids: list[Identifier] = Field(default_factory=list, max_length=20)


class ClassroomReadingContext(Contract):
    status: Literal['idle', 'playing', 'paused', 'interrupted', 'completed']
    lecture: LecturePosition | None = None


class PracticeDraft(Contract):
    option_ids: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default_factory=list, max_length=8)
    text: str = Field(default='', max_length=4000)


class PracticeContext(Contract):
    check_id: Identifier
    attempt_id: Identifier | None = None
    draft: PracticeDraft | None = None

    @model_validator(mode='after')
    def one_answer(self):
        if self.attempt_id and self.draft is not None:
            raise ValueError('choose a saved attempt or an unsubmitted draft')
        return self


class ReadingSnapshot(Contract):
    resource_ref: ResourceRef
    locator: Locator | None = None
    selected_text: Annotated[str, Field(max_length=10000)] = ''
    classroom: ClassroomReadingContext | None = None
    practice: PracticeContext | None = None


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
