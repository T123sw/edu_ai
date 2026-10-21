from .test_generation import phase_result
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from app.pbl import service, project_service
from app.pbl.project_schemas import ProjectArtifact, UiCheck, STARTER_FILES, hash_files
from app.pbl.project_workflow import SKILL_ROOT, validate_project_plan
from app.pbl.repository import NotFound, WorkspaceConflict
from app.services.durable_task_handlers import DurableTaskExecutionError

@pytest.fixture
def plan():
    plan=json.loads((SKILL_ROOT/'examples/calculator-plan.json').read_text())
    for check in plan['checks']: check['requiredAssertions']=['visible']
    return plan

def step_candidate(plan,index):
    step=plan['steps'][index]
    unit={key:step[key] for key in ('title','objective','focusFiles')}
    unit.update(stepId=step['id'],instructionsMarkdown='实现本步要求',explanationMarkdown='为什么这样实现',hints=['提示'],checkIds=step['newCheckIds'])
    checks=[{'id':cid,'label':cid,'actions':[{'type':'assert','target':{'testId':cid},'assertion':'visible'}]} for cid in step['newCheckIds']]
    return {'unit':unit,'checks':checks,'referenceFiles':{**STARTER_FILES,'/src/App.jsx':f'reference {index}'},
        'faultyFiles':{**STARTER_FILES,'/src/App.jsx':f'faulty {index}'},'faultyCheckId':step['newCheckIds'][0]}

@pytest.fixture
def artifact(plan,exercise):
    derived=validate_project_plan(plan)['cumulativeCheckIds']
    candidates=[step_candidate(plan,i) for i in range(len(plan['steps']))]
    return ProjectArtifact(exerciseId=exercise.id,artifactVersion=1,topic='计算器',title=plan['title'],summary=plan['goal'],plan=plan,starterFiles=STARTER_FILES,
        tasks=[{**c['unit'],'id':c['unit']['stepId'],'cumulativeCheckIds':derived[c['unit']['stepId']]} for c in candidates],
        checks=[check for c in candidates for check in c['checks']],validationSummary={'passed':True,'templateVersion':'react-app-v1'})

@pytest.fixture
def ready_project(repository,exercise,artifact):
    report={'passed':True,'templateVersion':'react-app-v1','validatedSteps':4,
        'results':[{'caseId':c.id,'status':'passed','message':''} for c in artifact.checks]}
    repository.publish('alice',exercise.id,exercise.current_job_id,artifact,{'referenceFiles':'private'},report)
    return exercise

@pytest.fixture
def check_request(artifact):
    return {'artifactVersion':1,'taskId':artifact.tasks[1].id,'runId':str(uuid4()),'files':dict(STARTER_FILES)}


def test_workspace_uses_actual_files_steps_and_cas(repository,ready_project,artifact):
    workspace=repository.get_or_create_workspace('alice',ready_project.id)
    assert workspace.files==STARTER_FILES and workspace.activeTaskId==artifact.tasks[0].id
    patch={'artifactVersion':1,'expectedRevision':0,'mutationId':str(uuid4()),'files':{**STARTER_FILES,'/src/App.jsx':'user work'},
        'activeTaskId':artifact.tasks[-1].id,'customInputText':''}
    saved=repository.save_workspace('alice',ready_project.id,patch)
    assert saved.files['/src/App.jsx']=='user work' and saved.activeTaskId==artifact.tasks[-1].id
    assert repository.save_workspace('alice',ready_project.id,patch)==saved
    for bad in ({'files':{'/src/algorithm.js':'bad'}},{'activeTaskId':'implement-sort'},{'artifactVersion':2}):
        with pytest.raises(ValueError): repository.save_workspace('alice',ready_project.id,{**patch,**bad})


