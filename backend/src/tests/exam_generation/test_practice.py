import asyncio
from copy import deepcopy
import json
from uuid import uuid4
from types import SimpleNamespace
import pytest
from fastapi import HTTPException,FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select
from app.database.models import AppStateRecord,DurableTaskModel
from app.database.session import database_session
from app.exam_practice.service import PracticeService,RUN,TURN
from app.exam_practice.contracts import Start,Draft,Submit,Finish,Ask
from app.exam_practice.worker import PracticeWorker
from app.exam_generation.repository import NAMESPACE
from test_blueprint_validation import complete_paper

@pytest.fixture
def svc(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'practice.db'),connect_args={'check_same_thread':False})
    AppStateRecord.__table__.create(engine);DurableTaskModel.__table__.create(engine)
    data=complete_paper();data.update(id='paper1');data['request']['requirement']='数据结构练习'
    with database_session(engine=engine) as db:db.add(AppStateRecord(namespace=NAMESPACE,record_key='paper1',owner_user_id='alice',payload=data))
    return PracticeService(engine)

def run(svc):return svc.start('alice','paper1',Start(request_id=uuid4()))
def choice(*ids):return {'option_ids':list(ids),'blank_values':[],'text':''}
def blanks(*values):return {'option_ids':[],'blank_values':list(values),'text':''}
def submit(svc,r,q='q_0',answer=None,rid=None):return svc.submit('alice','paper1',r['id'],q,Submit(request_id=rid or uuid4(),answer=answer or choice('E')))
def worker(svc,task_id,model):
    with database_session(engine=svc.engine) as db:command=deepcopy(db.get(DurableTaskModel,task_id).command)
    ctx=SimpleNamespace(owner_user_id='alice',task_id=task_id,is_cancel_requested=lambda:False,is_lease_valid=lambda:True)
    return PracticeWorker(svc,lambda _:model)(command,ctx)
class Model:
    def __init__(self,value):self.value=value;self.messages=[]
    async def complete(self,messages,tools,deadline):
        self.messages=deepcopy(messages)
        if isinstance(self.value,Exception):raise self.value
        return {'content':json.dumps(self.value,ensure_ascii=False),'calls':[]}

def test_public_paper_no_answers_and_resume(svc):
    p=svc.paper('alice','paper1');assert p['answer_count']==15
    assert 'correct_answer' not in json.dumps(p) and 'Proof' not in json.dumps(p)
    first=run(svc);assert run(svc)['id']==first['id']
    with pytest.raises(HTTPException) as error:svc.paper('bob','paper1')
    assert error.value.status_code==404

def test_cross_device_draft_revision_and_late_save(svc):
    r=run(svc)
    d=svc.draft('alice','paper1',r['id'],'q_0',Draft(answer=choice('A'),expected_revision=0));assert d['revision']==1
    assert svc.get_run('alice','paper1',r['id'])['drafts']['q_0']['answer']==choice('A')
    with pytest.raises(HTTPException) as e:svc.draft('alice','paper1',r['id'],'q_0',Draft(answer=choice('B'),expected_revision=0))
    assert e.value.status_code==409
    submit(svc,r)
    with pytest.raises(HTTPException):svc.draft('alice','paper1',r['id'],'q_0',Draft(answer=choice('A'),expected_revision=1))

def test_submission_idempotency_and_immutable_history(svc):
    r=run(svc);rid=uuid4();one=submit(svc,r,rid=rid);two=submit(svc,r,rid=rid)
    assert one['id']==two['id'] and one['correct'] is True
    with pytest.raises(HTTPException):submit(svc,r,answer=choice('A'),rid=rid)
    submit(svc,r,answer=choice('A'))
    attempts=svc.get_run('alice','paper1',r['id'])['answers']['q_0'];assert len(attempts)==2 and attempts[0]['correct'] is True and attempts[1]['correct'] is False

def test_finish_bulk_preserves_history_and_empty_questions(svc):
    r=run(svc);request=Finish(request_id=uuid4(),answers={'q_0':choice('E'),'q_10':blanks('1','2')})
    ended=svc.finish('alice','paper1',r['id'],request);assert ended['status']=='finished'
    assert len(svc.finish('alice','paper1',r['id'],request)['answers'])==2
    assert svc.runs('alice','paper1')[0]['submitted']==2
    new=run(svc);assert new['id']!=r['id'] and new['answers']=={}
    assert len(svc.get_run('alice','paper1',r['id'])['answers'])==2
    with pytest.raises(HTTPException):submit(svc,r,q='q_1')

