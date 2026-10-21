"""Structural delivery contract; passing validation does not confer readiness."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .schemas import Contract, Identifier, PositiveVersion, ResourceType, ShortText


ContentDigest = Annotated[str, StringConstraints(pattern=r'^[a-f0-9]{64}$')]


def unique(values, label: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f'{label} must be unique')


class LearningObjective(Contract):
    objective_id: Identifier
    text: ShortText


class ManifestResource(Contract):
    resource_id: Identifier
    resource_type: ResourceType
    version: PositiveVersion
    content_sha256: ContentDigest
    purpose: ShortText
    required: bool = True
    order: PositiveVersion
    objective_ids: tuple[Identifier, ...] = Field(min_length=1)
    objective_coverage: Literal['verified', 'planned'] = 'verified'
    source_refs: tuple[Identifier, ...] = Field(default=())


class CheckLocator(Contract):
    section_id: Identifier | None = None
    question_id: Identifier | None = None
    page: PositiveVersion | None = None

    @model_validator(mode='after')
    def not_empty(self):
        if not any((self.section_id, self.question_id, self.page)):
            raise ValueError('check locator must identify content')
        return self


class LearningCheck(Contract):
    check_id: Identifier
    objective_ids: tuple[Identifier, ...] = Field(min_length=1)
    mode: Literal['self_check', 'practice']
    resource_id: Identifier
    resource_version: PositiveVersion
    locator: CheckLocator


class ManifestNode(Contract):
    node_id: Identifier
    title: ShortText
    order: PositiveVersion
    required: bool = True
    delivery_state: Literal['ready', 'partial', 'pending'] = 'ready'
    generation_status: Literal['queued', 'generating', 'ready', 'failed'] | None = None
    pending_resource_types: tuple[ResourceType, ...] = ()
    objectives: tuple[LearningObjective, ...] = Field(min_length=1)
    prerequisite_node_ids: tuple[Identifier, ...] = Field(default=())
    estimated_minutes: PositiveVersion
    resources: tuple[ManifestResource, ...] = Field(default=())
    checks: tuple[LearningCheck, ...] = Field(default=())

    @model_validator(mode='after')
    def validate_coverage(self):
        objectives = {o.objective_id for o in self.objectives}
        unique([o.objective_id for o in self.objectives], 'objective IDs')
        unique([r.resource_id for r in self.resources], 'resource IDs within node')
        unique([r.order for r in self.resources], 'resource order')
        unique([c.check_id for c in self.checks], 'check IDs')
        unique(self.prerequisite_node_ids, 'prerequisites')
        resources = {r.resource_id: r for r in self.resources}
        if any(r.objective_coverage == 'planned' and r.resource_type not in ('classroom', 'quiz') for r in self.resources):
            raise ValueError('only classroom/quiz coverage may remain planned')
        for item in (*self.resources, *self.checks):
            unique(item.objective_ids, 'objective references')
            if not set(item.objective_ids) <= objectives:
                raise ValueError('resource/check references unknown objective')
        for check in self.checks:
            resource = resources.get(check.resource_id)
            if resource is None or resource.version != check.resource_version:
                raise ValueError('check must reference an included exact resource version')
            if not set(check.objective_ids) <= set(resource.objective_ids):
                raise ValueError('check objective must be covered by its resource')
        if self.required and self.delivery_state == 'ready':
            covered = {o for r in self.resources if r.required for o in r.objective_ids}
            checked = {o for c in self.checks for o in c.objective_ids}
            planned = {o for r in self.resources if r.required and r.resource_type == 'classroom'
                       and r.objective_coverage == 'planned' for o in r.objective_ids}
            verified = {o for r in self.resources if r.required and r.objective_coverage == 'verified'
                        for o in r.objective_ids}
            quiz_planned = {o for r in self.resources if r.required and r.resource_type == 'quiz'
                            and r.objective_coverage == 'planned' for o in r.objective_ids}
            if covered != objectives or objectives - checked - (planned - verified) - quiz_planned:
                raise ValueError('core node requires core resources and checks covering every objective')
        return self


class CourseManifest(Contract):
    schema_version: Literal[1] = 1
    delivery_state: Literal['complete', 'partial'] = 'complete'
    manifest_id: Identifier
    course_id: Identifier
    version: PositiveVersion
    route_version: PositiveVersion
    space: Literal['personal', 'course'] = 'personal'
    goal: ShortText
    audience: ShortText
    estimated_minutes: PositiveVersion
    assumptions: tuple[ShortText, ...] = Field(default=())
    nodes: tuple[ManifestNode, ...] = Field(min_length=1)
    quality_report_id: Identifier
    limitations: tuple[ShortText, ...] = Field(default=())
    created_by_preparation_id: Identifier

    @model_validator(mode='after')
    def validate_route(self):
        if self.delivery_state == 'complete' and any(n.delivery_state != 'ready' or n.pending_resource_types for n in self.nodes):
            raise ValueError('complete course cannot contain unfinished nodes')
        unique([n.node_id for n in self.nodes], 'node IDs')
        unique([n.order for n in self.nodes], 'node order')
        unique([o.objective_id for n in self.nodes for o in n.objectives], 'course objective IDs')
        unique([c.check_id for n in self.nodes for c in n.checks], 'course check IDs')
        if not any(n.required for n in self.nodes):
            raise ValueError('course requires at least one core node')
        nodes = {n.node_id: n for n in self.nodes}
        versions = {}
        for node in self.nodes:
            for prerequisite in node.prerequisite_node_ids:
                if prerequisite not in nodes or nodes[prerequisite].order >= node.order:
                    raise ValueError('prerequisite must exist and precede the node; cycles are invalid')
                if node.required and not nodes[prerequisite].required:
                    raise ValueError('core node cannot depend on optional prerequisite')
            for resource in node.resources:
                identity = (resource.resource_type, resource.version, resource.content_sha256)
                if resource.resource_id in versions and versions[resource.resource_id] != identity:
                    raise ValueError('resource ID must bind the same exact version throughout a manifest')
                versions[resource.resource_id] = identity
        return self
