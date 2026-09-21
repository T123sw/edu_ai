from copy import deepcopy
from types import SimpleNamespace

from app.course_preparation.quality import QualityStages
from app.course_preparation.tool_registry import digest


def resource(key, minutes=None, *, cap=None, node='n'):
    spec = {'node_id': node, 'revision': 2, 'resource_type': key,
            'teaching_context': {'resource_target_minutes': cap}}
    return {'artifact_id': key, 'spec': spec, 'spec_digest': digest(spec),
            'status': 'failed' if cap else 'draft',
            'failure_detail': {'code': 'RESOURCE_DURATION_EXCEEDED', 'category': 'content',
                               'phase': 'resource_write', 'retry_scope': 'content',
                               'message': 'duration exceeds provisional allocation'} if cap else None,
            'content': {'generation_state': {'preparation': {'duration': {
                'basis': 'unknown' if minutes is None else 'estimated', 'value_minutes': minutes}}}}}


def allocate(rows, *, hard=10, origins=None):
    from app.course_preparation.duration_reallocation import reallocate_duration_caps
    if origins is None:
        origins = {r['spec_digest']: None for r in rows if r['status'] == 'failed'}
    return reallocate_duration_caps(rows, [{'node_key': 'n', 'minutes': 10}], hard, origins)


def test_sibling_savings_are_available_to_failed_writer_without_raising_node_budget():
    rows = [resource('report', 1.7), resource('classroom', 4.92), resource('quiz', cap=2.72)]
    original = deepcopy(rows)
    assert allocate(rows) == {'quiz': 3.38}
    assert rows == original


def test_whole_course_limit_and_retained_material_still_reserve_their_time():
    rows = [resource('report', 1.7), resource('classroom', 4.92), resource('quiz', cap=2.72),
            resource('retained:other', 2, node='other')]
    assert allocate(rows, hard=11) == {'quiz': 2.38}


def test_unknown_sibling_or_missing_cap_provenance_does_not_release_time():
    rows = [resource('report'), resource('quiz', cap=2.72)]
    assert allocate(rows) == {}
    rows[0] = resource('report', 1)
    assert allocate(rows, origins={}) == {}


def test_explicit_resource_limit_is_never_relaxed():
    rows = [resource('report', 1), resource('quiz', cap=2)]
    assert allocate(rows, origins={rows[1]['spec_digest']: 2}) == {'quiz': 2}


def test_multiple_failed_writers_share_remaining_time_once():
    rows = [resource('classroom', 4), resource('report', cap=1), resource('quiz', cap=2)]
    assert allocate(rows) == {'report': 2, 'quiz': 4}
    assert sum(allocate(rows).values()) + 4 == 10


def test_failed_resource_review_supplies_reallocated_cap_to_repair(monkeypatch):
    import app.course_preparation.quality as module
    monkeypatch.setattr(module.ResearchState, 'model_validate', lambda _: SimpleNamespace(path={}))
    monkeypatch.setattr(module.ResearchAgent, '_validate_path', lambda *_: None)
    rows = [resource('report', 1.7), resource('classroom', 4.92), resource('quiz', cap=2.72)]
    cp = {'research_state': {}, 'resource_specs': [r['spec'] for r in rows],
          'generation_receipts': {r['spec_digest']: i for i, r in enumerate(rows)},
          'plan': {'nodes': [{'node_key': 'n', 'minutes': 10}]},
          'duration_cap_origins': {rows[-1]['spec_digest']: None}}
    request = SimpleNamespace(overrides=SimpleNamespace(total_minutes=10))
    stages = QualityStages(SimpleNamespace(get=lambda **_: SimpleNamespace(request=request)),
        SimpleNamespace(read_result=lambda owner, receipt: rows[receipt]),
        SimpleNamespace(validate=lambda *_: None), None)
    result = stages.review(SimpleNamespace(checkpoint=cp, owner_user_id='u', preparation_id='prep'))
    assert result.next_stage == 'repair'
    issue = result.checkpoint['quality']['issues'][0]
    assert issue['resource_duration_cap_minutes'] == 3.38
    assert issue['duration_cap_reallocated'] is True


def test_repair_tracks_derived_cap_and_preserves_explicit_origin():
    artifact = resource('quiz', 5)
    spec = artifact['spec']
    cp = {'resource_specs': [spec], 'artifacts': [artifact], 'generation_receipts': {},
          'quality': {'issues': [{'artifact_ids': ['quiz'], 'reason': 'node too long',
                                 'resource_duration_cap_minutes': 2.72}]}}
    stages = QualityStages(None, None, SimpleNamespace(validate=lambda *_: None), None)
    result = stages.repair(SimpleNamespace(checkpoint=cp, preparation_id='prep'))
    revised = result.checkpoint['resource_specs'][0]
    assert result.checkpoint['duration_cap_origins'][digest(revised)] is None
    failed = resource('quiz', cap=2.72)
    failed['spec'] = revised
    failed['spec_digest'] = digest(revised)
    next_cp = {**result.checkpoint, 'artifacts': [failed],
               'quality': {'issues': [{'artifact_ids': ['quiz'], 'reason': 'remaining time',
                                      'resource_duration_cap_minutes': 3.38,
                                      'duration_cap_reallocated': True}]}}
    next_result = stages.repair(SimpleNamespace(checkpoint=next_cp, preparation_id='prep'))
    final = next_result.checkpoint['resource_specs'][0]
    assert final['teaching_context']['resource_target_minutes'] is None
    assert final['teaching_context']['resource_repair_target_minutes'] == 3.38
    assert next_result.checkpoint['duration_cap_origins'][digest(final)] is None
    assert next_result.checkpoint['repair_counts']['content'] == 2


def test_joint_gate_uses_actual_duration_not_provisional_slots():
    rows = [resource('report', 2.8), resource('quiz', 2.6), resource('classroom', 4.5)]
    for row in rows:
        row['spec']['teaching_context']['resource_repair_target_minutes'] = 2
    nodes = [{'node_key': 'n', 'minutes': 10}]
    assert QualityStages._duration_issues(rows, nodes, 10) == []
    rows[-1] = resource('classroom', 4.7)
    assert QualityStages._duration_issues(rows, nodes, 10)


def test_new_guidance_field_does_not_change_old_context_serialization():
    from app.course_preparation.teaching_context import TeachingContext
    from tests.course_preparation.test_generated_content_constraints import context
    old = TeachingContext.model_validate(context())
    assert 'resource_repair_target_minutes' not in old.model_dump(mode='json')
    new = TeachingContext.model_validate({**context(), 'resource_repair_target_minutes': 2.72})
    assert new.model_dump(mode='json')['resource_repair_target_minutes'] == 2.72
