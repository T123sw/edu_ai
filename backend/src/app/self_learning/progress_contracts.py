"""Strict client events: actor and receipt are always server-owned."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field, model_validator
from .contracts import Contract, Identifier, Locator, ManifestRef, ResourceRef


class Opened(Contract):
    pass


class Position(Contract):
    stream_id: UUID
    sequence: Annotated[int, Field(strict=True, ge=1)]
    locator: Locator


class EndReached(Contract):
    locator: Locator


class Completion(Contract):
    completed: Annotated[bool, Field(strict=True)]


class SelfAssessment(Contract):
    value: Literal['understood', 'needs_review', 'unset']
    source_message_id: Identifier | None = None


PAYLOADS = {'resource_opened': Opened, 'reading_position_set': Position,
            'resource_end_reached': EndReached, 'resource_completion_set': Completion,
            'self_assessment_set': SelfAssessment}


class LearningEvent(Contract):
    schema_version: Literal[1] = 1
    event_id: UUID
    type: Literal['resource_opened', 'reading_position_set', 'resource_end_reached',
                  'resource_completion_set', 'self_assessment_set']
    manifest_ref: ManifestRef | None = None
    resource_ref: ResourceRef | None = None
    expected_revision: Annotated[int, Field(strict=True, ge=0)] | None = None
    occurred_at: datetime
    payload: dict

    @model_validator(mode='after')
    def validate_event(self):
        if self.occurred_at.tzinfo is None:
            raise ValueError('occurred_at requires timezone')
        PAYLOADS[self.type].model_validate(self.payload)
        if self.type == 'self_assessment_set':
            if self.resource_ref is not None:
                raise ValueError('self assessment targets the topic')
        elif self.resource_ref is None:
            raise ValueError('resource_ref required')
        if self.type in {'resource_completion_set', 'self_assessment_set'}:
            if self.expected_revision is None:
                raise ValueError('expected_revision required')
        elif self.expected_revision is not None:
            raise ValueError('reading events use stream sequence, not object revision')
        return self