def test_server_reports_cumulative_immutable_and_owner_bound(repository,ready_project,check_request,artifact):
    req,checks,existing=repository.project_check_input('alice',ready_project.id,check_request)
    assert existing is None and [c['id'] for c in checks]==artifact.tasks[1].cumulativeCheckIds
    result={'passed':False,'results':[{'caseId':c['id'],'status':'failed' if i==0 else 'passed','message':'check'} for i,c in enumerate(checks)],'durationMs':10}
    body=repository.save_project_check('alice',ready_project.id,check_request,result)
    assert body['status']=='failed' and body['evidenceSource']=='server_verified'
    assert body['codeHash']==hash_files(check_request['files']) and 'referenceFiles' not in str(body)
    assert repository.project_check_input('alice',ready_project.id,check_request)[2]==body
    assert repository.list_runs('alice',ready_project.id)==[body]
    for changed in ({'taskId':artifact.tasks[0].id},{'files':{**STARTER_FILES,'/src/App.jsx':'different'}},{'artifactVersion':2}):
        with pytest.raises(WorkspaceConflict): repository.project_check_input('alice',ready_project.id,{**check_request,**changed})
    with pytest.raises(NotFound): repository.project_check_input('bob',ready_project.id,check_request)
    with pytest.raises(ValueError): repository.append_run('alice',ready_project.id,body)


def test_publish_requires_complete_actual_report(repository,exercise,artifact):
    with pytest.raises(ValueError): repository.publish('alice',exercise.id,exercise.current_job_id,artifact,{},
        {'passed':True,'templateVersion':'react-app-v1','validatedSteps':4,'results':[]})

@pytest.mark.parametrize('action',[{'type':'click','target':{'role':'button'}},
    {'type':'assert','target':{'testId':'x','role':'button'},'assertion':'visible'},
    {'type':'assert','target':{'testId':'x'},'assertion':'count','expected':'1'}])
def test_ui_checks_reject_missing_assertion_and_ambiguous_targets(action):
    with pytest.raises(ValueError): UiCheck.model_validate({'id':'check','label':'check','actions':[action]})

def test_explicit_ui_engine_preserves_legacy_check_shape():
    from pydantic import TypeAdapter
    from app.pbl.project_schemas import ProjectCheck
    original={'id':'check','label':'check','actions':[{'type':'assert','target':{'testId':'result'},'assertion':'text','expected':'32'}]}
    explicit={**original,'engine':'ui'}
    adapter=TypeAdapter(ProjectCheck)
    assert adapter.validate_python(explicit).model_dump()==adapter.validate_python(original).model_dump()
    assert explicit['engine']=='ui'
    for invalid in ('unknown','http','sandpack-jest'):
        with pytest.raises(ValueError): adapter.validate_python({**original,'engine':invalid})
    with pytest.raises(ValueError): adapter.validate_python({**explicit,'actions':[{'type':'click','target':{'testId':'result'}}]})

@pytest.fixture
def pipeline(monkeypatch,repository,exercise,plan):
    import app.pbl.project_validation as validation
    context=SimpleNamespace(task_id=exercise.current_job_id,owner_user_id='alice',progress=Mock(),
        is_cancel_requested=lambda:False,is_lease_valid=lambda:True)
    calls=[]
    async def model(owner,snapshot,phase,data):
        calls.append(phase)
        if phase=='plan': return plan
        if phase=='review_plan': return {'approved':True,'issues':[]}
        return phase_result(step_candidate(plan,next(i for i,s in enumerate(plan['steps']) if s['id']==data['step']['id'])),phase)
    def check(files,checks):
        code=files['/src/App.jsx']
        level=int(code.split()[-1]) if code.startswith('reference ') else -1
        ids={cid:i for i,s in enumerate(plan['steps']) for cid in s['newCheckIds']}
        results=[{'caseId':c['id'],'status':'passed' if level>=ids[c['id']] else 'failed','message':''} for c in checks]
        return {'passed':all(r['status']=='passed' for r in results),'results':results,'durationMs':1}
    monkeypatch.setattr(project_service,'generate_project_phase',model)
    monkeypatch.setattr(validation,'check_project',check)
    monkeypatch.setattr(service,'get_job',lambda _:None)
    return context,calls,check

@pytest.mark.asyncio
async def test_skill_pipeline_validates_every_step_and_hides_answers(repository,exercise,pipeline):
    context,calls,_=pipeline
    result=await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    row=repository.get_owned('alice',exercise.id)
    assert result['saved'] and calls==['plan']+['build_step','build_checks']*4
    assert row.artifact_public['schemaVersion']==2 and len(row.artifact_public['tasks'])==4
    assert 'referenceFiles' not in json.dumps(row.artifact_public) and 'faultyFiles' not in json.dumps(row.artifact_public)
    assert len(row.checkpoint['completed'])==4 and row.candidate_private['completed'][-1]['validated']

