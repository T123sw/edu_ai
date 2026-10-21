import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from app.pbl import project_workflow as workflow


@pytest.fixture
def plan():
    return json.loads((workflow.SKILL_ROOT / 'examples/calculator-plan.json').read_text())


@pytest.fixture
def unit():
    return json.loads((workflow.SKILL_ROOT / 'examples/calculator-input-step.json').read_text())


@pytest.mark.parametrize('name,count', [('calculator-plan.json', 4), ('quicksort-plan.json', 1)])
def test_examples_define_plans_not_successful_runs(name, count):
    payload = json.loads((workflow.SKILL_ROOT / 'examples' / name).read_text())
    result = workflow.validate_project_plan(payload)
    assert len(result['plan']['steps']) == count
    assert result['structurallyValid']
    assert not result['executionValidated'] and not result['publishable']


def test_cumulative_checks_exclude_future_steps(plan):
    result = workflow.validate_project_plan(plan)
    assert result['cumulativeCheckIds']['build-layout'] == ['controls']
    assert result['cumulativeCheckIds']['number-input'] == ['controls', 'digits', 'clear']
    assert result['cumulativeCheckIds']['error-recovery'] == [check['id'] for check in plan['checks']]


def test_inherited_requirements_use_prior_checks_without_duplicate_new_checks(plan):
    before=workflow.validate_project_plan(plan)['cumulativeCheckIds']
    plan['steps'][1]['requirementIds'].extend(plan['steps'][0]['requirementIds'])
    result=workflow.validate_project_plan(plan)
    assert result['cumulativeCheckIds']==before


def test_inherited_coverage_cannot_hide_uncovered_new_requirement(plan):
    plan['steps'][1]['requirementIds'].extend(plan['steps'][0]['requirementIds'])
    plan['steps'][1]['requirementIds'].append('recovery')
    with pytest.raises(ValueError,match='检查覆盖'):
        workflow.validate_project_plan(plan)


def test_check_can_observe_shared_requirement_before_later_behavior(plan):
    before=workflow.validate_project_plan(plan)['cumulativeCheckIds']
    plan['checks'][0]['requirementIds'].append('recovery')
    result=workflow.validate_project_plan(plan)
    assert result['cumulativeCheckIds']==before
    assert result['executionValidated'] is False


def mutate_plan(plan, fault):
    if fault == 'future_dependency': plan['steps'][0]['dependsOn'] = ['number-input']
    elif fault == 'skip_previous': plan['steps'][2]['dependsOn'] = ['build-layout']
    elif fault == 'duplicate_step': plan['steps'][1]['id'] = plan['steps'][0]['id']
    elif fault == 'unknown_file': plan['steps'][0]['focusFiles'] = ['/src/secret.jsx']
    elif fault == 'path_escape': plan['editableFiles'][0] = '/src/../secret.jsx'
    elif fault == 'duplicate_check': plan['checks'].append(copy.deepcopy(plan['checks'][0]))
    elif fault == 'wrong_check_owner': plan['checks'][0]['stepId'] = 'number-input'
    elif fault == 'missing_requirement': plan['requirements'].append({'id': 'new-goal', 'description': '不能省略的用户目标'})
    elif fault == 'unassigned_check': plan['checks'].append({**plan['checks'][0], 'id': 'orphan-check'})
    elif fault == 'future_check': plan['steps'][0]['newCheckIds'].append('digits')
    elif fault == 'wrong_runtime': plan['runtimeKind'] = 'js_function'
    elif fault == 'invented_success': plan['saved'] = True
    elif fault == 'incomplete_step': plan['steps'][1]['newCheckIds'] = []
    elif fault == 'decorative_requirement': plan['steps'][1]['requirementIds'].append('recovery')
    else: raise AssertionError(fault)


@pytest.mark.parametrize('fault', [
    'future_dependency', 'skip_previous', 'duplicate_step', 'unknown_file', 'path_escape',
    'duplicate_check', 'wrong_check_owner', 'missing_requirement', 'unassigned_check',
    'future_check', 'wrong_runtime', 'invented_success', 'incomplete_step', 'decorative_requirement',
])
def test_reject_inconsistent_plans(plan, fault):
    mutate_plan(plan, fault)
    with pytest.raises(ValueError): workflow.validate_project_plan(plan)


