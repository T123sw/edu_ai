import asyncio
import json
from uuid import uuid4
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.api import practice as api
from app.practice import service
from app.practice.runtime import wrap_html
from app.services.job_store import JobKind, JobStatus

@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_STATE_PERSISTENCE_MODE','json')
    store=service.PracticeStore(root=tmp_path)
    monkeypatch.setattr(api,'PracticeStore',lambda:store)
    return store

def job(owner='alice', status=JobStatus.SUCCEEDED):
    return SimpleNamespace(owner_user_id=owner,kind=JobKind.GENERATE_PRACTICE,status=status)

def test_owner_cannot_read_or_modify_another_lab(monkeypatch,storage):
    monkeypatch.setattr(api,'get_job',lambda _:job())
    for operation in [lambda:api.detail('lab',{'username':'bob'}),lambda:api.observe('lab',api.Observation(),{'username':'bob'}),lambda:asyncio.run(api.ask('lab',api.Question(question='提示'),{'username':'bob'}))]:
        with pytest.raises(HTTPException) as error:operation()
        assert error.value.status_code==404

def test_observation_survives_store_reload_and_is_scoped(monkeypatch,storage):
    monkeypatch.setattr(api,'get_job',lambda _:job())
    storage.put('alice','lab',{'html':'x','plan':{'steps':[{}]}})
    api.observe('lab',api.Observation(state={'parameters':{'mu':.3},'results':{'distance':17}},note='摩擦越大，距离越短'),{'username':'alice'})
    assert storage.get('alice','lab:journal')['observations'][0]['state']['results']['distance']==17
    assert storage.get('bob','lab:journal')=={}

def test_no_learning_record_before_generation_succeeds(monkeypatch,storage):
    monkeypatch.setattr(api,'get_job',lambda _:job(status=JobStatus.RUNNING))
    storage.put('alice','lab',{'html':'candidate'})
    with pytest.raises(HTTPException) as error:api.observe('lab',api.Observation(),{'username':'alice'})
    assert error.value.status_code==409

def test_tutor_receives_actual_state_but_cannot_mark_steps_complete(monkeypatch,storage):
    monkeypatch.setattr(api,'get_job',lambda _:job())
    storage.put('alice','lab',{'html':'x','plan':{'steps':[{'title':'实验'}]},'science':{'constraints':['能量守恒']}})
    captured={}
    async def fake(owner,prompt,**kwargs):
        captured.update(json.loads(prompt)); return '试着增大摩擦系数，比较停车距离。'
    monkeypatch.setattr(api,'complete',fake)
    result=asyncio.run(api.ask('lab',api.Question(question='下一步？',state={'results':{'distance':17}}),{'username':'alice'}))
    assert captured['browser_reported_state']['results']['distance']==17
    assert result['messages'][-1]['role']=='assistant'
    assert 'completed' not in result

def test_duplicate_request_does_not_enqueue_twice(monkeypatch):
    jobs={}; calls=[]
    monkeypatch.setattr(api,'get_job',lambda key:jobs.get(key))
    monkeypatch.setattr(api,'upstream',lambda:None)
    monkeypatch.setattr(api.runtime_config_resolver,'capture_snapshot',lambda _: {})
    def create(**kwargs):
        value=SimpleNamespace(input_summary=kwargs['input_summary'],model_dump=lambda **_: {'status':'queued'})
        jobs[kwargs['edu_job_id']]=value
        return value
    monkeypatch.setattr(api,'create_job',create)
    monkeypatch.setattr(api,'enqueue_platform_task',lambda **kw:calls.append(kw) or kw['job'])
    payload=api.CreatePractice(topic='摩擦力',request_id=uuid4())
    assert api.create(payload,{'username':'alice'})==api.create(payload,{'username':'alice'})
    assert len(calls)==1
    with pytest.raises(HTTPException):api.create(payload.model_copy(update={'topic':'其他'}),{'username':'alice'})

def test_runtime_blocks_external_connections_and_injects_before_generated_scripts():
    html=wrap_html('```html\n<!DOCTYPE html><html><head><script>test()</script></head><body></body></html>\n```')
    assert html.index('Content-Security-Policy')<html.index('<script>')
    assert "connect-src 'none'" in html and "form-action 'none'" in html
    assert html.index('window.EduPractice=')<html.index('test()')
    with pytest.raises(ValueError):wrap_html('<html>truncated')

def test_failed_browser_checks_never_publish_artifact(monkeypatch,storage):
    from app.practice import native
    monkeypatch.setattr(service,'PracticeStore',lambda:storage)
    monkeypatch.setattr(service,'upstream',lambda:SimpleNamespace(anthropic_scientific_prompt=lambda _: 'science',visual_engine_prompt=lambda *_:'html'))
    plan={k:'test' for k in ['subject','concept_name','concept_overview','mastery_points','design_idea']}
    plan['steps']=[{'title':'t','instruction':'i','question':'q'}]*3
    outputs=iter([json.dumps(plan),'<html><head></head><body></body></html>'])
    async def generated(*args):
        return {'html':'<html><head></head><body></body></html>', 'science':{}, 'generation_info':{}, 'native_calls':[]}
    monkeypatch.setattr(native,'generate_native',generated)
    monkeypatch.setattr(native,'postprocess_native',lambda value:value)
    async def fake(*args,**kwargs):return next(outputs)
    monkeypatch.setattr(service,'complete',fake)
    monkeypatch.setattr(service,'validate_html',lambda _,**kw: {'ok':False,'issues':['result did not change']})
    context=SimpleNamespace(owner_user_id='alice',task_id='lab',progress=lambda *_:None,is_cancel_requested=lambda:False)
    with pytest.raises(ValueError,match='未通过'):asyncio.run(service.generate({'topic':'topic'},context))
    assert storage.get('alice','lab')=={}