@pytest.mark.asyncio
async def test_regression_in_later_step_blocks_publication(repository,exercise,pipeline,monkeypatch):
    import app.pbl.project_validation as validation
    context,calls,check=pipeline
    def regressed(files,checks):
        result=check(files,checks)
        if files['/src/App.jsx']=='reference 2':
            result['passed']=False; result['results'][0]['status']='failed'
        return result
    monkeypatch.setattr(validation,'check_project',regressed)
    with pytest.raises(DurableTaskExecutionError) as error:
        await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    assert error.value.code=='PBL_VALIDATION_FAILED' and calls.count('repair_step')==2
    row=repository.get_owned('alice',exercise.id)
    assert row.artifact_public is None and len(row.checkpoint['completed'])==2
    assert row.checkpoint['issues'] and row.checkpoint['lastCandidate']['referenceFiles']

@pytest.mark.asyncio
async def test_resume_validates_saved_steps_and_skips_model(repository,exercise,pipeline,monkeypatch):
    context,calls,check=pipeline
    original=repository.publish
    monkeypatch.setattr(repository,'publish',lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('interrupted')))
    with pytest.raises(RuntimeError): await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    assert len(repository.get_owned('alice',exercise.id).checkpoint['completed'])==4
    monkeypatch.setattr(repository,'publish',original)
    calls.clear()
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    assert calls==[]

@pytest.mark.asyncio
async def test_pending_candidate_survives_runtime_failure(repository,exercise,pipeline,monkeypatch):
    import app.pbl.project_validation as validation
    from app.pbl.validation import RuntimeUnavailable
    context,calls,check=pipeline
    monkeypatch.setattr(validation,'check_project',lambda *args:(_ for _ in ()).throw(RuntimeUnavailable('down')))
    with pytest.raises(DurableTaskExecutionError) as error:
        await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    assert error.value.code=='PBL_RUNTIME_UNAVAILABLE'
    row=repository.get_owned('alice',exercise.id)
    assert row.checkpoint['pending']['stepId']=='build-layout'
    calls.clear()
    monkeypatch.setattr(validation,'check_project',check)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    assert calls==['build_step','build_checks']*3

@pytest.mark.asyncio
async def test_step_repairs_remain_bounded_across_retry(repository,exercise,pipeline,monkeypatch):
    import app.pbl.project_validation as validation
    context,calls,check=pipeline
    def fail_reference(files,checks):
        result=check(files,checks)
        result['passed']=False
        for item in result['results']: item['status']='failed'
        return result
    monkeypatch.setattr(validation,'check_project',fail_reference)
    for _ in range(2):
        with pytest.raises(DurableTaskExecutionError):
            await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    assert calls.count('build_step')==1 and calls.count('repair_step')==2

@pytest.mark.asyncio
async def test_cancel_before_publish_preserves_private_checkpoint(repository,exercise,pipeline):
    context,calls,_=pipeline
    def progress(percent,*args):
        if percent==95: context.is_cancel_requested=lambda:True
    context.progress=progress
    # Production repository includes the context fence at the write boundary.
    repository.lease_context=context
    with pytest.raises(Exception):
        await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    assert repository.get_owned('alice',exercise.id).artifact_public is None

from tests.pbl.test_api import client

def test_project_check_api_executes_trusted_checks_and_replays(client,repository,ready_project,check_request,monkeypatch):
    import app.pbl.project_validation as validation
    calls=[]
    def execute(files,checks):
        calls.append((files,checks))
        return {'passed':True,'durationMs':1,'results':[{'caseId':c['id'],'status':'passed','message':''} for c in checks]}
    monkeypatch.setattr(validation,'check_project',execute)
    path='/api/pbl/'+ready_project.id
    first=client.post(path+'/check',json=check_request)
    assert first.status_code==200,first.text
    assert first.json()['evidenceSource']=='server_verified' and len(calls[0][1])==3
    assert client.post(path+'/check',json=check_request).json()==first.json() and len(calls)==1
    assert client.post(path+'/check',json={**check_request,'files':{**STARTER_FILES,'/src/App.jsx':'other'}}).status_code==409
    assert client.post(path+'/check',json={**check_request,'checks':[]}).status_code==422
    assert client.post(path+'/runs',json=first.json()).status_code==422
    detail=client.get(path).json()['artifact']
    assert detail['schemaVersion']==2 and 'referenceFiles' not in json.dumps(detail)
    from app.auth import get_current_user
    client.app.dependency_overrides[get_current_user]=lambda:{'username':'bob'}
    assert client.post(path+'/check',json=check_request).status_code==404 and len(calls)==1

