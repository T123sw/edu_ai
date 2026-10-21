import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.api import practice as api
from app.practice import service
from app.practice.experiment.contracts import ExperimentSpec, digest
from app.practice.experiment.repository import ExperimentRepository, SaveRun, FreezeQuestion, Conflict, Missing
EXAMPLES=Path(__file__).resolve().parents[2]/'app/practice/skills/design-experiment/examples'
def spec(name='quicksort'):return ExperimentSpec.model_validate_json((EXAMPLES/f'{name}.json').read_text()).model_dump()
def package():
    s=spec();return {'spec':s,'revision':digest(s)}
def view():
    p=package();state=p['spec']['checkpoints']['start']
    return {'run_id':str(uuid4()),'revision':p['revision'],'seq':0,'phase':'demonstrate','index':0,'attempt_id':str(uuid4()),'attempt_before':state,'last_input':{},'state':state,'feedback':'','verdict':'','events':[],'snapshots':{'0':state}}
def advanced(v):
    v=deepcopy(v);before=deepcopy(v['state']);v['seq']+=1;v['state']={**before,'selected':4};n=v['seq'];v['snapshots'][f'{n}:before']=before;v['snapshots'][str(n)]=v['state']
    v['events'].append({'id':str(uuid4()),'seq':n,'actor':'system','phase':'demonstrate','type':'action','task_id':None,'attempt_id':v['attempt_id'],'before':f'{n}:before','after':str(n),'at':1,'command':{'action':'select','input':{'index':4}}})
    return v
@pytest.mark.parametrize('name',['quicksort','friction','probability'])
def test_cross_domain_contract(name):assert spec(name)['protocol']=='edu-experiment/1'
@pytest.mark.parametrize('mutate',[
    lambda s:s['tasks'][0].update(allowed_actions=['absent']),lambda s:s['tasks'][0].update(checks=[]),lambda s:s.update(validation_cases=s['validation_cases'][:1]),lambda s:s['demo_steps'][0]['commands'][0].update(input={'index':99}),lambda s:s['tasks'][0]['checks'][0].update(path=['after','__proto__'])])
def test_invalid_design_rejected(mutate):
    s=spec();mutate(s)
    with pytest.raises(ValueError):ExperimentSpec.model_validate(s)
@pytest.fixture
def repository(tmp_path,monkeypatch):
    monkeypatch.setenv('APP_STATE_PERSISTENCE_MODE','json');return ExperimentRepository(service.PracticeStore(root=tmp_path))
def test_append_only_idempotence_conflicts_and_frozen_context(repository):
    v=view();p=package();first=SaveRun(expected_seq=-1,view=v)
    assert repository.save('alice','lab',p,first)==repository.save('alice','lab',p,first)
    newer=advanced(v);repository.save('alice','lab',p,SaveRun(expected_seq=0,view=newer))
    frozen=repository.freeze('alice','lab',p,v['run_id'],FreezeQuestion(expected_seq=1,question='为什么选择这里？'))
    newer2=advanced(newer);repository.save('alice','lab',p,SaveRun(expected_seq=1,view=newer2))
    assert repository.context('alice','lab',frozen['context_id'])['state_revision']==1
    assert len(frozen['events'])==1 and frozen['scientifically_verified'] is False
    with pytest.raises(Conflict):repository.save('alice','lab',p,SaveRun(expected_seq=1,view=advanced(newer2)))
    changed=advanced(newer2);changed['events'][0]['actor']='user'
    with pytest.raises(Conflict):repository.save('alice','lab',p,SaveRun(expected_seq=2,view=changed))
    with pytest.raises(Missing):repository.get('bob','lab',v['run_id'])
    with pytest.raises(Missing):repository.context('bob','lab',frozen['context_id'])
    with pytest.raises(Conflict):repository.freeze('alice','lab',p,v['run_id'],FreezeQuestion(expected_seq=1,question='旧状态？'))
def test_missing_snapshot_rejected():
    v=advanced(view());del v['snapshots']['1:before']
    with pytest.raises(ValueError):SaveRun(expected_seq=0,view=v)

def test_two_stage_packages_reject_removed_phase_and_legacy_remains_readable(repository):
    p = package(); p['spec']['phases'] = ['demonstrate', 'explore']
    v = view(); v['phase'] = 'guided'
    with pytest.raises(ValueError, match='不支持此阶段'):
        repository.save('alice', 'two-stage', p, SaveRun(expected_seq=-1, view=v))
    repository.save('alice', 'legacy', package(), SaveRun(expected_seq=-1, view=v))
    assert repository.get('alice', 'legacy', v['run_id'])['view']['phase'] == 'guided'
