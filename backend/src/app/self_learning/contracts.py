"""Versioned learning-domain contracts; independent of storage and model providers."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Version = Annotated[int, Field(strict=True, ge=1)]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)


class Actor(Contract):
    """Construct from authentication, never from a tool's arguments."""
    user_id: Identifier


class ResourceRef(Contract):
    course_id: Identifier
    material_type: Identifier
    material_id: Identifier
    version: Version

    @property
    def key(self) -> tuple[str, str, str, int]:
        return self.course_id, self.material_type, self.material_id, self.version


class ManifestRef(Contract):
    manifest_id: Identifier
    version: Version


class DocumentLocator(Contract):
    kind: Literal['document']
    section_id: Identifier | None = None
    block_id: Identifier | None = None
    offset: Annotated[int, Field(strict=True, ge=0)] | None = None
    scroll_top: Nonnegative | None = None
    content_hash: Identifier | None = None


class PdfLocator(Contract):
    kind: Literal['pdf']
    page: Version
    text_anchor: str | None = None
    content_hash: Identifier | None = None


class VideoLocator(Contract):
    kind: Literal['video']
    seconds: Nonnegative
    duration: Nonnegative | None = None
    content_hash: Identifier | None = None

    @model_validator(mode='after')
    def within_duration(self):
        if self.duration is not None and self.seconds > self.duration:
            raise ValueError('position exceeds duration')
        return self


class ClassroomLocator(Contract):
    kind: Literal['classroom']
    scene_id: Identifier
    action_id: Identifier | None = None
    content_hash: Identifier | None = None


Locator = Annotated[DocumentLocator | PdfLocator | VideoLocator | ClassroomLocator, Field(discriminator='kind')]


class ReadingContext(Contract):
    resource_ref: ResourceRef
    locator: Locator | None = None
    selected_text: Annotated[str, Field(max_length=10000)] = ''
    # Internal result only: public request DTOs must not accept this field.
    location_verified: bool = False


class ObjectiveView(Contract):
    objective_id: Identifier
    text: str


class ResourceView(Contract):
    resource_ref: ResourceRef
    title: str = ''
    required: bool | None = None
    order: int = 0
    objective_ids: list[Identifier] = Field(default_factory=list)


class TopicView(Contract):
    topic_id: Identifier
    title: str
    completion_policy: Literal['explicit', 'unknown'] = 'unknown'
    resources: list[ResourceView] = Field(default_factory=list)
    objectives: list[ObjectiveView] = Field(default_factory=list)
    required_activity_ids: list[Identifier] = Field(default_factory=list)
    available_check_ids: list[Identifier] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_resources(self):
        keys = [r.resource_ref.key for r in self.resources]
        if len(keys) != len(set(keys)):
            raise ValueError('duplicate topic resource')
        return self


class CourseView(Contract):
    course_id: Identifier
    source: Literal['manifest', 'legacy']
    manifest_ref: ManifestRef | None = None
    route_version: Version | None = None
    goal: str = ''
    completion_policy: Literal['explicit', 'unknown'] = 'unknown'
    topics: list[TopicView] = Field(default_factory=list)

    @model_validator(mode='after')
    def consistent_scope(self):
        ids = [t.topic_id for t in self.topics]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate topic identity')
        if any(r.resource_ref.course_id != self.course_id for t in self.topics for r in t.resources):
            raise ValueError('resource belongs to another course')
        if self.source == 'manifest' and (self.manifest_ref is None or self.route_version is None):
            raise ValueError('manifest source requires manifest and route versions')
        if self.source == 'legacy' and self.manifest_ref is not None:
            raise ValueError('legacy view cannot claim a manifest')
        return self


class ResourceState(Contract):
    resource_ref: ResourceRef
    opened: bool = False
    reached_end: bool = False
    completed: bool = False
    locator: Locator | None = None


class LearningFacts(Contract):
    resources: list[ResourceState] = Field(default_factory=list)
    self_assessments: dict[str, Literal['understood', 'needs_review', 'unset']] = Field(default_factory=dict)
    open_questions: dict[str, list[str]] = Field(default_factory=dict)
    completed_activity_ids: list[str] = Field(default_factory=list)
    facts_revision: Annotated[int, Field(strict=True, ge=0)] = 0

    @model_validator(mode='after')
    def unique_states(self):
        keys = [r.resource_ref.key for r in self.resources]
        if len(keys) != len(set(keys)):
            raise ValueError('duplicate resource state')
        return self


class TopicProjection(Contract):
    topic_id: Identifier
    progress: Literal['not_started', 'in_progress', 'core_completed']
    judgment: Literal['unverified', 'evidence_supports', 'needs_review', 'mixed'] = 'unverified'
    self_assessment: Literal['understood', 'needs_review', 'unset'] = 'unset'
    completed_core: int = 0
    total_core: int | None = None
    facts_revision: int = 0


class NextAction(Contract):
    kind: Literal['continue', 'resolve_question', 'check', 'review_course']
    topic_id: Identifier
    resource_ref: ResourceRef | None = None
    source_ids: list[str] = Field(default_factory=list)
    reason: str
    facts_revision: int
