from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Answer(Contract):
    option_ids: list[str] = Field(default_factory=list, max_length=20)
    blank_values: list[str] = Field(default_factory=list, max_length=50)
    text: str = Field(default='', max_length=12000)

class Start(Contract):
    request_id: UUID
    new: bool = False

class Draft(Contract):
    answer: Answer
    expected_revision: int = Field(ge=0)

class Submit(Contract):
    request_id: UUID
    answer: Answer

class Finish(Contract):
    request_id: UUID
    answers: dict[str, Answer] = Field(default_factory=dict, max_length=300)

class Ask(Contract):
    request_id: UUID
    question: str = Field(min_length=1, max_length=2000, pattern=r'\S')
    run_id: str
    question_id: str | None = None
    attempt_id: str | None = None
    draft: Answer | None = None
