import json
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.self_learning.resource_reader import excerpt
from app.self_learning.context_builder import ContextBuilder
from app.self_learning.turn_contracts import AnswerRequest
from tests.self_learning.test_agent_runtime import agent_service
from tests.self_learning.test_session_api import live_service, repository


def quiz():
    return {'material_type': 'quiz', 'title': '练习', 'questions': [
        {'id': 'same', 'stem': '第一题加法', 'answer': '5'},
        {'id': 'same', 'stem': '第二题乘法', 'answer': '6'}]}


def test_question_index_disambiguates_even_duplicate_ids():
    piece = excerpt(quiz(), locator={'kind': 'quiz', 'question_index': 1})
    assert '第二题乘法' in piece['excerpt'] and '第一题加法' not in piece['excerpt']
    assert piece['location_quality'] == 'exact'
    with pytest.raises(HTTPException):
        excerpt(quiz(), locator={'kind': 'quiz', 'question_index': 2})
    with pytest.raises(HTTPException):
        excerpt({'material_type': 'report', 'questions': quiz()['questions']}, locator={'kind': 'quiz', 'question_index': 0})


def test_search_retrieves_late_passage_and_returns_replayable_anchor():
    material = {'material_type': 'report', 'content': '# 😀 标题\n\n' + ('无关开头。\n\n' * 2000) + '递归终止条件是 n 等于 0。\n\n其他段落'}
    found = excerpt(material, query='递归终止条件是什么？', max_chars=1500)
    assert found['search_matched'] and found['location_quality'] == 'exact'
    assert '递归终止条件是 n 等于 0' in found['excerpt']
    replay = excerpt(material, locator=found['resolved_locator'], max_chars=1500)
    assert replay['excerpt'] == found['excerpt']
    with pytest.raises(HTTPException):
        excerpt({**material, 'content': '新版本'}, locator=found['resolved_locator'])
    missing = excerpt(material, query='quicksort partition')
    assert missing['search_matched'] is False and not missing['excerpt'] and not missing['resolved_locator']


def test_explicit_anchor_takes_priority_over_search():
    material = {'material_type': 'report', 'content': '苹果是水果。\n\n橘子也是水果。'}
    apple = excerpt(material, query='苹果')['resolved_locator']
    result = excerpt(material, locator=apple, query='橘子')
    assert result['resolved_locator'] == apple
    assert result['excerpt'].startswith('当前引用段落（Markdown 原文）：\n苹果')


def test_question_snapshot_uses_original_version_and_rejects_foreign_index(agent_service):
    svc = agent_service
    svc.manager.save_generated_material('course', 'quiz', 'quiz-nav', quiz(), owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    req = AnswerRequest(request_id=uuid4(), question='解释这题', reading_context={
        'resource_ref': {'course_id': 'course', 'material_type': 'quiz', 'material_id': 'quiz-nav', 'version': 1},
        'locator': {'kind': 'quiz', 'question_index': 1}})
    accepted = svc.turns.accept('alice', 'course', 'a', req)
    old = svc.material('course', 'quiz', 'quiz-nav', 'alice')
    svc.manager.save_generated_material('course', 'quiz', 'quiz-nav', {**quiz(), 'questions': [quiz()['questions'][0]], 'revision_history': {'1': old}}, owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    packet = ContextBuilder(svc).build(svc.turn_repository.get('alice', accepted['turn_id']))
    assert '第二题乘法' in packet['messages'][-3]['content']
    assert packet['citations']['ctx_01']['resource_ref']['version'] == 1
    assert packet['citations']['ctx_01']['locator'] == {'kind': 'quiz', 'question_index': 1}
    req.reading_context.resource_ref.version = 2
    with pytest.raises(HTTPException):
        svc.turns.accept('alice', 'course', 'a', req.model_copy(update={'request_id': uuid4()}))


def test_context_searches_current_report_before_model_call(agent_service):
    svc = agent_service
    svc.manager.save_generated_material('course', 'report', 'doc', {'title': '长文', 'content': ('前言。\n\n' * 2000) + '递归终止条件是 n 为零。'}, owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    current = svc.material('course', 'report', 'doc', 'alice')
    req = AnswerRequest(request_id=uuid4(), question='递归终止条件是什么', reading_context={
        'resource_ref': {'course_id': 'course', 'material_type': 'report', 'material_id': 'doc', 'version': current['version']}})
    turn = svc.turns.accept('alice', 'course', 'a', req)
    packet = ContextBuilder(svc).build(svc.turn_repository.get('alice', turn['turn_id']))
    data = json.loads(packet['messages'][1]['content'].split('\n', 1)[1])
    assert data['reading']['search_matched'] and 'n 为零' in data['reading']['excerpt']