def test_api_ownership_and_legacy_ask_boundary(monkeypatch,repository):
    monkeypatch.setattr(api,'get_job',lambda _:SimpleNamespace(owner_user_id='alice',kind=api.JobKind.GENERATE_PRACTICE,status=api.JobStatus.SUCCEEDED))
    monkeypatch.setattr(api,'PracticeStore',lambda:repository.store);repository.store.put('alice','lab',{'html':'ready','experiment':package()})
    with pytest.raises(HTTPException) as error:api.latest_experiment_run('lab',{'username':'bob'})
    assert error.value.status_code==404
    with pytest.raises(HTTPException) as error:asyncio.run(api.ask('lab',api.Question(question='为什么？'),{'username':'alice'}))
    assert error.value.status_code==409
@pytest.mark.parametrize('valid',[True,False])
def test_new_pipeline_skill_native_stages_and_failed_publish_guard(monkeypatch,repository,valid):
    s=spec();calls=[];html='<!doctype html><html><head></head><body>experiment</body></html>';science={k:['模型约束'] for k in ['core_formulas','mechanism','constraints','forbidden_errors']}
    async def complete(owner,prompt,**kw):
        calls.append(prompt)
        if len(calls)==1:return json.dumps(s)
        if len(calls)==2:return json.dumps(science)
        if len(calls)==5:return '{"metadata":{"title":"实验"}}'
        return html
    monkeypatch.setattr(service,'complete',complete);monkeypatch.setattr(service,'PracticeStore',lambda:repository.store)
    monkeypatch.setattr(service,'validate_html',lambda html,**kw:{'ok':valid,'issues':[] if valid else ['demo failed']})
    context=SimpleNamespace(owner_user_id='alice',task_id='new',is_cancel_requested=lambda:False,progress=lambda *_:None)
    if valid:
        asyncio.run(service.generate({'topic':'基准选择','protocol':'edu-experiment/1'},context));artifact=repository.store.get('alice','new')
        assert artifact['experiment']['revision']==digest(s) and len(artifact['native_calls'])==4
        assert 'EduExperiment.register' in calls[2] and 'EduExperiment.register' in calls[3] and 'design-experiment' in calls[0]
    else:
        with pytest.raises(ValueError,match='未通过'):asyncio.run(service.generate({'topic':'测试','protocol':'edu-experiment/1'},context))
        assert not repository.store.get('alice','new')

def test_teaching_tools_page_all_evidence_and_bind_delayed_answers(repository):
    from app.practice.experiment.teaching import EvidenceRequest, read_evidence, response_matches_context
    v=advanced(advanced(view()));repository.save('alice','lab',package(),SaveRun(expected_seq=-1,view=v))
    context=repository.freeze('alice','lab',package(),v['run_id'],FreezeQuestion(expected_seq=v['seq'],question='这一步？'))
    page=read_evidence(context,EvidenceRequest(tool='list_events',limit=1))
    assert len(page['result']['items'])==1 and page['result']['has_more']
    next_page=read_evidence(context,EvidenceRequest(tool='list_events',after_seq=page['result']['next_seq']))
    assert len(next_page['result']['items'])==1 and not next_page['result']['has_more']
    diff=read_evidence(context,EvidenceRequest(tool='compare_snapshots',snapshot_id='0',other_snapshot_id='1'))
    assert diff['result']['changes'][0]['field']=='selected'
    assert len(read_evidence(context,EvidenceRequest(tool='get_attempt'))['result']['events'])==2
    assert response_matches_context(page,context)
    assert not response_matches_context({**page,'state_revision':999},context)
    with pytest.raises(ValueError):read_evidence(context,EvidenceRequest(tool='get_snapshot',snapshot_id='999'))

def test_sql_repository_path_keeps_owned_records(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from app.database import AppStateRecord
    from app.persistence.postgres_app_state_repository import PostgresAppStateRepository
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    AppStateRecord.__table__.create(engine)
    try:
        repository=ExperimentRepository(service.PracticeStore(root=tmp_path,repository=PostgresAppStateRepository(engine)))
        v=view();repository.save('alice','lab',package(),SaveRun(expected_seq=-1,view=v))
        assert repository.latest('alice','lab')['view']==v
        assert repository.latest('bob','lab') is None
        repository.save('alice','lab',package(),SaveRun(expected_seq=0,view=advanced(v)))
        with pytest.raises(Conflict):repository.save('alice','lab',package(),SaveRun(expected_seq=0,view=advanced(v)))
    finally:engine.dispose()

def test_design_json_roundtrip_has_stable_revision():
    s=spec();assert digest(s)==digest(ExperimentSpec.model_validate(json.loads(json.dumps(s))).model_dump())

def test_concurrent_writers_keep_one_history(repository):
    from concurrent.futures import ThreadPoolExecutor
    v=view();repository.save('alice','lab',package(),SaveRun(expected_seq=-1,view=v))
    def write():
        try:
            repository.save('alice','lab',package(),SaveRun(expected_seq=0,view=advanced(v)));return 'saved'
        except Conflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(lambda _:write(),range(2)))
    assert sorted(results)==['conflict','saved']
    assert repository.get('alice','lab',v['run_id'])['view']['seq']==1

