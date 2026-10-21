import json
import pytest
from app.pbl.project_schemas import UiCheck, validate_runtime_plan, validate_planned_checks, ProjectArtifact
from app.pbl.project_workflow import SKILL_ROOT

def plan():
    value=json.loads((SKILL_ROOT/'examples/calculator-plan.json').read_text())
    for check in value['checks']: check['requiredAssertions']=['visible']
    value['checks'][0].update(requiredAssertions=['above','not_overlapping','within_viewport'],viewport='mobile')
    return value

def check():
    return {'id':'controls','label':'屏幕在按钮上方，按钮不重叠且完整显示','viewport':'mobile','actions':[
        {'type':'assert','target':{'testId':'display'},'assertion':'above','relativeTo':{'role':'button'}},
        {'type':'assert','target':{'role':'button'},'assertion':'not_overlapping'},
        {'type':'assert','target':{'role':'button'},'assertion':'within_viewport'},
    ]}

def test_new_generation_contract_requires_declared_capabilities_and_viewport():
    old=json.loads((SKILL_ROOT/'examples/calculator-plan.json').read_text())
    validate_runtime_plan(old)  # Existing artifacts remain readable.
    validate_runtime_plan(old,require_check_contract=True)
    validate_runtime_plan(plan(),require_check_contract=True)
    missing=plan();missing['checks'][0].pop('viewport')
    assert validate_runtime_plan(missing,require_check_contract=True)['plan']['checks'][0]['viewport']=='desktop'

def test_step_must_execute_declared_layout_in_same_viewport():
    candidate=UiCheck.model_validate(check()).model_dump(exclude_none=True)
    validate_planned_checks(plan(),[candidate])
    candidate['actions'].pop()
    with pytest.raises(ValueError,match='布局验收'):validate_planned_checks(plan(),[candidate])
    candidate=check();candidate['viewport']='desktop'
    with pytest.raises(ValueError,match='检查窗口'):validate_planned_checks(plan(),[candidate])

@pytest.mark.parametrize('change',[
    {'relativeTo':None}, {'expected':True}, {'type':'click'},
    {'assertion':'visible'}, {'assertion':'within_viewport'},
])
def test_geometry_rejects_ambiguous_or_unsupported_fields(change):
    candidate=check();candidate['actions'][0].update(change)
    with pytest.raises(ValueError):UiCheck.model_validate(candidate)

@pytest.mark.parametrize('role',['listitem','list','table','row','cell','article','main','combobox','radio','tab','alert'])
def test_generic_semantic_roles_are_supported(role):
    from app.pbl.project_schemas import UiTarget
    assert UiTarget.model_validate({'role':role}).role==role


def test_invented_role_is_rejected():
    from app.pbl.project_schemas import UiTarget
    with pytest.raises(ValueError): UiTarget.model_validate({'role':'invented-widget'})
