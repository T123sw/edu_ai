"""The public selection limit must remain usable with all learning tools mounted."""
import json

import pytest

from app.self_learning.agent_runtime import LearningAgentRuntime
from tests.self_learning.test_agent_runtime import Model, accept, request
from tests.self_learning.test_preparation_adapter import preparation, memory, agent_service, live_service, repository


@pytest.mark.parametrize('selection_length', [170, 10000])
def test_report_quote_with_all_tools_preserves_selection_and_question(preparation, selection_length, monkeypatch):
    svc = preparation.learning
    svc.checks = object()  # Mount the check schema; this test never requests a check.
    selected = ('变量与对象引用。' * 1250)[:selection_length]
    svc.manager.save_generated_material('course', 'report', 'doc', {'title': '报告', 'content': selected},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    question = '请解释这段内容。' if selection_length == 170 else '请解释' + '含义' * 998
    original_room = svc.room
    def room(*args, **kwargs):
        result = original_room(*args, **kwargs)
        result['chapters'][0]['objectives'] = [
            {'objective_id': f'obj-{i}', 'text': '说明变量与对象的关系。' * 100} for i in range(8)]
        return result
    monkeypatch.setattr(svc, 'room', room)
    req = request(question=question, selected=selected)
    req.reading_context.resource_ref.version = svc.material('course', 'report', 'doc', 'alice')['version']
    accepted = accept(svc, req)
    model = Model()
    LearningAgentRuntime(svc, svc.turn_repository, lambda _: model).run_once()
    result = svc.turns.get('alice', accepted['turn_id'])
    assert result['status'] == 'succeeded', json.dumps(result,ensure_ascii=False)
    messages = json.loads(model.messages[0])
    data = json.loads(messages[1]['content'].split('\n', 1)[1])
    assert data['selected_text'] == selected
    assert messages[-1]['content'] == question
    assert result['result']['teaching_skill']['mode'] == 'document'
    topic = data['learning_context']['current_topic']
    assert topic['objectives'][0]['objective_id'] == 'obj-0'
    assert len(topic['objectives']) == 3 and topic['objectives_truncated'] is True
    if selection_length == 10000:
        assert data['reading']['truncated'] is True


def test_resumed_long_selection_rebuild_after_preference_write(preparation, monkeypatch):
    from app.self_learning.context_builder import ContextBuilder
    from app.self_learning.tools import LearningTools
    from app.self_learning.turn_repository import TurnRepository
    svc=preparation.learning
    svc.checks=object()
    selected='变量与对象引用。'*1250
    svc.manager.save_generated_material('course','report','doc',{'title':'报告','content':selected},
        owner_user_id='alice',visibility='course',scope_type='knowledge_point',scope_id='a')
    original_room=svc.room
    def room(*args,**kwargs):
        result=original_room(*args,**kwargs)
        result['chapters'][0]['objectives']=[{'objective_id':f'obj-{i}','text':'说明变量与对象的关系。'*100} for i in range(8)]
        return result
    monkeypatch.setattr(svc,'room',room)
    req=request(question='以后都先举例。'+ '含义'*990,selected=selected)
    req.reading_context.resource_ref.version=svc.material('course','report','doc','alice')['version']
    accepted=accept(svc,req)
    clock=[100.]
    repo=TurnRepository(svc.turn_repository.engine,clock=lambda:clock[0])
    claim=repo.claim()
    schemas_size=len(json.dumps(LearningTools(svc,claim,{}).schemas(),ensure_ascii=False).encode())
    packet=ContextBuilder(svc).build(claim,budget=64000-schemas_size-1024)
    call={'id':'pref','type':'function','function':{'name':'update_learning_preference',
        'arguments':json.dumps({'operation':'set','field':'example_order','scope':'global','value':'先举例','source_quote':'以后都先举例'})}}
    packet['messages'].append({'role':'assistant','content':None,'tool_calls':[call]})
    repo.save(claim,{'packet':packet,'rounds':1,'tools':0,'pending':[call],'repair_used':False})
    clock[0]=116.
    model=Model()
    LearningAgentRuntime(svc,repo,lambda _:model).run_once()
    result=repo.get('alice',accepted['turn_id'])
    assert result['status']=='succeeded',json.dumps(result,ensure_ascii=False)
    assert svc.memory.read('alice','course')['items'][0]['value']=='先举例'
    assert selected in model.messages[0]
