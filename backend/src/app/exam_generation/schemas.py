from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceRef(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_id: str = Field(min_length=1, max_length=200)
    role: Literal['context', 'template'] = 'context'


class CreateGeneration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    requirement: str = Field(min_length=1, max_length=20000, pattern=r'\S')
    mode: Literal['custom', 'mimic'] = 'custom'
    language: Literal['zh', 'en'] = 'zh'
    num_questions: int = Field(default=5, ge=1)
    question_types: list[Literal['choice', 'concept', 'fill_in_blank', 'short_answer', 'written', 'coding']] = Field(default_factory=list)
    per_type_counts: dict[str, int] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def consistent(self):
        templates = [s for s in self.sources if s.role == 'template']
        if len(templates) != (1 if self.mode == 'mimic' else 0):
            raise ValueError('仿卷需要指定一份模板资料')
        if len({s.document_id for s in self.sources}) != len(self.sources):
            raise ValueError('资料不能重复选择')
        if self.per_type_counts and (sum(self.per_type_counts.values()) != self.num_questions or
                any(k not in self.question_types or v <= 0 for k, v in self.per_type_counts.items())):
            raise ValueError('题型数量必须与总题数一致')
        return self
