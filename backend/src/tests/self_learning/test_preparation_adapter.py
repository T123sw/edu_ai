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
    adapter.submit(turn,'supplement_node','工具失败案例',changes=['保留原资料'])
    assert not calls[-1][1].requested_changes and calls[-1][1].goal==turn['request']['question']
    with pytest.raises(Exception): adapter.submit(turn,'adjust_course','更换全部路径',changes=['重新排课'])
    turn['request']['question']='只解释这个概念，不要生成'
    with pytest.raises(Exception): adapter.submit(turn,'supplement_node','工具失败案例')
    assert len(calls)==3


@pytest.mark.parametrize('question,expected',[
 ('请先保存检查题，让我在作答卡中回答，不要创建或保存课程资料。',False),
 ('无需重新生成或保存任何资料，只解释。',False),
 ('请保存作答，不要生成新课程。',False),
 ('请修改这份报告并保存，不要修改其他资料。',True),
 ('请保存一套面试练习。',True),
])
def test_negated_course_writes_and_check_persistence_are_not_resource_requests(question,expected):
    assert requests_saved_work(question) is expected
