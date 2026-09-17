import asyncio
from uuid import uuid4
import pytest
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database import Base, User
from app.course_preparation.production_service import ProductionService
from app.self_learning.preparation_adapter import PreparationAdapter
from tests.self_learning.test_memory_lifecycle import memory, agent_service, live_service, repository
from tests.self_learning.test_agent_runtime import accept, request

@pytest.fixture
def preparation(memory):
    from app.course_preparation.production_models import TABLES
    engine = memory.engine
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in (
        'users','course_preparations','course_preparation_attempts','course_preparation_events',*TABLES)])
    with Session(engine) as db, db.begin():
        for name in ('alice','bob'):
            db.add(User(user_id='id-'+name,username=name,password_hash='test-only',role='student'))
    service = ProductionService(memory.learning, engine)
    adapter = PreparationAdapter(memory.learning, service)
    memory.learning.preparations = adapter
    return adapter

def turn(adapter, question='请帮我生成并保存一份关于变量的补充文档'):
    first = accept(adapter.learning, request(question))
    return adapter.learning.turn_repository.get('alice',first['turn_id'])

def args(**updates):
    return {'operation':'supplement_node','goal':'保存变量的补充解释和例子','resource_types':['report'],**updates}

def test_explanation_or_ambiguous_revision_never_submits(preparation):
    source = turn(preparation,'解释变量赋值，不要生成或保存资料')
    with pytest.raises(HTTPException):
        preparation.submit(source,args(),{},'no-write')
    assert preparation.list('alice','course') == []
    source['request']['question']='请修改保存那份文档'
    with pytest.raises(HTTPException):
        preparation.submit(source,args(operation='revise_resource'),{},'ambiguous')

def test_submission_is_idempotent_and_keeps_authenticated_origin(preparation):
    source = turn(preparation)
    first = preparation.submit(source,args(),{},'operation')
    second = preparation.submit(source,args(),{},'operation')
    assert first['preparation_id'] == second['preparation_id']
    assert first['status'] == 'accepted'
    status = preparation.get('alice',first['preparation_id'])
    assert status['origin_ref']['conversation_id'] == source['session_id']
    with pytest.raises(HTTPException):
        preparation.get('bob',first['preparation_id'])

def test_submit_response_loss_replays_same_preparation(preparation):
    source = turn(preparation)
    preparation.submit(source,args(),{},'lost-response')
    replay = PreparationAdapter(preparation.learning,preparation.service).submit(source,args(),{},'lost-response')
    assert len(preparation.list('alice','course')) == 1
    assert replay['preparation_id'] == preparation.list('alice','course')[0]['preparation_id']

async def producer(owner, system, data, snapshot):
    if '检查者' in system:
        return {'passed':True,'issues':[]}
    return {'title':'变量补充解释','content':'# 变量\n\n变量保存一个值，赋值会让名称指向新的值。\n\n例如 x = 1，再执行 x = 2，此时 x 的值是 2。\n\n常见误区是把赋值当成数学等式；程序中的赋值是一条操作指令，执行顺序影响最后结果。\n\n可以逐行追踪值的变化来检查自己的理解。'}

def submit_and_run(preparation, question=None, **updates):
    source=turn(preparation,question) if question else turn(preparation)
    receipt=preparation.submit(source,args(**updates),{},'production')
    preparation.service.model_json=producer
    assert preparation.service.run_once()
    result=preparation.get('alice',receipt['preparation_id'])
    assert result['status']=='succeeded',result
    return source,result

def test_real_storage_delivery_only_after_commit(preparation):
    before=preparation.learning.room('course','alice',include_progress=False)
    source,result=submit_and_run(preparation)
    ref=result['result']['resource_refs'][0]
    after=preparation.learning.room('course','alice',include_progress=False)
    assert after['selectedId']==before['selectedId']
    assert any(r['id']==ref['material_id'] for t in after['chapters'] for r in t['resources'])
    assert preparation.learning.material('course','report',ref['material_id'],'alice')['content'].startswith('# 变量')
    with pytest.raises(HTTPException):
        preparation.learning.material('course','report',ref['material_id'],'bob')
    assert result['result']['course_ready'] is False
    assert result['quality_report']['passed'] is True
    assert len(preparation.service.resources('alice','course'))==1
    assert not preparation.service.run_once()

