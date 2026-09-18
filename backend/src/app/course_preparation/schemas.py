"""Untrusted request contracts. Identity and authorization are server inputs."""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
PositiveVersion = Annotated[int, Field(strict=True, ge=1)]
ResourceType = Literal['report', 'quiz', 'classroom', 'lesson_plan', 'blog', 'flashcard', 'graph', 'game', 'video']
Operation = Literal['create_course', 'supplement_node', 'revise_resource', 'adjust_course']


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class UploadRef(Contract):
    document_id: Identifier
    version: PositiveVersion
    usage: Literal['auto', 'primary', 'reference', 'coverage'] = 'auto'


class SourcePolicy(Contract):
    mode: Literal['uploaded_only', 'uploads_preferred', 'open']


class PreparationOverrides(Contract):
    language: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=40)] | None = None
    total_minutes: Annotated[int, Field(strict=True, ge=1, le=100000)] | None = None
    depth: Literal['introductory', 'intermediate', 'advanced'] | None = None
    required_resource_types: tuple[ResourceType, ...] = Field(default=(), max_length=9)


class PreparationTarget(Contract):
    course_id: Identifier
    base_manifest_version: PositiveVersion
    node_id: Identifier | None = None
    resource_id: Identifier | None = None
    base_resource_version: PositiveVersion | None = None
    base_route_version: PositiveVersion | None = None


class OriginRef(Contract):
    conversation_id: Identifier
    message_id: Identifier


class LearningContext(Contract):
    difficulty_summary: ShortText | None = None
    evidence_refs: tuple[Identifier, ...] = Field(default=(), max_length=20)


class PreparationRequest(Contract):
    schema_version: Literal[1] = 1
    request_id: UUID
    operation: Operation
    goal: ShortText
    target: PreparationTarget | None = None
    origin: OriginRef | None = None
    learning_context: LearningContext | None = None
    requested_changes: tuple[ShortText, ...] = Field(default=(), max_length=30)
    uploads: tuple[UploadRef, ...] = Field(default=(), max_length=30)
    overrides: PreparationOverrides = Field(default_factory=PreparationOverrides)
    source_policy: SourcePolicy

    @model_validator(mode='before')
    @classmethod
    def default_source_policy(cls, value):
        if isinstance(value, dict) and 'source_policy' not in value:
            value = {**value, 'source_policy': {
                'mode': 'uploads_preferred' if value.get('uploads') else 'open',
            }}
        return value

    @model_validator(mode='after')
    def validate_scope(self):
        if len({u.document_id for u in self.uploads}) != len(self.uploads):
            raise ValueError('each document may appear only once')
        if self.source_policy.mode == 'uploaded_only' and not self.uploads:
            raise ValueError('uploaded_only requires at least one upload')
        if len(set(self.overrides.required_resource_types)) != len(self.overrides.required_resource_types):
            raise ValueError('required resource types must be unique')
        target = self.target
        if self.operation == 'create_course':
            if target is not None or self.requested_changes:
                raise ValueError('create_course cannot specify an existing target or changes')
        else:
            if target is None:
                raise ValueError('existing-course operations require a target')
            if self.operation in ('supplement_node', 'revise_resource') and not target.node_id:
                raise ValueError('node operation requires node_id')
            if self.operation == 'revise_resource':
                if target.resource_id is None or target.base_resource_version is None:
                    raise ValueError('revision requires resource_id and base_resource_version')
            elif target.resource_id is not None or target.base_resource_version is not None:
                raise ValueError('resource target is only valid for revise_resource')
            if self.operation == 'adjust_course':
                if target.base_route_version is None or not self.requested_changes:
                    raise ValueError('adjust_course requires route version and requested changes')
            elif self.requested_changes or target.base_route_version is not None:
                raise ValueError('route changes are only valid for adjust_course')
        return self


def request_digest(request: PreparationRequest) -> str:
    """Hash the entire validated request, including defaults and version references."""
    encoded = json.dumps(request.model_dump(mode='json'), ensure_ascii=False,
                         sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()
