import copy
import pytest
from app.pbl import service, project_service, project_validation
from app.pbl.validation import RuntimeUnavailable
from app.services.durable_task_handlers import DurableTaskExecutionError
from .test_project_integration import plan,pipeline


@pytest.mark.asyncio
async def test_regression_is_repaired_before_acceptance_with_both_snapshots(repository,exercise,pipeline,plan,monkeypatch):
    context,calls,run=pipeline
    original=project_service.generate_project_phase
    target=plan['steps'][1]['id'];events=[];repairs=[]
    async def model(owner,snapshot,phase,data):
        events.append((phase,data.get('step',{}).get('id')))
        if phase=='repair_step' and data['step']['id']==target:
            repairs.append(copy.deepcopy(data))
        if phase in {'build_checks','repair_checks'} and data['step']['id']==target:
            assert data['previousCheckReport']['passed']
            assert data['referenceFiles']['/src/App.jsx']=='reference 1'
        result=await original(owner,snapshot,phase,data)
        if phase=='build_step' and data['step']['id']==target:result['referenceFiles']['/src/App.jsx']='reference -1'
        return result
    def execute(files,checks):
        events.append(('run',files['/src/App.jsx']))
        return run(files,checks)
    monkeypatch.setattr(project_service,'generate_project_phase',model)
    monkeypatch.setattr(project_validation,'check_project',execute)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'项目'},context,repository=repository)
    assert len(repairs)==1
    data=repairs[0]
    assert data['previousFiles']['/src/App.jsx']=='reference 0'
    assert data['priorCandidate']['referenceFiles']['/src/App.jsx']=='reference -1'
    assert not data['previousCheckReport']['passed']
    assert data['previousCheckReport']['checkIds']==plan['steps'][0]['newCheckIds']
    assert '尚未设计本步验收' in data['issues'][0]
    assert ('build_checks',target) not in events
    assert events.index(('run','reference -1'))<events.index(('repair_step',target))<events.index(('repair_checks',target))
    assert repository.get_owned('alice',exercise.id).artifact_public


@pytest.mark.asyncio
async def test_persistent_prior_failure_never_calls_new_acceptance(repository,exercise,pipeline,plan,monkeypatch):
    context,calls,run=pipeline
    original=project_service.generate_project_phase
    target=plan['steps'][1]['id'];phases=[]
    async def model(owner,snapshot,phase,data):
        if data.get('step',{}).get('id')==target:phases.append(phase)
        result=await original(owner,snapshot,phase,data)
        if phase in {'build_step','repair_step'} and data['step']['id']==target:
            result['referenceFiles']['/src/App.jsx']='reference -1'
        return result
    monkeypatch.setattr(project_service,'generate_project_phase',model)
    for _ in range(2):
        with pytest.raises(DurableTaskExecutionError) as error:
            await service.generate_exercise({'exercise_id':exercise.id,'topic':'项目'},context,repository=repository)
        assert error.value.code=='PBL_VALIDATION_FAILED'
    assert phases==['build_step','repair_step','repair_step']
    row=repository.get_owned('alice',exercise.id)
    assert not row.artifact_public and len(row.checkpoint['completed'])==1
    assert row.checkpoint['previousCheckReport']['passed'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('interrupt_at',['runtime','acceptance'])
async def test_resume_reexecutes_previous_checks_and_reuses_saved_code(repository,exercise,pipeline,plan,monkeypatch,interrupt_at):
    context,calls,run=pipeline
    original=project_service.generate_project_phase
    target=plan['steps'][1]['id'];interrupted=False;phase_count=[];prior_runs=[]
    async def model(owner,snapshot,phase,data):
        nonlocal interrupted
        if data.get('step',{}).get('id')==target:
            phase_count.append(phase)
            if interrupt_at=='acceptance' and phase=='build_checks' and not interrupted:
                interrupted=True;raise TimeoutError('temporary')
        return await original(owner,snapshot,phase,data)
    def execute(files,checks):
        nonlocal interrupted
        if files['/src/App.jsx']=='reference 1' and [c['id'] for c in checks]==plan['steps'][0]['newCheckIds']:
            prior_runs.append(True)
            if interrupt_at=='runtime' and not interrupted:
                interrupted=True;raise RuntimeUnavailable('temporary')
        return run(files,checks)
    monkeypatch.setattr(project_service,'generate_project_phase',model)
    monkeypatch.setattr(project_validation,'check_project',execute)
    with pytest.raises(DurableTaskExecutionError):
        await service.generate_exercise({'exercise_id':exercise.id,'topic':'项目'},context,repository=repository)
    checkpoint=repository.get_owned('alice',exercise.id).checkpoint
    assert checkpoint['pending']['implementation']['referenceFiles']['/src/App.jsx']=='reference 1'
    assert checkpoint['repairs'].get(target,0)==0
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'项目'},context,repository=repository)
    assert len(prior_runs)==2 and phase_count.count('build_step')==1
    assert repository.get_owned('alice',exercise.id).artifact_public


@pytest.mark.asyncio
async def test_cancel_during_previous_run_does_not_start_acceptance(repository,exercise,pipeline,plan,monkeypatch):
    context,calls,run=pipeline
    def execute(files,checks):
        result=run(files,checks)
        if files['/src/App.jsx']=='reference 1':context.is_cancel_requested=lambda:True
        return result
    monkeypatch.setattr(project_validation,'check_project',execute)
    with pytest.raises(DurableTaskExecutionError) as error:
        await service.generate_exercise({'exercise_id':exercise.id,'topic':'项目'},context,repository=repository)
    assert error.value.code=='GENERATION_CANCELLED'
    assert calls==['plan','build_step','build_checks','build_step']
    assert not repository.get_owned('alice',exercise.id).artifact_public