def test_step_unit_keeps_plan_identity_and_adds_prior_checks(plan, unit):
    result = workflow.validate_step_unit(plan, unit)
    assert result['unit']['checkIds'] == ['digits', 'clear']
    assert result['cumulativeCheckIds'] == ['controls', 'digits', 'clear']
    assert not result['publishable']


@pytest.mark.parametrize('fault', ['reference', 'missing_check', 'future_check'])
def test_reject_private_or_inconsistent_step_materials(plan, unit, fault):
    if fault == 'reference': unit['referenceSolution'] = 'private answer'
    elif fault == 'goal': unit['objective'] = '改变已确认目标'
    elif fault == 'files': unit['focusFiles'] = ['/src/styles.css']
    elif fault == 'missing_check': unit['checkIds'] = ['digits']
    elif fault == 'future_check': unit['checkIds'].append('add')
    with pytest.raises(ValueError): workflow.validate_step_unit(plan, unit)


@pytest.mark.parametrize('phase', list(workflow.PHASE_REFERENCES))
def test_loads_only_stage_references(phase):
    loaded = workflow.load_project_skill(phase)
    assert loaded['name'] == workflow.SKILL_NAME and loaded['phase'] == phase
    assert loaded['references'] == [workflow.PHASE_REFERENCES[phase], 'integration.md']
    assert len(loaded['version']) == 64
    assert loaded['instructions']


def test_unknown_phase_cannot_select_a_file():
    with pytest.raises(ValueError, match='PHASE_UNKNOWN'):
        workflow.load_project_skill('../../elsewhere')


def test_loaded_reference_changes_version(tmp_path, monkeypatch):
    import shutil
    root = tmp_path / workflow.SKILL_NAME
    shutil.copytree(workflow.SKILL_ROOT, root)
    monkeypatch.setattr(workflow, 'SKILL_ROOT', root)
    before = workflow.load_project_skill('plan')
    reference = root / 'references/planning.md'
    reference.write_text(reference.read_text() + '\nAdditional review constraint.\n')
    assert workflow.load_project_skill('plan')['version'] != before['version']


def test_cli_checks_materials_and_reports_invalid_plan(tmp_path, plan):
    script = workflow.SKILL_ROOT / 'scripts/validate_plan.py'
    good = subprocess.run([sys.executable, str(script), str(workflow.SKILL_ROOT / 'examples/calculator-plan.json'),
                           '--step-unit', str(workflow.SKILL_ROOT / 'examples/calculator-input-step.json')],
                          capture_output=True, text=True, timeout=15)
    assert good.returncode == 0, good.stderr
    assert not json.loads(good.stdout)['publishable']
    plan['steps'][0]['dependsOn'] = ['number-input']
    invalid = tmp_path / 'invalid.json'
    invalid.write_text(json.dumps(plan))
    bad = subprocess.run([sys.executable, str(script), str(invalid)], capture_output=True, text=True, timeout=15)
    assert bad.returncode == 1
    assert not json.loads(bad.stdout)['structurallyValid']


def test_missing_requirement_error_identifies_uncovered_goal(plan):
    plan['requirements'].append({'id':'new-goal','description':'新增目标'})
    with pytest.raises(ValueError,match='new-goal'):
        workflow.validate_project_plan(plan)

@pytest.mark.parametrize('notes',[[],None])
def test_planning_expectations_are_optional_notes(plan,notes):
    if notes is None: plan['checks'][0].pop('expected')
    else: plan['checks'][0]['expected']=notes
    assert workflow.validate_project_plan(plan)['plan']['checks'][0]['expected']==[]


def test_step_wording_and_focus_are_not_approval_conditions(plan,unit):
    unit.update(title='润色后的标题',objective='润色后的目标',focusFiles=['/src/styles.css'])
    assert workflow.validate_step_unit(plan,unit)['unit']['title']==unit['title']
    unit['focusFiles']=['/etc/passwd']
    with pytest.raises(ValueError,match='许可'): workflow.validate_step_unit(plan,unit)


@pytest.mark.parametrize('notes',[None,'', ['  ','']])
def test_empty_note_variants_do_not_trigger_regeneration(plan,notes):
    plan['checks'][0]['expected']=notes
    assert workflow.validate_project_plan(plan)['plan']['checks'][0]['expected']==[]


def test_single_planning_note_normalizes_without_changing_meaning(plan):
    plan['checks'][0]['expected']='标题在内容上方'
    assert workflow.validate_project_plan(plan)['plan']['checks'][0]['expected']==['标题在内容上方']
