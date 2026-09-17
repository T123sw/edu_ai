"""Separate processes share only PostgreSQL; no Python mutex can serialize them."""
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from uuid import uuid4
import pytest
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from app.database import ConversationMessage,CoursePreparationEventRecord
from app.self_learning.turn_repository import TurnRepository,LostLease
from app.self_learning.progress_contracts import LearningEvent
from app.self_learning.progress_repository import ProgressRepository
from app.self_learning.turn_contracts import AnswerRequest
from tests.self_learning.test_preparation_adapter import preparation,memory,agent_service,live_service,repository,submit_and_run


def worker(url,schema,action,payload):
    engine=create_engine(url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        from app.self_learning.postgres_repository import SessionRepository,SessionConflict
        if action=='enter':
            return SessionRepository(engine).ensure_session('alice','course','a','导学')['session_id']
        if action=='event':
            return ProgressRepository(engine).record('alice','course','a',LearningEvent.model_validate(payload))['event_id']
        if action=='ask':
            sid=SessionRepository.identity('alice','course','a')
            try:
                return TurnRepository(engine).accept('alice',sid,AnswerRequest.model_validate(payload))['turn_id']
            except SessionConflict:
                return 'conflict'
        if action=='claim':
            return TurnRepository(engine,clock=lambda:payload).claim()
        if action=='notify':
            from types import SimpleNamespace
            from app.course_preparation.production_service import ProductionService
            from app.self_learning.notifications import NotificationService
            return NotificationService(SimpleNamespace(service=ProductionService(None,engine))).consume(payload)
    finally:
        engine.dispose()

@pytest.mark.integration
def test_two_processes_enter_events_turns_lease_and_outbox(preparation):
    engine=preparation.service.engine
    if engine.dialect.name!='postgresql':
        pytest.skip('requires isolated PostgreSQL')
    with engine.connect() as conn:
        schema=conn.scalar(text('select current_schema()'))
    url=engine.url.render_as_string(hide_password=False)
    with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
        def pair(action,payloads):
            jobs=[pool.submit(worker,url,schema,action,p) for p in payloads]
            return [j.result(timeout=45) for j in jobs]
        sessions=pair('enter',[{},{}]);assert sessions[0]==sessions[1]
        event={'event_id':str(uuid4()),'type':'resource_completion_set','resource_ref':{'course_id':'course','material_type':'report','material_id':'doc','version':1},
            'expected_revision':0,'occurred_at':'2026-09-17T00:00:00Z','payload':{'completed':True}}
        assert pair('event',[event,event])==[event['event_id']]*2
        assert preparation.learning.progress_service.repository.read('alice','course')['facts_revision']==1
        def request():return {'request_id':str(uuid4()),'question':'同节点竞争','reading_context':{'resource_ref':event['resource_ref']}}
        results=pair('ask',[request(),request()]);assert results.count('conflict')==1
        tid=next(r for r in results if r!='conflict')
        claims=pair('claim',[100.,100.]);assert sum(c is not None for c in claims)==1
        old=next(c for c in claims if c)
        new=pool.submit(worker,url,schema,'claim',116.).result(timeout=45)
        assert new['token']!=old['token']
        repo=TurnRepository(engine,clock=lambda:116.)
        with pytest.raises(LostLease):repo.finish(old,result={'answer_markdown':'迟到'})
        repo.finish(new,result={'answer_markdown':'有效回答','citation_ids':[]})
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(ConversationMessage).where(ConversationMessage.message_id==tid+':assistant'))==1
        _,result=submit_and_run(preparation)
        with Session(engine) as db:
            event_id=db.scalar(select(CoursePreparationEventRecord.event_id).where(CoursePreparationEventRecord.preparation_id==result['preparation_id'],CoursePreparationEventRecord.event_type=='succeeded'))
        assert sorted(pair('notify',[event_id,event_id]))==[False,True]
        assert len(preparation.notifications.list('alice','course')['items'])==1