@pytest.mark.asyncio
async def test_generation_does_not_call_independent_plan_review(repository,exercise,pipeline,monkeypatch):
    context,calls,_=pipeline
    original=project_service.generate_project_phase
    async def advisory(owner,snapshot,phase,data):
        if phase=='review_plan':
            calls.append(phase)
            return {'approved':True,'issues':['计划完整且可验收；可选改善按钮样式']}
        return await original(owner,snapshot,phase,data)
    monkeypatch.setattr(project_service,'generate_project_phase',advisory)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    assert calls.count('plan')==1 and calls.count('review_plan')==0 and repository.get_owned('alice',exercise.id).artifact_public

@pytest.mark.asyncio
@pytest.mark.parametrize('tamper',['skill','plan','step'])
async def test_resume_rejects_changed_skill_or_invalid_persisted_material(repository,exercise,pipeline,monkeypatch,tamper):
    context,calls,_=pipeline
    original=repository.publish
    monkeypatch.setattr(repository,'publish',lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('interrupted')))
    with pytest.raises(RuntimeError): await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    checkpoint=copy.deepcopy(repository.get_owned('alice',exercise.id).checkpoint)
    if tamper=='skill': checkpoint['skillVersions']['plan']='different-version'
    elif tamper=='plan': checkpoint['plan']['steps'][0]['newCheckIds']=['unknown']
    else: checkpoint['completed'][0]['candidate']['unit']['stepId']='unknown'
    repository.save_checkpoint('alice',exercise.id,context.task_id,checkpoint)
    calls.clear()
    monkeypatch.setattr(repository,'publish',original)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    assert calls==['plan']+['build_step','build_checks']*4

@pytest.mark.asyncio
async def test_wrong_step_unit_is_repaired_before_execution(repository,exercise,pipeline,plan,monkeypatch):
    context,calls,_=pipeline
    original=project_service.generate_project_phase
    wrong=True
    async def mismatch(owner,snapshot,phase,data):
        nonlocal wrong
        if phase=='build_step' and wrong:
            wrong=False
            calls.append(phase)
            candidate=step_candidate(plan,0)
            candidate['unit']=step_candidate(plan,1)['unit']
            return phase_result(candidate,phase)
        return await original(owner,snapshot,phase,data)
    monkeypatch.setattr(project_service,'generate_project_phase',mismatch)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'计算器'},context,repository=repository)
    assert calls.count('repair_step')==1 and repository.get_owned('alice',exercise.id).artifact_public

@pytest.mark.asyncio
@pytest.mark.parametrize('schema_failure',[False,True])
async def test_repair_receives_rejected_candidate_and_current_contract(repository,exercise,pipeline,plan,monkeypatch,schema_failure):
    context,calls,_=pipeline
    original=project_service.generate_project_phase
    rejected=step_candidate(plan,0)
    rejected['checks'][0]['actions'][0].update(assertion=None)
    seen=[]
    async def model(owner,snapshot,phase,data):
        seen.append((phase,data))
        if phase=='build_checks' and data['step']['id']==plan['steps'][0]['id']:
            if schema_failure: raise project_service.InvalidProjectOutput(rejected,'断言格式错误')
            return phase_result(rejected,phase)
        return await original(owner,snapshot,phase,data)
    monkeypatch.setattr(project_service,'generate_project_phase',model)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'页面项目'},context,repository=repository)
    repair=next(data for phase,data in seen if phase=='repair_step')
    assert repair['priorCandidate']==rejected
    assert repair['issues'] and '断言' in repair['issues'][0]
    assert [check['id'] for check in repair['requiredChecks']]==plan['steps'][0]['newCheckIds']
    assert repository.get_owned('alice',exercise.id).artifact_public

