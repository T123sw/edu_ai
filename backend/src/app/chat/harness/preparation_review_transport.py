"""Ephemeral review references; persisted audits retain canonical bindings."""
from copy import deepcopy
from pydantic import BaseModel, ConfigDict, Field, StrictInt


class IndexedPreparationCheck(BaseModel):
    model_config = ConfigDict(extra='forbid')
    binding_index: StrictInt = Field(ge=0)
    passed: bool
    reason: str = Field(min_length=5)


def binding_rows(metadata):
    return [(kind, item[kind], item['locator'])
            for kind, collection in [('requirement_id', 'applied_requirements'), ('objective_id', 'objective_bindings')]
            for item in metadata[collection]]


def indexed_preparation(metadata):
    result = deepcopy(metadata)
    index = 0
    for collection in ('applied_requirements', 'objective_bindings'):
        for item in result[collection]:
            item['binding_index'] = index
            index += 1
    return result


def restore_preparation_checks(raw, metadata):
    if not isinstance(raw, dict) or not isinstance(raw.get('preparation_checks'), list):
        return raw
    checks = raw['preparation_checks']
    if not any(isinstance(c, dict) and 'binding_index' in c for c in checks):
        return raw  # Legacy literal bindings still undergo canonical validation.
    parsed = [IndexedPreparationCheck.model_validate(c) for c in checks]
    rows = binding_rows(metadata)
    if sorted(c.binding_index for c in parsed) != list(range(len(rows))):
        raise ValueError('preparation_review_binding_index_coverage_incomplete: each original index required exactly once')
    return {**raw, 'preparation_checks': [
        {'binding_type': rows[c.binding_index][0], 'binding_id': rows[c.binding_index][1],
         'locator': deepcopy(rows[c.binding_index][2]), 'passed': c.passed, 'reason': c.reason}
        for c in parsed]}
