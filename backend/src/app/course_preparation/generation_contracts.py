"""Server-constructed automatic policy, distinct from workbench confirmation."""
from typing import Literal

from pydantic import Field, model_serializer, model_validator
from .teaching_context import TeachingContext
from .schemas import Contract, Identifier, ShortText, ResourceType


class ResourceSpec(Contract):
    schema_version: Literal[1, 2] = 1
    teaching_context: TeachingContext | None = None
    node_id: Identifier
    title: ShortText
    resource_type: ResourceType
    required: bool=True
    revision: int=Field(default=1,ge=1)
    objectives: tuple[ShortText,...]=Field(min_length=1,max_length=10)
    objective_ids: tuple[Identifier,...]=Field(min_length=1,max_length=10)
    evidence: tuple[dict,...]=Field(min_length=1,max_length=40)
    language: Identifier
    audience: ShortText
    minutes: int=Field(ge=1)
    learning_check: ShortText
    memory_subject: Identifier
    memory_refs: dict=Field(default_factory=dict)
    memory_epoch: int=Field(ge=0)
    config_snapshot: dict=Field(default_factory=dict)
    revision_feedback: tuple[ShortText,...]=Field(default=(),max_length=10)
    delivery_resource_id: Identifier | None = None
    delivery_resource_version: int = Field(default=1, ge=1)
    source_resource_ref: dict | None = None
    original_content: dict | str | None = None
    preparation_policy: str='automatic_personal_draft_v1'


    @model_validator(mode='after')
    def versioned_context(self):
        teaching = self.teaching_context
        if self.schema_version == 1:
            if teaching is not None:
                raise ValueError('V1_TEACHING_CONTEXT_NOT_ALLOWED')
            return self
        if teaching is None:
            raise ValueError('V2_TEACHING_CONTEXT_REQUIRED')
        if (self.node_id != teaching.node_id or self.minutes != teaching.node_budget_minutes
                or list(self.objectives) != teaching.objectives
                or list(self.objective_ids) != teaching.objective_ids
                or self.language != teaching.language or self.learning_check != teaching.self_check):
            raise ValueError('V2_TEACHING_CONTEXT_MISMATCH')
        return self

    @model_serializer(mode='wrap')
    def serialize_version(self, handler):
        value = handler(self)
        # Do not add the new defaults to previously persisted v1 specifications:
        # ArtifactStore hashes this serialized value during replay and reuse.
        if self.schema_version == 1:
            for key in ('schema_version', 'teaching_context'):
                if key not in self.model_fields_set:
                    value.pop(key, None)
        return value
