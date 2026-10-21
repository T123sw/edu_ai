"""Persisted specifications are identities, not objects to silently upgrade."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.course_preparation.generation_contracts import ResourceSpec
from app.course_preparation.tool_registry import digest
from tests.course_preparation.test_generation_context import context_input, build


def legacy_fixture():
    return json.loads((Path(__file__).parent / 'fixtures/parameters_v1_spec.json').read_text())


def v2_spec():
    request, cp, node = context_input()
    old = legacy_fixture()['spec']
    context = build(request, cp, node).model_dump(mode='json')
    return {**old, 'schema_version': 2, 'teaching_context': context,
            'node_id': 'n1', 'objectives': node['objectives'], 'objective_ids': ['n1:o1'],
            'learning_check': node['self_check'], 'language': 'zh-CN'}


def test_real_v1_round_trip_keeps_spec_digest_action_key_and_content():
    fixture = legacy_fixture()
    original = deepcopy(fixture['spec'])
    parsed = ResourceSpec.model_validate(original)
    assert parsed.schema_version == 1
    assert parsed.teaching_context is None
    restored = parsed.model_dump(mode='json')
    assert restored == original
    assert digest(restored) == fixture['spec_digest']
    assert 'generation:' + digest(restored) == fixture['action_key']
    assert original == fixture['spec']
    revised = {**original, 'original_content': {'content': '  原始正文\n', 'metadata': {'v': 1}}}
    assert ResourceSpec.model_validate(revised).model_dump(mode='json') == revised


def test_v2_requires_context_and_binds_compatibility_fields():
    value = v2_spec()
    assert ResourceSpec.model_validate(value).model_dump(mode='json') == value
    for field, replacement in [('teaching_context', None), ('minutes', 20),
                               ('objective_ids', ['wrong']), ('objectives', ['wrong']),
                               ('node_id', 'wrong'), ('language', 'en'), ('learning_check', 'wrong')]:
        with pytest.raises(ValueError):
            ResourceSpec.model_validate({**value, field: replacement})
    with pytest.raises(ValueError):
        ResourceSpec.model_validate({**value, 'schema_version': 1})


@pytest.mark.parametrize('change', ['activity', 'memory_value', 'memory_revision', 'memory_delete', 'epoch'])
def test_changed_context_or_memory_cannot_reuse_old_spec(change):
    value = v2_spec()
    changed = deepcopy(value)
    context = changed['teaching_context']
    if change == 'activity': context['learning_activities'].reverse(); context['learning_activities'].append('先原理后例子')
    elif change == 'memory_value': context['effective_preferences']['learning_style']['value'] = '详细解释'
    elif change == 'memory_revision': context['effective_preferences']['learning_style']['revision'] = 'v2'
    elif change == 'memory_delete': context['effective_preferences'] = {}
    else: changed['memory_epoch'] += 1
    assert digest(ResourceSpec.model_validate(changed).model_dump(mode='json')) != digest(value)


def production(request, checkpoint):
    from app.course_preparation.production_stages import ProductionStages
    actions = []
    def begin(ctx, key, kind, spec, cost):
        actions.append((key, deepcopy(spec)))
        return {'status': 'pending', 'replay': False, 'action_id': key}
    repo = SimpleNamespace(get=lambda **kwargs: SimpleNamespace(request=request),
        begin_action=begin, finish_action=lambda *args: None)
    generation = SimpleNamespace(submit=lambda ctx, spec, key: {'artifact_id': key},
        read_result=lambda *args: {'status': 'pending'})
    runner = ProductionStages(repo, generation, SimpleNamespace(validate=lambda *args: None), concurrency=4)
    result = runner.produce(SimpleNamespace(checkpoint=checkpoint, owner_user_id='alice', preparation_id='prep'))
    return result, actions


def production_input():
    request, cp, node = context_input()
    cp.update(memory_subject='alice', memory_refs={'m1': 'v1'}, config_snapshot={},
              node_evidence={'n1': legacy_fixture()['spec']['evidence']})
    return request, cp, node


def test_prepare_specifications_stops_before_any_resource_submission():
    from app.course_preparation.production_stages import ProductionStages
    request, cp, node = production_input()
    before = deepcopy(cp)
    def forbidden(*args, **kwargs):
        pytest.fail('preparing specifications must not submit or reserve generation')
    repo = SimpleNamespace(get=lambda **kwargs: SimpleNamespace(request=request), begin_action=forbidden)
    generation = SimpleNamespace(submit=forbidden, reconcile=forbidden, read_result=forbidden)
    stages = ProductionStages(repo, generation, SimpleNamespace(validate=lambda *args: None))
    context = SimpleNamespace(checkpoint=cp, owner_user_id='alice', preparation_id='prep')
    prepared = stages.prepare_specifications(context)
    assert [s['resource_type'] for s in prepared['resource_specs']] == ['classroom', 'report', 'quiz']
    assert cp == before
    assert 'generation_receipts' not in prepared
    result, actions = production(request, cp)
    assert result.checkpoint['resource_specs'] == prepared['resource_specs']
    assert len(actions) == 3


def test_production_keeps_kinds_and_shares_node_budget_without_resource_allocation():
    request, cp, node = production_input()
    request = request.model_copy(update={'overrides': request.overrides.model_copy(update={'required_resource_types': ('classroom',)})})
    before = deepcopy(cp)
    result, actions = production(request, cp)
    specs = result.checkpoint['resource_specs']
    assert [s['resource_type'] for s in specs] == ['classroom', 'report', 'quiz']
    expected = build(request, cp, node).model_dump(mode='json')
    assert all(s['schema_version'] == 2 and s['teaching_context'] == expected for s in specs)
    assert all(s['minutes'] == 10 and s['teaching_context']['resource_target_minutes'] is None for s in specs)
    assert [key for key, spec in actions] == ['generation:' + digest(s) for s in specs]
    assert cp == before


@pytest.mark.parametrize('enabled', [None, True, False])
def test_classroom_switch_controls_actual_generation_even_when_brief_disagrees(enabled):
    request, cp, _ = production_input()
    # Deliberately make the model contradict the UI choice.
    cp['brief']['required_resource_types'] = ['classroom'] if enabled is False else ['report', 'quiz']
    if enabled is not None:
        request = request.model_copy(update={'overrides': request.overrides.model_copy(update={
            'include_classroom': enabled, 'required_resource_types': ('classroom',)})})
    result, actions = production(request, cp)
    expected = ['report', 'quiz'] if enabled is False else ['classroom', 'report', 'quiz']
    assert [s['resource_type'] for s in result.checkpoint['resource_specs']] == expected
    assert [s['resource_type'] for _, s in actions] == expected


def test_production_replays_raw_v1_checkpoint_without_rebuilding():
    request, cp, node = production_input()
    fixture = legacy_fixture()
    cp['resource_specs'] = [deepcopy(fixture['spec'])]
    cp['plan']['nodes'] = []  # Old specs, not a freshly reconstructed context, are authoritative.
    result, actions = production(request, cp)
    assert result.checkpoint['resource_specs'] == [fixture['spec']]
    assert actions == [(fixture['action_key'], fixture['spec'])]
    cp = result.checkpoint
    result, actions = production(request, cp)
    assert actions == []
    assert result.checkpoint['resource_specs'] == [fixture['spec']]


def test_local_revision_keeps_exact_target_and_original_content():
    from app.course_preparation.schemas import PreparationRequest
    from uuid import uuid4
    request, cp, node = production_input()
    request = PreparationRequest(request_id=uuid4(), operation='revise_resource', goal='给当前资料补充例子',
        target={'course_id': 'c1', 'base_manifest_version': 3, 'node_id': 'n1',
                'resource_id': 'r1', 'base_resource_version': 4})
    old = {'node_id': 'n1', 'objectives': [{'objective_id': 'saved-id', 'text': '解释分工'}]}
    cp['target_snapshot'] = {'node': old, 'manifest': {'nodes': [old]}, 'source_owner': 'alice',
        'resource': {'resource_type': 'report', 'resource_id': 'r1', 'resource_version': 4},
        'resource_content': {'content': '原始正确内容\n'}}
    result, _ = production(request, cp)
    spec, = result.checkpoint['resource_specs']
    assert spec['objective_ids'] == spec['teaching_context']['objective_ids'] == ['saved-id']
    assert spec['delivery_resource_id'] == 'r1' and spec['delivery_resource_version'] == 5
    assert spec['original_content'] == {'content': '原始正确内容\n'}
    assert spec['source_resource_ref']['resource_version'] == 4


# Reuse the existing isolated SQLite/PostgreSQL fixture; no business .env.
from tests.course_preparation.test_generation_adapter import generation


def test_real_v1_artifact_sql_read_and_reconcile_preserve_stored_identity(generation):
    from sqlalchemy.orm import Session
    from app.database import User
    from app.database.models import PreparationArtifact
    from app.course_preparation.runtime_contracts import BudgetCost
    repo, context, adapter = generation
    fixture = legacy_fixture()
    with Session(repo.engine) as db, db.begin():
        db.get(User, 'alice').username = fixture['spec']['memory_subject']
    action = repo.begin_action(context, fixture['action_key'], 'generate_resource', fixture['spec'], BudgetCost(calls=1))
    receipt = adapter.submit(context, fixture['spec'], action['action_id'])
    content = {'content': '## 概念与机制\n\n历史正文，不因规格升级改写。'}
    with Session(repo.engine) as db, db.begin():
        row = db.get(PreparationArtifact, receipt['artifact_id'])
        row.content, row.content_digest = content, digest(content)
    assert adapter.reconcile(context, fixture['spec'], action['action_id']) == receipt
    restored = adapter.artifacts.get('alice', receipt['artifact_id'], content=True)
    assert restored['spec'] == fixture['spec']
    assert restored['spec_digest'] == fixture['spec_digest']
    assert restored['content'] == content
    assert restored['content_digest'] == digest(content)


@pytest.mark.parametrize('enabled', [True, False])
def test_every_new_node_gets_companions_and_resume_does_not_duplicate(enabled):
    request, cp, _ = production_input()
    request = request.model_copy(update={'overrides': request.overrides.model_copy(update={'include_classroom': enabled})})
    other = {**deepcopy(cp['plan']['nodes'][0]), 'node_key': 'n2'}
    cp['plan']['nodes'].append(other)
    cp['node_evidence']['n2'] = deepcopy(cp['node_evidence']['n1'])
    first, _ = production(request, cp)
    specs = first.checkpoint['resource_specs']
    for node_id in ('n1', 'n2'):
        kinds = [spec['resource_type'] for spec in specs if spec['node_id'] == node_id]
        assert kinds.count('report') == kinds.count('quiz') == 1
        assert kinds.count('classroom') == int(enabled)
    second, _ = production(request, first.checkpoint)
    assert second.checkpoint['resource_specs'] == specs


def test_adjusted_nodes_include_companions_but_supplements_remain_scoped():
    from app.course_preparation.resource_selection import course_resource_types
    request, _, _ = production_input()
    request = request.model_copy(update={'operation': 'adjust_course'})
    assert set(course_resource_types(request, ['classroom'])) == {'report', 'quiz', 'classroom'}
    request = request.model_copy(update={'operation': 'supplement_node'})
    assert course_resource_types(request, ['report']) == ['report']