@pytest.mark.asyncio
async def test_empty_plan_notes_and_weak_negative_are_nonblocking(repository,exercise,pipeline,plan,monkeypatch):
    context,calls,_=pipeline
    plan['checks'][0]['expected']=[]
    original=project_service.generate_project_phase
    async def material(owner,snapshot,phase,data):
        candidate=await original(owner,snapshot,phase,data)
        if phase=='build_checks':
            candidate['faultyFiles']=data['referenceFiles']
            candidate['unit']['title']='更自然的本步标题'
            candidate['unit']['objective']='说明本步成果的新措辞'
        return candidate
    monkeypatch.setattr(project_service,'generate_project_phase',material)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'页面项目'},context,repository=repository)
    row=repository.get_owned('alice',exercise.id)
    assert row.artifact_public['validationSummary']['passed']
    assert len(row.artifact_public['validationSummary']['qualityWarnings'])==4
    assert calls==['plan']+['build_step','build_checks']*4
    assert row.artifact_public['plan']['checks'][0]['expected']==[]

@pytest.mark.asyncio
async def test_extra_valid_assertions_do_not_trigger_repairs(repository,exercise,pipeline,monkeypatch):
    context,calls,_=pipeline
    original=project_service.generate_project_phase
    async def material(owner,snapshot,phase,data):
        candidate=await original(owner,snapshot,phase,data)
        if phase=='build_checks':
            for check in candidate['checks']:
                check['actions'].append({'type':'assert','target':{'testId':check['id']},'assertion':'text','expected':'内容'})
            candidate['checks'].reverse()
        return candidate
    monkeypatch.setattr(project_service,'generate_project_phase',material)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'页面项目'},context,repository=repository)
    assert calls==['plan']+['build_step','build_checks']*4
    assert repository.get_owned('alice',exercise.id).artifact_public

@pytest.mark.asyncio
@pytest.mark.parametrize('negative',['partial','missing','unknown-check'])
async def test_auxiliary_negative_material_does_not_block_working_project(repository,exercise,pipeline,monkeypatch,negative):
    context,calls,_=pipeline
    original=project_service.generate_project_phase
    async def material(owner,snapshot,phase,data):
        candidate=await original(owner,snapshot,phase,data)
        if phase=='build_checks':
            if negative=='partial': candidate['faultyFiles'].pop('/src/styles.css')
            elif negative=='missing':
                candidate.pop('faultyFiles'); candidate.pop('faultyCheckId')
            else: candidate['faultyCheckId']='not-a-current-check'
        return candidate
    monkeypatch.setattr(project_service,'generate_project_phase',material)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'页面项目'},context,repository=repository)
    row=repository.get_owned('alice',exercise.id)
    assert row.artifact_public['validationSummary']['passed']
    assert calls==['plan']+['build_step','build_checks']*4
    if negative=='partial':
        candidate=row.candidate_private['completed'][-1]['candidate']
        assert candidate['faultyFiles']['/src/styles.css']==candidate['referenceFiles']['/src/styles.css']
    else: assert row.artifact_public['validationSummary']['qualityWarnings']


def test_scope_schema_accepts_empty_nested_scope_but_rejects_nesting():
    from app.pbl.project_schemas import UiTarget
    target=UiTarget.model_validate({'role':'button','name':'操作','within':{'testId':'row','within':None}})
    assert target.within.testId=='row'
    with pytest.raises(ValueError):
        UiTarget.model_validate({'role':'button','within':{'testId':'row','within':{'testId':'outer'}}})


def test_action_locator_alias_is_canonicalized_without_hiding_conflicts():
    from app.pbl.project_schemas import UiAction
    raw={'type':'click','target':{'role':'button','name':'变更'},'within':{'testId':'row','index':1}}
    action=UiAction.model_validate(raw)
    assert action.target.within.testId=='row' and action.target.within.index==1
    assert 'within' not in action.model_dump(exclude_none=True)
    with pytest.raises(ValueError,match='冲突'):
        UiAction.model_validate({**raw,'target':{**raw['target'],'within':{'testId':'other'}}})
