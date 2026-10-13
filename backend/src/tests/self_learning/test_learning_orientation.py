import json

import pytest
from fastapi import HTTPException

from app.self_learning.context_builder import ContextBuilder
from tests.self_learning.test_agent_runtime import agent_service, accept, request
from tests.self_learning.test_session_api import live_service, repository


def test_generic_report_keeps_official_course_and_topic_without_intro_history(agent_service):
    svc = agent_service
    svc.manager.save_generated_material('course', 'report', 'doc',
        {'title': '学习指南', 'content': '# 核心概念\n\n## 定义的本质属性\n\n该概念是多维复合系统。'},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    req = request(question='围绕哪个知识点', selected='该概念是多维复合系统。')
    req.reading_context.resource_ref.version = svc.material('course', 'report', 'doc', 'alice')['version']
    accepted = accept(svc, req)
    packet = ContextBuilder(svc).build(svc.turn_repository.get('alice', accepted['turn_id']))
    data = json.loads(packet['messages'][1]['content'].split('\n', 1)[1])
    context = data['learning_context']
    assert context['course'] == {'id': 'course', 'title': 'Python'}
    assert context['current_topic']['title'] == '变量'
    assert context['current_resource']['title'] == '学习指南'
    assert context['current_resource']['resource_ref'] == req.reading_context.resource_ref.model_dump()
    assert data['selected_text'] == req.reading_context.selected_text
    assert not any('这一节围绕' in m['content'] for m in packet['messages'][1:])


def test_topic_identity_follows_request_not_last_opened_resource(agent_service):
    svc = agent_service
    accepted = accept(svc)
    claim = svc.turn_repository.get('alice', accepted['turn_id'])
    svc.patch('course', 'alice', {'selectedId': 'pending:b'})
    packet = ContextBuilder(svc).build(claim)
    context = json.loads(packet['messages'][1]['content'].split('\n', 1)[1])['learning_context']
    assert context['current_topic']['id'] == 'a'
    assert context['current_topic']['title'] == '变量'
    with pytest.raises(HTTPException):
        ContextBuilder(svc).build({**claim, 'topic_id': 'b'})


def test_each_entry_refreshes_course_directory_without_duplicate_greeting(live_service):
    svc = live_service
    first = svc.sessions.enter('alice', 'course', 'a')
    second = svc.sessions.enter('alice', 'course', 'b')
    assert first['learning_context']['current_topic']['title'] == '变量'
    assert second['learning_context']['current_topic']['title'] == '条件'
    svc.manager.save_course_info('course', {'id': 'course', 'title': 'Python 基础', 'created_by': 'alice'})
    again = svc.sessions.enter('alice', 'course', 'a')
    assert again['session_id'] == first['session_id']
    assert again['message_count'] == first['message_count']
    assert again['learning_context']['course']['title'] == 'Python 基础'
