from uuid import uuid4
import pytest
from app.self_learning.migration import LearningMigration
from tests.self_learning.test_preparation_adapter import preparation, memory, agent_service, live_service, repository

@pytest.fixture(autouse=True)
def migration_tables(preparation):
    preparation.learning.progress_repository=preparation.learning.progress_service.repository
    from app.database import Base
    from app.self_learning.migration_models import TABLES
    Base.metadata.create_all(preparation.service.engine,tables=[Base.metadata.tables[n] for n in TABLES])

def source(count=3):
    return {'owner':'alice','course_id':'course','sessions':[{'topic_id':'a','session_id':'old-id','turns':[
        {'turn_id':f'old-{i}','question':f'question {i}','answer_text':f'answer {i}','resource_id':'doc'} for i in range(count)]}],
        'overlay':{'progress':{'doc':{'completed':True},'gone':{'completed':True},'pending:a':{'note':'保留占位笔记'}},'understanding':{'a':'review'}}}

@pytest.mark.parametrize('count',[3,150])
def test_scan_read_only_repeat_import_and_reconcile(preparation,count):
    migration=LearningMigration(preparation.learning)
    raw=source(count)
    report=migration.scan(raw)
    assert preparation.learning.session_repository.find('alice','course','a') is None
    assert report['counts']['turns']==count
    assert report['unresolved']
    first=migration.import_records(report)
    second=migration.import_records(report)
    assert first['created']>0 and second['created']==0
    assert migration.reconcile(report)['unexplained_differences']==[]
    preparation.learning.sessions.enter('alice','course','b')
    assert migration.reconcile(report)['unexplained_differences']==[]
    assert migration.import_records(report)['created']==0
    facts=preparation.learning.progress_repository.read('alice','course')
    assert not any(r['completed'] for r in facts['resources'])
    assert migration.archived('alice','course')['overlay']['progress']['pending:a']['note']=='保留占位笔记'

def test_modified_source_is_conflict_not_overwrite(preparation):
    migration=LearningMigration(preparation.learning)
    migration.import_records(migration.scan(source()))
    changed=source();changed['sessions'][0]['turns'][0]['answer_text']='changed'
    with pytest.raises(ValueError):
        migration.import_records(migration.scan(changed))

def test_scoped_cutover_and_model_rollback_keep_new_facts(preparation,monkeypatch):
    svc=preparation.learning
    migration=LearningMigration(svc)
    raw=source();raw['overlay']['progress']['doc']['version']=1
    report=migration.scan(raw)
    migration.import_records(report)
    migration.activate(report,5)
    monkeypatch.setenv('LEARNING_SCOPED_ROLLOUT','true')
    assert svc.room('course','alice')['progressPersistence']
    assert not svc.room('course','bob')['progressPersistence']
    assert svc.room('course','alice')['progress']['doc']['completed']
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        svc.patch('course','alice',{'progress':{'doc':{'completed':False}}})
    # Simulate model features disabled on app rollback; facts still read new DB.
    svc.turns=svc.checks=svc.memory=svc.preparations=None
    svc.store.put('alice','course',{'progress':{'doc':{'completed':False}}})
    assert svc.room('course','alice')['progress']['doc']['completed']
    assert not svc.room('course','alice')['agentRuntime']
    with pytest.raises(HTTPException):
        svc.answer('course','alice','a','question',str(uuid4()),'doc')
    with pytest.raises(ValueError):
        migration.activate(report,1)

def test_active_legacy_answer_blocks_cutover(preparation,monkeypatch):
    svc=preparation.learning
    migration=LearningMigration(svc)
    report=migration.scan(migration.collect('alice','course'))
    migration.import_records(report)
    session=svc.session('course','a','alice')
    svc.qa.begin_turn(session=session,client_turn_id='in-flight',question='旧路径回答中',checkpoint={'resource_id':'doc'})
    with pytest.raises(ValueError,match='active turn'):
        migration.activate(report,5)
    from app.self_learning.migration_models import LearningRolloutScope
    from sqlalchemy.orm import Session
    with Session(migration.engine) as db:
        assert db.get(LearningRolloutScope,('alice','course')) is None


def test_stale_live_store_scan_refuses_activation(preparation):
    svc=preparation.learning
    migration=LearningMigration(svc)
    report=migration.scan(migration.collect('alice','course'))
    migration.import_records(report)
    svc.store.put('alice','course',{'progress':{'doc':{'note':'扫描后的新笔记'}}})
    with pytest.raises(ValueError,match='changed since scan'):
        migration.activate(report,5)

def test_worker_mounts_only_tools_in_activated_scope(preparation,monkeypatch):
    from app.self_learning.agent_runtime import LearningAgentRuntime
    from tests.self_learning.test_agent_runtime import accept,Model
    svc=preparation.learning
    migration=LearningMigration(svc)
    report=migration.scan(source())
    migration.import_records(report)
    migration.activate(report,3)
    monkeypatch.setenv('LEARNING_SCOPED_ROLLOUT','true')
    class ScopedModel(Model):
        async def complete(self,messages,tools,deadline):
            assert {t['function']['name'] for t in tools}=={'read_resource_excerpt','search_course_resources','read_course_learning_summary','search_learning_history'}
            return await super().complete(messages,tools,deadline)
    answer=accept(svc)
    LearningAgentRuntime(svc,svc.turn_repository,lambda _:ScopedModel()).run_once()
    assert svc.turns.get('alice',answer['turn_id'])['status']=='succeeded'