def test_shared_revision_preserves_original_identity_and_version(preparation):
    original=preparation.learning.material('course','report','doc','alice')
    _,result=submit_and_run(preparation,'请修改当前这份文档，增加变量例子并保存个人版本',operation='revise_resource')
    ref=result['result']['resource_refs'][0]
    assert ref['material_id']!='doc'
    assert preparation.learning.material('course','report','doc','alice')==original
    revised=preparation.learning.material('course','report',ref['material_id'],'alice')
    assert revised['source_ref']['material_id']=='doc' and revised['source_ref']['version']==1
    assert revised['visibility']=='private'

def test_canceled_worker_cannot_deliver_or_publish(preparation):
    source=turn(preparation)
    receipt=preparation.submit(source,args(),{},'cancel')
    claim=preparation.service.claim()
    preparation.service.control('alice',receipt['preparation_id'],'cancel')
    preparation.service.model_json=producer
    asyncio.run(preparation.service.execute(claim))
    assert preparation.get('alice',receipt['preparation_id'])['status']=='canceled'
    assert preparation.service.resources('alice','course')==[]
    retry=preparation.service.control('alice',receipt['preparation_id'],'retry')
    assert retry['attempt_no']==2
    assert preparation.service.run_once()
    assert preparation.get('alice',receipt['preparation_id'])['status']=='succeeded'

def test_version_conflict_keeps_draft_unattached(preparation):
    source=turn(preparation)
    receipt=preparation.submit(source,args(),{},'conflict')
    from app.course_preparation.production_models import PersonalManifestHead
    with preparation.service.write() as db:
        db.get(PersonalManifestHead,('alice','course')).version=2
    preparation.service.model_json=producer
    preparation.service.run_once()
    failed=preparation.get('alice',receipt['preparation_id'])
    assert failed['status']=='failed' and failed['result']['error_code']=='VERSION_CONFLICT'
    room=preparation.learning.room('course','alice',include_progress=False)
    assert all(not r['id'].startswith('prep_') for t in room['chapters'] for r in t['resources'])

def test_quality_gate_failure_never_delivers(preparation):
    receipt=preparation.submit(turn(preparation),args(),{},'quality')
    async def fail(owner,system,data,snapshot):
        if '检查者' in system:
            return {'passed':False,'issues':['目标不满足']}
        return await producer(owner,system,data,snapshot)
    preparation.service.model_json=fail
    preparation.service.run_once()
    failed=preparation.get('alice',receipt['preparation_id'])
    assert failed['status']=='failed' and failed['result']['error_code']=='QUALITY_GATE_FAILED'
    assert preparation.service.resources('alice','course')==[]

def test_notification_replay_owner_and_stale_attempt(preparation):
    _,result=submit_and_run(preparation)
    assert preparation.notifications.drain()==1
    assert preparation.notifications.drain()==0
    notices=preparation.notifications.list('alice','course')['items']
    assert len(notices)==1 and notices[0]['type']=='succeeded'
    assert preparation.notifications.list('bob','course')['items']==[]
    with pytest.raises(HTTPException):
        preparation.notifications.mark_read('bob',notices[0]['notification_id'])
    preparation.notifications.mark_read('alice',notices[0]['notification_id'])
    assert preparation.notifications.list('alice','course')['items'][0]['read']

def test_lease_reclaim_fences_old_worker(preparation):
    service=preparation.service
    now=[100.]
    service.clock=lambda:now[0]
    receipt=preparation.submit(turn(preparation),args(),{},'lease')
    old=service.claim()
    now[0]=116.
    new=service.claim()
    assert old['token']!=new['token']
    from app.course_preparation.production_service import ProductionFence
    with pytest.raises(ProductionFence):
        service.save(old,old['payload'])
    service.model_json=producer
    asyncio.run(service.execute(new))
    assert preparation.get('alice',receipt['preparation_id'])['status']=='succeeded'

def test_stale_canceled_notice_ignored_after_retry(preparation):
    receipt=preparation.submit(turn(preparation),args(),{},'stale')
    preparation.service.control('alice',receipt['preparation_id'],'cancel')
    from app.database import CoursePreparationEventRecord as Event
    from sqlalchemy import select
    with Session(preparation.service.engine) as db:
        old=db.scalar(select(Event.event_id).where(Event.event_type=='canceled'))
    preparation.service.control('alice',receipt['preparation_id'],'retry')
    assert not preparation.notifications.consume(old)
    assert preparation.notifications.list('alice','course')['items']==[]

