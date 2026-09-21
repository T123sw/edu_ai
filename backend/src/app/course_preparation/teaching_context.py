"""Pure teaching input assembly; authorization and path review remain stage gates."""
from copy import deepcopy
from typing import Literal

from pydantic import ConfigDict, Field, model_validator, model_serializer

from .schemas import Contract, Identifier, PreparationRequest

PREFERENCE_FIELDS = frozenset({'language', 'response_detail', 'learning_style', 'resource_preference'})


class TeachingContextError(ValueError):
    """A persisted reference cannot be resolved without changing its meaning."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ContextContract(Contract):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)


class RequirementContext(ContextContract):
    requirement_id: Identifier
    text: str = Field(min_length=1)
    source_quote: str = ''
    source_document_id: Identifier | None = None
    source_ref: Identifier | None = None


class NodeReference(ContextContract):
    node_id: Identifier
    title: str = Field(min_length=1)
    objectives: list[str] = Field(min_length=1)


class TeachingContext(ContextContract):
    schema_version: Literal[1] = 1
    request_goal: str = Field(min_length=1)
    requirements: list[RequirementContext]
    prior_knowledge: str
    desired_outcomes: list[str]
    exclusions: list[str]
    language: str = Field(min_length=1)
    depth: Literal['introductory', 'intermediate', 'advanced'] | None
    source_policy: dict
    effective_preferences: dict
    node_id: Identifier
    objective_ids: list[Identifier] = Field(min_length=1)
    objectives: list[str] = Field(min_length=1)
    prerequisites: list[NodeReference]
    learning_activities: list[str]
    self_check: str = Field(min_length=1)
    node_budget_minutes: int = Field(ge=1)
    resource_target_minutes: int | float | None = Field(default=None, gt=0, allow_inf_nan=False)
    resource_repair_target_minutes: int | float | None = Field(default=None, gt=0, allow_inf_nan=False)
    assumptions: list[str]
    limitations: list[str]
    requirement_ids: list[Identifier] = Field(default_factory=list)
    requested_changes: list[str] = Field(default_factory=list)
    learning_context: dict | None = None

    @model_serializer(mode='wrap')
    def preserve_existing_context(self, handler):
        value = handler(self)
        if 'resource_repair_target_minutes' not in self.model_fields_set:
            value.pop('resource_repair_target_minutes', None)
        return value

    @model_validator(mode='after')
    def references(self):
        if len(self.objectives) != len(self.objective_ids) or len(set(self.objective_ids)) != len(self.objective_ids):
            raise TeachingContextError('OBJECTIVE_ID_MISMATCH')
        ids = [r.requirement_id for r in self.requirements]
        if len(ids) != len(set(ids)) or not set(self.requirement_ids) <= set(ids):
            raise TeachingContextError('REQUIREMENT_REFERENCE_INVALID')
        for axis, value in self.effective_preferences.items():
            if axis not in PREFERENCE_FIELDS or not isinstance(value, dict) or not all(
                k in value and value[k] is not None for k in ('value', 'memory_id', 'revision')
            ):
                raise TeachingContextError('PREFERENCE_PROVENANCE_MISSING')
        return self


def resource_time_cap(context, *, include_repair_target=True):
    """Explicit limits always apply; provisional slots only guide bounded writing."""
    fields = ['resource_target_minutes']
    if include_repair_target:
        fields.append('resource_repair_target_minutes')
    values = [(context or {}).get(field) for field in fields]
    return min(value for value in values if value is not None) if any(value is not None for value in values) else None


def build_teaching_context(*, request: PreparationRequest, checkpoint: dict, node: dict) -> TeachingContext:
    """Consume a server-reviewed plan, never mutate it or infer missing user facts.

    Standalone callers supply a reviewed ``plan``. If the durable research state
    is present, its passed review and exact path must also match that plan.
    """
    cp, node = deepcopy(checkpoint), deepcopy(node)
    plan = cp['plan']
    nodes = plan['nodes']
    keys = [n['node_key'] for n in nodes]
    if len(set(keys)) != len(keys):
        raise TeachingContextError('DUPLICATE_NODE')
    if node['node_key'] not in keys or nodes[keys.index(node['node_key'])] != node:
        raise TeachingContextError('NODE_CHANGED_OR_MISSING')
    if 'research_state' in cp:
        state = cp['research_state']
        if state.get('phase') != 'done' or (state.get('review') or {}).get('decision') != 'pass':
            raise TeachingContextError('PATH_NOT_REVIEWED')
        if state.get('path') != plan:
            raise TeachingContextError('REVIEWED_PATH_CHANGED')
    index = keys.index(node['node_key'])
    prior_keys = node.get('prerequisite_keys', [])
    if len(set(prior_keys)) != len(prior_keys) or not set(prior_keys) <= set(keys[:index]):
        raise TeachingContextError('PREREQUISITE_REFERENCE_INVALID')
    by_id = {n['node_key']: n for n in nodes}
    prerequisites = [NodeReference(node_id=k, title=by_id[k]['title'], objectives=by_id[k]['objectives'])
                     for k in prior_keys]
    objective_ids = [f"{node['node_key']}:o{i + 1}" for i in range(len(node['objectives']))]
    if request.operation in ('supplement_node', 'revise_resource'):
        if len(nodes) != 1 or node['node_key'] != request.target.node_id:
            raise TeachingContextError('TARGET_SCOPE_CHANGED')
        target = cp.get('target_snapshot', {}).get('node')
        if not target or target['node_id'] != request.target.node_id:
            raise TeachingContextError('TARGET_NODE_MISSING')
        if node['objectives'] != [o['text'] for o in target['objectives']]:
            raise TeachingContextError('TARGET_OBJECTIVES_CHANGED')
        objective_ids = [o['objective_id'] for o in target['objectives']]
    if 'objective_ids' in node and node['objective_ids'] != objective_ids:
        raise TeachingContextError('OBJECTIVE_ID_ORDER_CHANGED')
    brief = cp['brief']
    requirements = [RequirementContext.model_validate(r) for r in brief.get('requirements', [])]
    # Explicit structured overrides win over inferred brief values. Free-form
    # conflicts are retained for the writer/reviewer, never keyword-classified.
    source_policy = request.source_policy.model_dump(mode='json')
    # Match intake.effective_request: inferred restrictions may narrow access,
    # but a brief cannot relax the submitted source policy.
    if (brief.get('source_policy') or {}).get('mode') == 'uploaded_only':
        source_policy = {'mode': 'uploaded_only'}
    preferences = cp.get('memory_view', {}).get('preferences', {})
    limitations = list(dict.fromkeys([
        *plan.get('limitations', []),
        *cp.get('research_summary', {}).get('limitations', []),
        *cp.get('research_summary', {}).get('unresolved_gaps', []),
        *brief.get('material_gaps', []),
    ]))
    return TeachingContext(
        request_goal=request.goal, requirements=requirements,
        prior_knowledge=brief.get('prior_knowledge', ''),
        desired_outcomes=brief.get('desired_outcomes', []), exclusions=brief.get('exclusions', []),
        language=request.overrides.language or brief['language'],
        depth=request.overrides.depth or brief.get('depth'), source_policy=source_policy,
        effective_preferences={k: deepcopy(v) for k, v in preferences.items() if k in PREFERENCE_FIELDS},
        node_id=node['node_key'], objective_ids=objective_ids, objectives=node['objectives'],
        prerequisites=prerequisites, learning_activities=node.get('learning_activities', []),
        self_check=node['self_check'], node_budget_minutes=node['minutes'],
        resource_target_minutes=None, assumptions=brief.get('assumptions', []), limitations=limitations,
        requirement_ids=node.get('requirement_ids', []), requested_changes=list(request.requested_changes),
        learning_context=request.learning_context.model_dump(mode='json') if request.learning_context else None,
    )
