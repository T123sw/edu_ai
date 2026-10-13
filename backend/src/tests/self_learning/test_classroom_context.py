import copy
import json
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.self_learning.classroom_context import classroom_context, narration_sentences
from app.self_learning.context_builder import ContextBuilder
from app.self_learning.resource_reader import excerpt
from app.self_learning.turn_contracts import AnswerRequest, AgentFailure
from app.self_learning.agent_runtime import LearningAgentRuntime
from tests.self_learning.test_agent_runtime import agent_service, Model
from tests.self_learning.test_session_api import live_service, repository


def material():
    return {'title': '变量课件', 'learning_course_resource': True, 'scenes': [
        {'id': 'one', 'type': 'slide', 'title': '赋值', 'content': {'type': 'slide', 'canvas': {
            'elements': [
                {'id': 'text', 'type': 'text', 'content': '<p style="color:red">变量 &amp; 值</p><p>完整末句</p>'},
                {'id': 'formula', 'type': 'latex', 'latex': 'x=1', 'path': 'HUGE_SVG' * 10000},
                {'id': 'code', 'type': 'code', 'language': 'python', 'lines': [{'id': 'L1', 'content': 'x = 1'}]},
                {'id': 'table', 'type': 'table', 'data': [[{'text': '<b>数值</b>', 'style': {'color': 'red'}}]]},
                {'id': 'chart', 'type': 'chart', 'chartType': 'bar', 'data': {'labels': ['一'], 'legends': ['值'], 'series': [[1]]}},
                {'id': 'image', 'type': 'image', 'name': '变量示意', 'src': 'data:image/png;base64,SECRET_IMAGE'},
            ], 'script': '教师备注'}},
         'actions': [{'id': 'focus', 'type': 'spotlight', 'elementId': 'formula'},
                     {'id': 'speech', 'type': 'speech', 'text': '再试一次。再试一次。最后总结！', 'audioUrl': 'SECRET_AUDIO'}]},
        {'id': 'two', 'type': 'slide', 'title': '条件', 'content': {'type': 'slide', 'canvas': {
            'elements': [{'id': 'next', 'type': 'text', 'content': '下一页完整内容'}]}}, 'actions': []}]}


def playback():
    return {'status': 'paused', 'lecture': {'scene_id': 'one', 'action_id': 'speech',
        'speech_action_id': 'speech', 'sentence_index': 1, 'sentence_alignment': 'estimated',
        'speech_completed': False, 'highlighted_element_ids': ['formula']}}


def test_full_semantics_without_rendering_noise_or_invented_vision():
    value = classroom_context(material(), {'kind': 'classroom', 'scene_id': 'one'}, playback())
    page = value['viewed_page']
    assert page['elements'][0]['text'] == '变量 & 值\n完整末句'
    assert page['elements'][1]['latex'] == 'x=1'
    assert page['elements'][2]['lines'][0]['content'] == 'x = 1'
    assert page['elements'][3]['rows'][0][0]['text'] == '数值'
    assert page['elements'][4]['data']['series'] == [[1]]
    assert page['elements'][5]['visual_content_available'] is False
    assert page['speaker_notes'] == '教师备注'
    assert page['narration'][0]['text'].endswith('最后总结！')
    assert value['lecture_position']['current_sentence'] == '再试一次。'
    assert value['lecture_position']['sentence_index'] == 1
    assert value['lecture_position']['highlighted_elements'][0]['latex'] == 'x=1'
    rendered = json.dumps(value, ensure_ascii=False)
    assert all(noise not in rendered for noise in ('HUGE_SVG', 'SECRET_IMAGE', 'SECRET_AUDIO', 'color:red'))


def test_viewed_page_is_independent_and_unknown_playback_is_not_invented():
    value = classroom_context(material(), {'kind': 'classroom', 'scene_id': 'two'}, playback())
    assert value['viewed_page']['scene_id'] == 'two'
    assert value['lecture_position']['same_as_viewed_page'] is False
    assert value['lecture_position']['scene_id'] == 'one'
    assert [d['scene_id'] for d in value['directory']] == ['one', 'two']
    missing = classroom_context(material(), None)
    assert missing['viewed_page'] is None and missing['lecture_position'] is None
    assert missing['playback_status'] == 'unknown'
    assert narration_sentences('重复！重复！\n最后。') == ['重复！', '重复！', '最后。']


@pytest.mark.parametrize('change', [
    {'scene_id': 'foreign'}, {'action_id': 'foreign'}, {'speech_action_id': 'focus'},
    {'sentence_index': 99}, {'highlighted_element_ids': ['foreign']},
])
def test_foreign_or_invalid_position_is_rejected(change):
    pointer = playback()
    pointer['lecture'].update(change)
    with pytest.raises(HTTPException):
        classroom_context(material(), {'kind': 'classroom', 'scene_id': 'one'}, pointer)


def test_read_other_page_uses_semantics_and_never_falls_back_to_first_page():
    piece = excerpt(material(), locator={'kind': 'classroom', 'scene_id': 'two'})
    assert '下一页完整内容' in piece['excerpt'] and piece['location_quality'] == 'exact'
    with pytest.raises(HTTPException):
        excerpt(material(), locator={'kind': 'classroom', 'scene_id': 'absent'})


def test_versioned_snapshot_reaches_model_and_preserves_full_current_page(agent_service):
    svc = agent_service
    original = material()
    # A normal text-heavy slide beyond the old 6,000-character raw JSON cutoff.
    original['scenes'][0]['content']['canvas']['elements'][0]['content'] = '课程正文' * 1600 + '保留末尾'
    svc.manager.save_generated_material('course', 'classroom', 'slides', original,
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    req = AnswerRequest(request_id=uuid4(), question='刚才那句话什么意思？', reading_context={
        'resource_ref': {'course_id': 'course', 'material_type': 'classroom', 'material_id': 'slides', 'version': 1},
        'locator': {'kind': 'classroom', 'scene_id': 'one'}, 'classroom': playback()})
    accepted = svc.turns.accept('alice', 'course', 'a', req)
    claim = svc.turn_repository.get('alice', accepted['turn_id'])
    packet = ContextBuilder(svc).build(claim, budget=40000)
    data = json.loads(packet['messages'][1]['content'].split('\n', 1)[1])
    assert data['reading']['truncated'] is False
    assert '保留末尾' in data['reading']['excerpt']
    with pytest.raises(AgentFailure, match='CONTEXT_BUDGET_EXCEEDED'):
        ContextBuilder(svc).build(claim, budget=2000)
    changed = copy.deepcopy(original)
    changed['scenes'][0]['title'] = 'NEW_VERSION_MARKER'
    changed['revision_history'] = {'1': svc.material('course', 'classroom', 'slides', 'alice')}
    svc.manager.save_generated_material('course', 'classroom', 'slides', changed,
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    model = Model()
    LearningAgentRuntime(svc, svc.turn_repository, lambda _: model).run_once()
    result = svc.turns.get('alice', accepted['turn_id'])
    assert result['status'] == 'succeeded', result
    assert '保留末尾' in model.messages[0]
    assert 'NEW_VERSION_MARKER' not in model.messages[0]
    assert result['result']['citations'][0]['resource_ref']['version'] == 1