@pytest.mark.parametrize('question,answer',[('q_0',choice('Z')),('q_0',choice('A','B')),('q_10',blanks('one')),('unknown',choice('A'))])
def test_invalid_answer_does_not_save(svc,question,answer):
    r=run(svc)
    with pytest.raises(HTTPException):submit(svc,r,q=question,answer=answer)
    assert svc.get_run('alice','paper1',r['id'])['answers']=={}

def test_evaluation_failure_keeps_answer_then_retry(svc):
    r=run(svc);a=submit(svc,r,q='q_10',answer=blanks('一','二'))
    assert a['status']=='pending_evaluation'
    worker(svc,a['task_id'],Model(RuntimeError('offline')))
    saved=svc.get_run('alice','paper1',r['id'])['answers']['q_10'][0]
    assert saved['status']=='evaluation_failed' and saved['answer']['blank_values']==['一','二']
    retry=svc.retry_evaluation('alice','paper1',r['id'],'q_10',a['id']);worker(svc,retry['task_id'],Model({'supported':True,'feedback':'表达等价，两个空均符合。'}))
    saved=svc.get_run('alice','paper1',r['id'])['answers']['q_10'][0]
    assert saved['correct'] is True and saved['evaluator']=='model'

def test_stale_worker_cannot_replace_new_evaluation(svc):
    r=run(svc);a=submit(svc,r,q='q_10',answer=blanks('1','2'))
    with database_session(engine=svc.engine) as db:db.get(DurableTaskModel,a['task_id']).status='failed'
    new=svc.retry_evaluation('alice','paper1',r['id'],'q_10',a['id'])
    model=Model({'supported':False,'feedback':'old'});worker(svc,a['task_id'],model)
    assert model.messages==[] and new['task_id']!=a['task_id']

def test_agent_context_is_frozen_and_shared_for_paper(svc):
    r=run(svc);a=submit(svc,r,answer=choice('A'))
    request=Ask(request_id=uuid4(),question='解释我这次为什么选错',run_id=r['id'],question_id='q_0',attempt_id=a['id'])
    turn=svc.ask('alice','paper1',request);assert 'context' not in turn
    assert svc.ask('alice','paper1',request)['id']==turn['id']
    submit(svc,r,answer=choice('E'))
    model=Model({'answer':'根据你提交的 A 选项，需要注意边界条件。'});worker(svc,turn['task_id'],model)
    context=json.loads(model.messages[-1]['content'])['context']
    assert context['practice']['answer']==choice('A') and context['question']['question_id']=='q_0'
    result=svc.turns('alice','paper1')[0];assert result['status']=='succeeded' and result['citations'][0]['question_id']=='q_0'
    with pytest.raises(HTTPException):svc.ask('alice','paper1',Ask(request_id=uuid4(),question='讲解',run_id=r['id'],question_id='q_1',attempt_id=a['id']))

def test_cancel_and_delete_fence_late_workers(svc):
    r=run(svc);turn=svc.ask('alice','paper1',Ask(request_id=uuid4(),question='提示',run_id=r['id'],question_id='q_0'))
    svc.control('alice','paper1',turn['id'],'cancel');m=Model({'answer':'late'});worker(svc,turn['task_id'],m);assert m.messages==[]
    retry=svc.control('alice','paper1',turn['id'],'retry');svc.delete('alice','paper1');worker(svc,retry['task_id'],m)
    with database_session(engine=svc.engine) as db:
        assert not list(db.scalars(select(AppStateRecord).where(AppStateRecord.namespace.in_([RUN,TURN,NAMESPACE]))))
        assert all(t.cancel_requested for t in db.scalars(select(DurableTaskModel)))

def test_api_round_trip_and_owner_boundary(svc):
    from app.api import exam_practice as api
    app=FastAPI();app.include_router(api.router);app.dependency_overrides[api.service]=lambda:svc
    app.dependency_overrides[api.get_current_user]=lambda:{'username':'alice'}
    with TestClient(app) as client:
        assert client.get('/api/exam-generations/paper1/practice').status_code==200
        response=client.post('/api/exam-generations/paper1/practice-runs',json={'request_id':str(uuid4())});assert response.status_code==200
        rid=response.json()['id'];path=f'/api/exam-generations/paper1/practice-runs/{rid}'
        assert client.post(path+'/answers/q_0',json={'request_id':str(uuid4()),'answer':choice('E')}).json()['correct'] is True
        app.dependency_overrides[api.get_current_user]=lambda:{'username':'bob'}
        assert client.get(path).status_code==404
