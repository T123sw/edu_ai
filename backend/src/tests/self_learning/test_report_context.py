import json
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.self_learning.report_document import normalize_report, report_markdown, report_fingerprint
from app.self_learning.resource_reader import excerpt
from app.self_learning.context_builder import ContextBuilder
from app.self_learning.turn_contracts import AnswerRequest
from tests.self_learning.test_agent_runtime import agent_service
from tests.self_learning.test_session_api import live_service, repository


def anchor(material, target):
    source = normalize_report(report_markdown(material))
    start = source.rindex(target)
    return {'kind': 'document', 'block_id': f'report-v1:{start}:{start + len(target)}:{report_fingerprint(source)}'}


def test_repeated_formatted_paragraph_reads_the_chosen_occurrence():
    material = {'material_type': 'report', 'content': '# 开头 😀\n\n重复 **段落**。\n\n' + ('前文。' * 500) + '\n\n## 第二节\n\n重复 **段落**。\n\n后文标记'}
    locator = anchor(material, '重复 **段落**。')
    result = excerpt(material, selected_text='重复 段落。', locator=locator)
    assert result['anchor_verified'] is True
    assert result['resolved_locator'] == locator
    assert '第二节' in result['excerpt'] and '后文标记' in result['excerpt']
    assert '# 开头' not in result['excerpt']
    with pytest.raises(HTTPException):
        excerpt({**material, 'content': 'changed'}, locator=locator)
    with pytest.raises(HTTPException):
        excerpt(material, locator={**locator, 'block_id': f'report-v1:0:999999:{report_fingerprint(normalize_report(material["content"]))}'})


def test_report_anchor_reaches_model_context_with_correct_scope(agent_service):
    svc = agent_service
    material = {'title': '报告段落', 'material_type': 'report', 'content': '# 标题\n\n前文\n\n**变量**引用对象。\n\n后文'}
    svc.manager.save_generated_material('course', 'report', 'doc', material, owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    current = svc.material('course', 'report', 'doc', 'alice')
    req = AnswerRequest(request_id=uuid4(), question='这段是什么意思', reading_context={
        'resource_ref': {'course_id': 'course', 'material_type': 'report', 'material_id': 'doc', 'version': current['version']},
        'selected_text': '变量引用对象。', 'locator': anchor(current, '**变量**引用对象。')})
    accepted = svc.turns.accept('alice', 'course', 'a', req)
    packet = ContextBuilder(svc).build(svc.turn_repository.get('alice', accepted['turn_id']))
    data = json.loads(packet['messages'][1]['content'].split('\n', 1)[1])
    assert data['reading']['anchor_verified'] is True
    assert '**变量**引用对象。' in data['reading']['excerpt']
    assert data['selected_text'] == '变量引用对象。'
    assert packet['citations']['ctx_01']['locator']['block_id'] == req.reading_context.locator.block_id