def test_submission_schema_expresses_mutually_exclusive_modes():
    schema=ExperimentSpec.model_json_schema()
    assert schema['properties']['tasks']['items']['discriminator']['propertyName']=='submission'
    assert schema['$defs']['ExplicitSubmissionTask']['properties']['submit_action']['type']=='null'
    s=spec();s['tasks'][0]['submission']='explicit_submit'
    with pytest.raises(ValueError) as error:ExperimentSpec.model_validate(s)
    assert error.value.errors()[0]['loc']==('tasks',0,'explicit_submit','submit_action')


def test_manual_submission_conflict_is_normalized_without_changing_actions_or_checks():
    from app.practice.experiment.design import normalize_design
    original=spec();original['tasks'][0]['submission']='explicit_submit';unchanged=deepcopy(original)
    normalized,adjustments=normalize_design(original)
    assert original==unchanged
    assert adjustments[0]['path']==['tasks',0,'submit_action']
    assert normalized['tasks'][0]['submit_action'] is None
    assert normalized['tasks'][0]['submission']=='explicit_submit'
    assert normalized['tasks'][0]['checks']==original['tasks'][0]['checks']
    assert normalized['actions']==original['actions']
    ExperimentSpec.model_validate(normalized)
    auto=spec();auto['tasks'][0]['submit_action']='not-an-action'
    normalized,adjustments=normalize_design(auto)
    assert adjustments==[]
    with pytest.raises(ValueError):ExperimentSpec.model_validate(normalized)


def test_design_conflict_recovery_keeps_owned_diagnostics_and_avoids_extra_model_call(repository):
    from app.practice.experiment.design import design
    s=spec();s['tasks'][0]['submission']='explicit_submit';calls=[]
    async def complete(*args,**kwargs):calls.append(args);return json.dumps(s)
    context=SimpleNamespace(owner_user_id='alice',task_id='design',is_cancel_requested=lambda:False)
    result,adjustments=asyncio.run(design('冒泡排序',context,complete,repository.store))
    assert len(calls)==1 and result['tasks'][0]['submit_action'] is None and adjustments
    diagnostic=repository.store.get('alice','design:design-diagnostics')
    assert diagnostic['attempts'][0]['status']=='valid'
    assert json.loads(diagnostic['attempts'][0]['raw_output'])['tasks'][0]['submit_action']=='select'
    assert repository.store.get('bob','design:design-diagnostics')=={}


def test_failed_repair_reports_model_conflict_and_keeps_both_attempts(repository):
    from app.practice.experiment.design import design
    calls=[]
    async def complete(*args,**kwargs):calls.append(args);return '{}'
    context=SimpleNamespace(owner_user_id='alice',task_id='bad-design',is_cancel_requested=lambda:False)
    with pytest.raises(ValueError,match='无需修改实验主题'):
        asyncio.run(design('冒泡排序',context,complete,repository.store))
    assert len(calls)==2
    attempts=repository.store.get('alice','bad-design:design-diagnostics')['attempts']
    assert len(attempts)==2 and attempts[-1]['errors']
    assert 'input' not in attempts[-1]['errors'][0]


def test_condition_paths_describe_roots_and_report_exact_repair_location():
    schema=ExperimentSpec.model_json_schema()['$defs']['Condition']
    assert schema['properties']['path']['prefixItems'][0]['enum']==['before','after','input']
    for field,path in [('path',['selected']),('right_path',['array']),('path',['after','__proto__'])]:
        s=spec();s['demo_steps'][0]['assertions'][0][field]=path
        with pytest.raises(ValueError) as error:ExperimentSpec.model_validate(s)
        assert error.value.errors()[0]['loc']==('demo_steps',0,'assertions',0,field)


def test_initial_observation_and_conventional_action_ids_are_valid():
    s=spec();intro=deepcopy(s['demo_steps'][0]);intro.update(id='observe',commands=[])
    s['demo_steps'].insert(0,intro)
    extra=deepcopy(s['actions'][0]);extra['id']='Auto_step';extra['phases']=['explore'];s['actions'].append(extra)
    validated=ExperimentSpec.model_validate(s)
    assert validated.demo_steps[0].commands==[]
    s['demo_steps'][0]['assertions']=[]
    with pytest.raises(ValueError):ExperimentSpec.model_validate(s)
