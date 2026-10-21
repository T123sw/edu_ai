"""Optional, subject-independent meanings and transition evidence from pages.

Malformed or legacy metadata degrades to unknown; never blocks an experiment.
Declarations explain values, they do not independently certify page correctness.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

VERSION = 'edu-state-evidence/1'
KEY = '_teaching'


class Report(BaseModel):
    model_config = ConfigDict(extra='ignore', strict=True)


class FieldMeaning(Report):
    path: list[str | int] = Field(min_length=1, max_length=12)
    meaning: str = Field(min_length=1, max_length=1000)
    scope: str = Field(min_length=1, max_length=300)
    reset_when: str = Field(min_length=1, max_length=500)


class ResetEvidence(Report):
    path: list[str | int] = Field(min_length=1, max_length=12)
    before: JsonValue
    after: JsonValue
    reason: str = Field(min_length=1, max_length=500)


class TransitionEvidence(Report):
    id: str = Field(min_length=1, max_length=160)
    kind: str = Field(min_length=1, max_length=100)
    observations: dict[str, JsonValue] = Field(default_factory=dict)
    resets: list[ResetEvidence] = Field(default_factory=list, max_length=30)


class CompletionEvidence(Report):
    status: Literal['in_progress', 'complete']
    code: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=1000)
    basis: dict[str, JsonValue] = Field(default_factory=dict)


class StateEvidence(Report):
    version: Literal['edu-state-evidence/1']
    fields: list[FieldMeaning] = Field(default_factory=list, max_length=60)
    transition: TransitionEvidence | None = None
    completion: CompletionEvidence | None = None


LIMITS = [
    'Snapshot values describe this instant, not the full history. False/zero may follow a reset; they do not prove no earlier event occurred.',
    'Do not infer field lifetime, resets, round numbers or completion causes from field names, a final flag, or generated prose.',
    'Missing semantics or completion evidence stays unknown. Algorithm reasoning must be conditional and cannot invent extra rounds or measurements.',
]


def state_evidence(state):
    raw = state.get(KEY)
    result = {'status': 'not_reported', 'source': 'page_reported_not_independently_verified',
              'fields': [], 'last_transition': None, 'completion': None,
              'interpretation_limits': LIMITS}
    if raw is None:
        return result
    if not isinstance(raw, dict) or raw.get('version') != VERSION:
        return {**result, 'status': 'unsupported_or_invalid'}
    # Parse components independently: bad optional completion metadata must not
    # discard useful field meanings or cause the teaching request to fail.
    result['status'] = 'reported'
    try:
        result['fields'] = StateEvidence.model_validate({'version': VERSION, 'fields': raw.get('fields', [])}).model_dump()['fields']
    except ValidationError:
        result['field_semantics_status'] = 'invalid'
    for key, schema, target in [('transition', TransitionEvidence, 'last_transition'),
                                ('completion', CompletionEvidence, 'completion')]:
        if raw.get(key) is None:
            continue
        try:
            result[target] = schema.model_validate(raw[key]).model_dump()
        except ValidationError:
            result[key + '_status'] = 'invalid'
    if result['last_transition']:
        result['transition_scope'] = 'latest_page_reported_transition; repeated snapshots of its id are not additional operations'
    return result


def completion_reason(state):
    evidence = state_evidence(state)
    if evidence['completion'] is None:
        return 'not_reported_as_structured_evidence'
    return {**evidence['completion'], 'source': evidence['source']}
