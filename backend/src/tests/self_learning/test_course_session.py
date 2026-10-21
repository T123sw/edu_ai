import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import ConversationMessage
from app.self_learning.context_builder import ContextBuilder
from app.self_learning.postgres_repository import SessionConflict
from tests.self_learning.test_agent_runtime import agent_service, accept, request, Model
from tests.self_learning.test_session_api import live_service
from tests.self_learning.test_session_repository import repository
from app.self_learning.agent_runtime import LearningAgentRuntime


def test_merge_keeps_message_ids_sources_and_owner_course_boundaries(repository):
    a = repository.ensure_session('alice', 'course', 'a', 'A', [
        {'turn_id': 'a1', 'question': '变量困惑', 'answer_text': '使用盒子类比'}])
    b = repository.ensure_session('alice', 'course', 'b', 'B', [
        {'turn_id': 'b1', 'question': '条件困惑', 'answer_text': '使用岔路类比'}])
    foreign = repository.ensure_session('bob', 'course', 'a', 'private', [
        {'turn_id': 'b2', 'question': '别人的秘密', 'answer_text': 'private'}])
    other = repository.ensure_session('alice', 'other', 'a', 'other')
    ids = {m['id'] for old in [a, b] for m in repository.messages('alice', old['session_id'])['items']
           if m['kind'] != 'introduction'}
    with ThreadPoolExecutor(max_workers=3) as pool:
        merged = list(pool.map(lambda _: repository.ensure_course_session('alice', 'course', '课程导学'), range(3)))
    sid = merged[0]['session_id']
    assert all(s['session_id'] == sid for s in merged)
    assert repository.find('alice', 'course', 'a')['session_id'] == sid
    assert repository.find('alice', 'course', 'b')['session_id'] == sid
    messages = repository.messages('alice', sid)['items']
    assert len(messages) == 5
    assert {m['id'] for m in messages if m['kind'] != 'introduction'} == ids
    assert {m['chapterId'] for m in messages if m['kind'] != 'introduction'} == {'a', 'b'}
    assert '别人的秘密' not in json.dumps(messages, ensure_ascii=False)
    assert repository.find('bob', 'course', 'a')['session_id'] == foreign['session_id']
    assert repository.find('alice', 'other', 'a')['session_id'] == other['session_id']
    assert len(repository.recent_turns('alice', sid)) == 2


def test_active_legacy_answer_is_preserved_until_finished(repository):
    old = repository.ensure_session('alice', 'course', 'a', '导学')
    claim = repository.begin_turn('alice', old['session_id'], 'q1', '未完成问题', 'res')
    with pytest.raises(SessionConflict):
        repository.ensure_course_session('alice', 'course', '课程导学')
    assert repository.find_course('alice', 'course') is None
    repository.finish_turn('alice', old['session_id'], 'q1', claim['token'], answer='已完成')
    shared = repository.ensure_course_session('alice', 'course', '课程导学')
    assert [m['text'] for m in repository.messages('alice', shared['session_id'])['items']] == [
        '课程导学', '未完成问题', '已完成']


def test_cross_topic_answer_uses_shared_history_but_keeps_original_reading(agent_service):
    svc = agent_service
    svc.manager.save_generated_material('course', 'report', 'b-doc',
        {'title': '条件', 'content': '条件按真假分支。', 'learning_course_resource': True},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='b')
    first = accept(svc, request(question='请记住我刚才的变量问题'))
    # Switching topics while A is running must keep the same conversation and active turn.
    shared = svc.sessions.enter('alice', 'course', 'b')
    assert shared['session_id'] == first['session_id']
    assert svc.turns.list_topic('alice', 'course', 'b')[0]['turn_id'] == first['turn_id']
    pending_request = request(question='同时从 B 节提问')
    pending_request.reading_context.resource_ref.material_id = 'b-doc'
    with pytest.raises(HTTPException) as conflict:
        svc.turns.accept('alice', 'course', 'b', pending_request)
    assert conflict.value.status_code == 409
    runtime = LearningAgentRuntime(svc, svc.turn_repository, lambda _: Model())
    runtime.run_once()
    second_request = request(question='结合前面的变量问题解释条件')
    second_request.reading_context.resource_ref.material_id = 'b-doc'
    second = svc.turns.accept('alice', 'course', 'b', second_request)
    assert second['session_id'] == first['session_id']
    assert second['topic_id'] == 'b'
    packet = ContextBuilder(svc).build(svc.turn_repository.get('alice', second['turn_id']))
    assert '请记住我刚才的变量问题' in json.dumps(packet['messages'], ensure_ascii=False)
    assert packet['citations']['ctx_01']['resource_ref']['material_id'] == 'b-doc'
    runtime.run_once()
    messages = svc.sessions.messages('alice', 'course', 'b')['items']
    assert [m['chapterId'] for m in messages if m['kind'] != 'introduction'] == ['a', 'a', 'b', 'b']
    with Session(svc.session_repository.engine) as db:
        originals = list(db.scalars(select(ConversationMessage).where(
            ConversationMessage.conversation_id == first['session_id'])))
    assert len(originals) == 5
