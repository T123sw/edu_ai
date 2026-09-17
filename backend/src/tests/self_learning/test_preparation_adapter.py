from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base,User
from app.self_learning.preparation_adapter import PreparationAdapter,requests_saved_work


def test_explicit_save_handoff_binds_original_turn_and_request_replay():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine,tables=[User.__table__])
    with Session(engine) as db,db.begin(): db.add(User(user_id='immutable-alice',username='alice',password_hash='unused',role='student'))
    manifest={'version':3,'route_version':1}
    prepared=SimpleNamespace(engine=engine,manifest=lambda *_:manifest)
    learning=SimpleNamespace(prepared_courses=prepared,require=lambda *_:None)
    calls=[]
    service=SimpleNamespace(submit=lambda owner,request:calls.append((owner,request)) or {'preparation_id':'same','status':'accepted'})
    adapter=PreparationAdapter(learning,service)
    turn={'owner':'alice','course_id':'course','topic_id':'node','session_id':'session','turn_id':'turn',
          'request':{'question':'请补充资料并保存一个工具失败案例'}}
    assert adapter.submit(turn,'supplement_node','工具失败案例')==adapter.submit(turn,'supplement_node','工具失败案例')
    assert calls[0][0]=='immutable-alice' and calls[0][1].request_id==calls[1][1].request_id
    assert calls[0][1].origin.message_id=='turn:user'
    assert calls[0][1].target.node_id=='node' and calls[0][1].target.base_manifest_version==3
    turn['request']['question']='只解释这个概念，不要生成'
    with pytest.raises(Exception): adapter.submit(turn,'supplement_node','工具失败案例')
    assert len(calls)==2