def test_saved_task_exposed_when_answer_fails(preparation):
    from app.self_learning.agent_runtime import LearningAgentRuntime
    from app.self_learning.turn_contracts import AgentFailure
    import json
    source=turn(preparation)
    class Model:
        calls=0
        async def complete(self,messages,tools,deadline):
            self.calls+=1
            if self.calls>1:
                raise AgentFailure('MODEL_UNAVAILABLE')
            return {'content':'','calls':[{'id':'prep','type':'function','function':{'name':'submit_preparation_request','arguments':json.dumps(args())}}]}
    model=Model()
    LearningAgentRuntime(preparation.learning,preparation.learning.turn_repository,lambda _:model).run_once()
    result=preparation.learning.turns.get('alice',source['turn_id'])
    assert result['status']=='failed'
    assert any(e['kind']=='preparation' for e in result['committed_effects']),result
    assert len(preparation.list('alice','course'))==1

def test_hallucinated_submit_is_repaired_with_real_tool_receipt(preparation):
    import json
    from app.self_learning.agent_runtime import LearningAgentRuntime
    source=turn(preparation)
    class Model:
        round=0
        async def complete(self,messages,tools,deadline):
            self.round+=1
            if self.round==1:
                return {'content':'已提交生成请求，资料正在准备。','calls':[]}
            if self.round==2:
                assert any(t['function']['name']=='submit_preparation_request' for t in tools)
                return {'content':'','calls':[{'id':'repair-submit','type':'function','function':{'name':'submit_preparation_request','arguments':json.dumps(args())}}]}
            return {'content':json.dumps({'answer_markdown':'任务已接收，准备完成后可以自行打开。','citation_ids':[]}), 'calls':[]}
    model=Model()
    LearningAgentRuntime(preparation.learning,preparation.learning.turn_repository,lambda _:model).run_once()
    result=preparation.learning.turns.get('alice',source['turn_id'])
    assert result['status']=='succeeded',result
    assert len(result['result']['preparation_receipts'])==1
    assert len(preparation.list('alice','course'))==1

def test_repeated_false_submission_never_publishes(preparation):
    import json
    from app.self_learning.agent_runtime import LearningAgentRuntime
    source=turn(preparation)
    class Model:
        async def complete(self,messages,tools,deadline):
            return {'content':json.dumps({'answer_markdown':'已提交生成请求。','citation_ids':[]}), 'calls':[]}
    LearningAgentRuntime(preparation.learning,preparation.learning.turn_repository,lambda _:Model()).run_once()
    result=preparation.learning.turns.get('alice',source['turn_id'])
    assert result['status']=='failed' and result['error_code']=='ANSWER_SCHEMA_INVALID'
    assert not preparation.list('alice','course')
    messages=preparation.learning.session_repository.messages('alice',source['session_id'])['items']
    assert not any(m['text']=='已提交生成请求。' for m in messages)

def test_status_query_uses_past_task_handle_and_current_read_receipt(preparation):
    import json
    from app.self_learning.agent_runtime import LearningAgentRuntime
    from tests.self_learning.test_agent_runtime import Model
    # The first answer carries a real task receipt in its durable result.
    source=turn(preparation)
    receipt=preparation.submit(source,args(),{},'status-query')
    preparation.service.model_json=producer
    preparation.service.run_once()
    claim=preparation.learning.turn_repository.claim()
    saved=preparation.get('alice',receipt['preparation_id'])
    preparation.learning.turn_repository.finish(claim,result={'answer_markdown':'准备任务已接收。','citation_ids':[], 'preparation_receipts':[saved]})
    second=turn(preparation,'刚才的任务完成了吗？')
    from app.self_learning.context_builder import ContextBuilder
    packet=ContextBuilder(preparation.learning).build(second)
    assert receipt['preparation_id'] in json.dumps(packet,ensure_ascii=False)
    call={'id':'status','type':'function','function':{'name':'get_preparation_status','arguments':json.dumps({'preparation_id':receipt['preparation_id']})}}
    model=Model([{'content':'','calls':[call]},{'content':json.dumps({'answer_markdown':'任务已完成，可从通知打开资料。','citation_ids':[]}), 'calls':[]}])
    LearningAgentRuntime(preparation.learning,preparation.learning.turn_repository,lambda _:model).run_once()
    answer=preparation.learning.turns.get('alice',second['turn_id'])
    assert answer['status']=='succeeded',answer
    assert answer['result']['preparation_receipts'][0]['status']=='succeeded'
