import pytest
from fastapi import HTTPException
from app.database.models import ConversationMessage
from app.self_learning.db_models import LearningTopicSession
from app.self_learning.observations import ObservationService
from tests.self_learning.test_session_api import live_service,repository


def test_user_can_resolve_sourced_observation_without_rewriting_history(live_service):
    svc=live_service;session=svc.sessions.enter('alice','course','a');sid=session['session_id']
    observation={'kind':'confusion','text':'工具职责仍待澄清','source_quote':'我不清楚谁执行','source_refs':['turn:user'],'evaluator':'model','status':'hypothesis','objective_ids':[]}
    with svc.session_repository._write(sid) as db:
        row=db.get(LearningTopicSession,sid)
        svc.session_repository._append(db,row,'observed-answer','assistant','可以解释职责。','assistant_content',{'answer_result':{'observation':observation}})
    service=ObservationService(svc)
    assert service.list('alice','course','a')[0]['status']=='hypothesis'
    with pytest.raises(HTTPException):service.update('bob','course','a','observed-answer','resolved',0)
    result=service.update('alice','course','a','observed-answer','resolved',0)
    assert result['status']=='resolved'
    assert service.update('alice','course','a','observed-answer','resolved',0)==result
    assert service.list('alice','course','a')[0]['status']=='resolved'
    with pytest.raises(HTTPException):service.update('alice','course','a','observed-answer','retracted',0)
    with svc.session_repository._write(sid) as db:
        assert db.get(ConversationMessage,'observed-answer').raw_payload['answer_result']['observation']['status']=='hypothesis'
        assert db.get(LearningTopicSession,sid).import_metadata['summary_job']['pending']
    messages=svc.sessions.messages('alice','course','a')['items']
    assert sum('我确认此前' in m['text'] for m in messages)==1
