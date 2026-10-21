from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app.api import pbl
from app.auth import get_current_user
from app.chat.tasks.task_store import TaskStore
from app.services import job_store

@pytest.fixture
def client(repository,tmp_path,monkeypatch):
    # All job writes stay in the isolated directory established by isolated.py.
    store=TaskStore(db_path=tmp_path/'tasks.db')
    monkeypatch.setattr(pbl,'get_task_store',lambda:store)
    monkeypatch.setattr(pbl.runtime_config_resolver,'capture_snapshot',lambda owner:{})
    app=FastAPI()
    app.include_router(pbl.router)
    app.dependency_overrides[pbl.repository]=lambda:repository
    app.dependency_overrides[get_current_user]=lambda:{'username':'alice'}
    client=TestClient(app)
    client.task_store=store
    yield client


def test_create_idempotent_and_enqueue_recovery(client,monkeypatch):
    request={'topic':'快速排序','request_id':str(uuid4())}
    original=pbl.enqueue_platform_task
    monkeypatch.setattr(pbl,'enqueue_platform_task',lambda **kw:kw['job'])
    first=client.post('/api/pbl',json=request)
    assert first.status_code==202
    identifier=first.json()['exerciseId']
    assert client.task_store.get_durable(identifier) is None
    monkeypatch.setattr(pbl,'enqueue_platform_task',original)
    second=client.post('/api/pbl',json=request)
    assert second.json()==first.json()
    assert client.task_store.get_durable(identifier).command['exercise_id']==identifier
    monkeypatch.setattr(pbl,'enqueue_platform_task',lambda **kw:pytest.fail('must not enqueue existing durable task'))
    assert client.post('/api/pbl',json=request).json()==first.json()
    assert client.post('/api/pbl',json={**request,'topic':'快排'}).status_code==409
    assert client.post('/api/pbl',json={**request,'topic':'二叉树'}).status_code==409


def test_public_shapes_private_data_excluded(client,ready_exercise,candidate,patch,run):
    job_store.create_job(kind=job_store.JobKind.GENERATE_PBL,edu_job_id=ready_exercise.current_job_id,
        owner_user_id='alice',scope_type='pbl',scope_id=ready_exercise.id,input_summary={'topic':'快速排序'})
    detail=client.get('/api/pbl/'+ready_exercise.id)
    assert detail.status_code==200
    assert set(detail.json())=={'exerciseId','job','artifact'}
    assert candidate.referenceSolution not in detail.text and 'referenceSolution' not in detail.text
    listing=client.get('/api/pbl').json()
    assert listing['items'][0]['exerciseId']==ready_exercise.id
    assert client.get('/api/pbl/'+ready_exercise.id+'/workspace').json()['revision']==0
    assert client.put('/api/pbl/'+ready_exercise.id+'/workspace',json=patch).json()['revision']==1
    assert client.post('/api/pbl/'+ready_exercise.id+'/runs',json=run).status_code==200
    assert len(client.get('/api/pbl/'+ready_exercise.id+'/runs').json()['items'])==1


def test_owner_isolation_every_route(client,ready_exercise,patch,run):
    client.app.dependency_overrides[get_current_user]=lambda:{'username':'bob'}
    base='/api/pbl/'+ready_exercise.id
    for method,path,payload in [('get',base,None),('get',base+'/workspace',None),
        ('put',base+'/workspace',patch),('post',base+'/runs',run),('get',base+'/runs',None)]:
        response=client.request(method,path,**({'json':payload} if payload else {}))
        assert response.status_code==404,response.text
    assert client.get('/api/pbl').json()['items']==[]


def test_not_ready_and_invalid_fields(client,exercise,patch):
    assert client.get('/api/pbl/'+exercise.id+'/workspace').status_code==409
    assert client.put('/api/pbl/'+exercise.id+'/workspace',json={**patch,'owner':'bob'}).status_code==422


def test_lost_enqueue_ack_reuses_durable_and_recovers_public_status(client,monkeypatch):
    request={'topic':'快速排序','request_id':str(uuid4())}
    created=client.post('/api/pbl',json=request).json()
    job_store.update_job(created['jobId'],status=job_store.JobStatus.FAILED,error_code='TASK_ENQUEUE_FAILED',error_message='lost acknowledgement')
    monkeypatch.setattr(pbl,'enqueue_platform_task',lambda **kw:pytest.fail('must reuse durable task'))
    restored=client.post('/api/pbl',json=request)
    assert restored.status_code==202 and restored.json()['status']=='queued'
    assert restored.json()['jobId']==created['jobId']


def test_actual_enqueue_failure_can_be_recovered(client,monkeypatch):
    request={'topic':'快速排序','request_id':str(uuid4())}
    original=client.task_store.enqueue
    def fail(**kwargs): raise RuntimeError('queue unavailable')
    monkeypatch.setattr(client.task_store,'enqueue',fail)
    failed=client.post('/api/pbl',json=request)
    assert failed.status_code==202 and failed.json()['status']=='failed'
    monkeypatch.setattr(client.task_store,'enqueue',original)
    recovered=client.post('/api/pbl',json=request)
    assert recovered.status_code==202 and recovered.json()['status']=='queued'
    assert recovered.json()['exerciseId']==failed.json()['exerciseId']
    assert client.task_store.get_durable(recovered.json()['jobId']) is not None


def test_queue_wait_does_not_consume_pbl_execution_window(client):
    import time
    from app.pbl.generation_policy import PBL_GENERATION_TIMEOUT_SECONDS
    response=client.post('/api/pbl',json={'topic':'独立页面','request_id':str(uuid4())})
    task=client.task_store.get_durable(response.json()['jobId'])
    assert task.command['execution_timeout_seconds']==PBL_GENERATION_TIMEOUT_SECONDS
    # A long queue wait still leaves the full, bounded generation window.
    started=time.time()+1200
    claimed=client.task_store.claim_next(lease_owner='worker',lease_seconds=60,now=started)
    assert claimed.task_id==task.task_id
    assert claimed.deadline_at==started+PBL_GENERATION_TIMEOUT_SECONDS
    assert claimed.deadline_at>task.deadline_at
