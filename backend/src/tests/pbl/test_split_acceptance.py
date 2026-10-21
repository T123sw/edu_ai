import copy
import json
import pytest
from app.pbl import service, project_service, project_generator
from app.pbl.project_schemas import UiAction, hash_files
from app.services.durable_task_handlers import DurableTaskExecutionError
from .test_project_integration import plan, pipeline


@pytest.mark.asyncio
async def test_acceptance_reads_saved_current_code_and_previous_contract(repository,exercise,pipeline,monkeypatch):
    context,calls,_=pipeline
    original=project_service.generate_project_phase
    seen=[]
    async def model(owner,snapshot,phase,data):
        if phase=='build_checks':
            checkpoint=repository.get_owned('alice',exercise.id).checkpoint
            assert checkpoint['stage']=='previous_checks_complete'
            assert data['previousCheckReport']==checkpoint['pending']['previousCheckReport']
            if data['previousChecks']:
                assert data['previousCheckReport']['passed']
                assert data['previousCheckReport']['referenceHash']==data['referenceHash']
            else:
                assert data['previousCheckReport']['skipped']
            assert checkpoint['pending']['implementation']['referenceFiles']==data['referenceFiles']
            assert checkpoint['pending']['implementationHash']==data['referenceHash']==hash_files(data['referenceFiles'])
            assert 'checks' not in checkpoint['pending']['implementation']
            assert data['referenceFiles']!=data['previousFiles']
            seen.append(copy.deepcopy(data))
        return await original(owner,snapshot,phase,data)
    monkeypatch.setattr(project_service,'generate_project_phase',model)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'项目'},context,repository=repository)
    assert calls==['plan']+['build_step','build_checks']*4
    assert all(len(data['previousChecks'])>0 for data in seen[1:])
    assert seen[0]['previousChecks']==[]


@pytest.mark.asyncio
@pytest.mark.parametrize('tamper',[False,True])
async def test_checks_model_failure_resumes_code_snapshot(repository,exercise,pipeline,monkeypatch,tamper):
    context,calls,_=pipeline
    original=project_service.generate_project_phase
    async def interrupted(owner,snapshot,phase,data):
        if phase=='build_checks': raise TimeoutError('unavailable')
        return await original(owner,snapshot,phase,data)
    monkeypatch.setattr(project_service,'generate_project_phase',interrupted)
    with pytest.raises(DurableTaskExecutionError) as error:
        await service.generate_exercise({'exercise_id':exercise.id,'topic':'项目'},context,repository=repository)
    assert error.value.code=='PBL_MODEL_UNAVAILABLE'
    checkpoint=copy.deepcopy(repository.get_owned('alice',exercise.id).checkpoint)
    assert checkpoint['pending']['implementation']['referenceFiles']['/src/App.jsx']=='reference 0'
    if tamper:
        checkpoint['pending']['implementation']['referenceFiles']['/src/App.jsx']='changed'
        repository.save_checkpoint('alice',exercise.id,context.task_id,checkpoint)
    calls.clear()
    monkeypatch.setattr(project_service,'generate_project_phase',original)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'项目'},context,repository=repository)
    expected=(['build_step'] if tamper else [])+['build_checks']+['build_step','build_checks']*3
    assert calls==expected


@pytest.mark.asyncio
async def test_current_check_can_be_repaired_without_changing_correct_code_or_prior_checks(repository,exercise,pipeline,plan,monkeypatch):
    from app.pbl import project_validation
    context,calls,run=pipeline
    original=project_service.generate_project_phase
    target=plan['steps'][1]['id']
    before={};repair={}
    async def model(owner,snapshot,phase,data):
        result=await original(owner,snapshot,phase,data)
        if phase=='build_checks' and data['step']['id']==target:
            before.update(copy.deepcopy(data))
            result['checks'][0]['actions'].append({'type':'assert','target':{'testId':'container'},'assertion':'count','expected':0})
        if phase=='repair_checks' and data['step']['id']==target:
            repair.update(copy.deepcopy(data))
        return result
    def execute(files,checks):
        report=run(files,checks)
        for check,result in zip(checks,report['results']):
            if any(action.get('assertion')=='count' for action in check['actions']):
                result.update(status='failed',message='count matches container: expected 0, actual 1')
        report['passed']=all(result['status']=='passed' for result in report['results'])
        return report
    monkeypatch.setattr(project_service,'generate_project_phase',model)
    monkeypatch.setattr(project_validation,'check_project',execute)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'项目'},context,repository=repository)
    assert calls.count('repair_step')==calls.count('repair_checks')==1
    assert repair['referenceFiles']==before['referenceFiles']
    assert repair['previousChecks']==before['previousChecks']
    assert repair['priorCandidate']['checks'][0]['actions'][-1]['assertion']=='count'
    assert 'expected 0, actual 1' in repair['issues'][0]
    assert repository.get_owned('alice',exercise.id).artifact_public


def test_generation_contract_separates_outputs_and_defines_count_semantics():
    code=project_generator.StepImplementation.model_json_schema()['properties']
    checks=project_generator.StepAcceptance.model_json_schema()['properties']
    assert 'referenceFiles' in code and 'checks' not in code
    assert 'checks' in checks and 'referenceFiles' not in checks
    schema=UiAction.model_json_schema()
    assert '不是容器子元素数量' in schema['properties']['assertion']['description']
    assert '不会自动定位其子元素' in schema['$defs']['UiTarget']['properties']['testId']['description']
    assert '允许修复本步' in checks['checks']['description']
