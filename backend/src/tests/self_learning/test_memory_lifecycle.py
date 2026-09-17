import pytest
from uuid import uuid4
from fastapi import HTTPException
from app.database import Base
from app.self_learning.memory_adapter import MemoryAdapter
from app.self_learning.enrichment_models import TABLES
from tests.self_learning.test_agent_runtime import agent_service, live_service, repository

@pytest.fixture
def memory(agent_service):
    engine = agent_service.session_repository.engine
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in ('agent_memory_items', 'user_profile_facts', 'agent_memory_audit_events', *TABLES)])
    result = MemoryAdapter(agent_service, engine)
    agent_service.memory = result
    return result

def put(memory, value='先举例', scope='course', revision=0, source='source-1'):
    return memory.update('alice', 'course', 'example_order', scope, value, revision,
        operation_id=str(uuid4()), source_id=source, source_quote='以后都先举例', explicit=True)

def test_scope_revision_and_current_request_priority(memory):
    put(memory, '全局先举例', scope='global')
    first = put(memory, '本课程先举例')
    assert memory.read('alice', 'course')['items'][0]['value'] == '本课程先举例'
    assert memory.read('bob', 'course')['items'] == []
    assert memory.read('alice', None)['items'][0]['value'] == '全局先举例'
    with pytest.raises(HTTPException):
        put(memory, '覆盖', revision=0)
    assert first['revision'] == 1

def test_delete_suppresses_old_source_and_invalidates_epoch(memory):
    first = put(memory)
    deleted = memory.delete('alice', 'course', 'example_order', 'course', first['revision'], operation_id='delete-1')
    assert memory.read('alice', 'course')['items'] == []
    assert deleted['memory_epoch'] > first['memory_epoch']
    assert memory.suppressed('alice', 'source-1')
    with pytest.raises(HTTPException):
        put(memory, revision=deleted['revision'], source='source-1')
    put(memory, revision=deleted['revision'], source='new-source')
    assert memory.suppressed('alice', 'source-1')

def test_transient_or_forged_quote_cannot_write(memory):
    for question, quote in [('这次先举例', '这次先举例'), ('解释变量', '以后都先举例')]:
        with pytest.raises(HTTPException):
            memory.apply_explicit_request({'owner':'alice', 'course_id':'course', 'turn_id':'turn', 'request':{'question':question}},
                {'operation':'set', 'field':'example_order', 'scope':'course', 'value':'先举例', 'source_quote':quote}, 'op')
    assert memory.read('alice', 'course')['items'] == []

def test_deletion_fences_running_answer_and_final_transaction(memory):
    import json
    from app.self_learning.agent_runtime import LearningAgentRuntime
    from app.self_learning.turn_contracts import AgentFailure
    from tests.self_learning.test_agent_runtime import accept
    svc = memory.learning
    first = put(memory)
    turn = accept(svc)
    class Model:
        async def complete(self, messages, tools, deadline):
            memory.delete('alice', 'course', 'example_order', 'course', first['revision'], operation_id='during-answer')
            return {'content': json.dumps({'answer_markdown':'含旧偏好的回答', 'citation_ids':['ctx_01']}), 'calls':[]}
    LearningAgentRuntime(svc, svc.turn_repository, lambda _: Model()).run_once()
    saved = svc.turn_repository.get('alice', turn['turn_id'])
    assert saved['status'] == 'failed' and saved['error_code'] == 'MEMORY_CONTEXT_CHANGED'
    assert all('含旧偏好' not in m['text'] for m in svc.session_repository.messages('alice', turn['session_id'])['items'])
    svc.turn_repository.control('alice', turn['turn_id'], 'retry')
    claim = svc.turn_repository.claim()
    with pytest.raises(AgentFailure):
        svc.turn_repository.finish(claim, result={'answer_markdown':'在最后提交窗口迟到', 'memory_epoch':first['memory_epoch']})


def test_legacy_delete_invalidates_epoch_and_background_cannot_restore(memory):
    from app.chat.memory.repository import SqlAlchemyMemoryRepository
    from app.chat.memory.domain import MemoryRecordDraft
    first = put(memory)
    current = memory.read('alice', 'course')['items'][0]
    legacy = SqlAlchemyMemoryRepository(memory.engine)
    assert legacy.invalidate(memory_id=current['memory_id'], subject_user_id='alice', reason='user_requested')
    assert memory.epoch('alice') > first['memory_epoch']
    with pytest.raises(ValueError):
        legacy.upsert_memory(MemoryRecordDraft(subject_user_id='alice', owner_user_id='alice', course_id='course',
            memory_type='preference', fact_kind='explicit', content='先举例', confidence=1.,
            source_type='conversation', source_id='old-message', source_span='先举例', profile_axis='learning_style'))
    assert not memory.read('alice', 'course')['items']

def test_deleted_source_is_filtered_from_context_and_history(memory):
    from app.self_learning.context_builder import ContextBuilder
    from app.self_learning.tools import LearningTools
    from tests.self_learning.test_agent_runtime import accept
    svc = memory.learning
    turn = accept(svc)
    row = svc.turn_repository.get('alice', turn['turn_id'])
    first = put(memory, source='past:user')
    with svc.session_repository._write(turn['session_id']) as db:
        session = svc.session_repository._owned(db, 'alice', turn['session_id'])
        svc.session_repository._append(db, session, 'past:user', 'user', '以后都先举例', 'user_content', {'request_id':'past'})
        svc.session_repository._append(db, session, 'past:assistant', 'assistant', '将先举例', 'assistant_content', {'request_id':'past'})
    memory.delete('alice', 'course', 'example_order', 'course', first['revision'], operation_id='suppress-history')
    packet = ContextBuilder(svc).build(row)
    assert '以后都先举例' not in str(packet)
    tool = LearningTools(svc, row, packet)
    result = tool.dispatch({'id':'history', 'function':{'name':'search_learning_history','arguments':'{"query":"举例"}'}})
    assert result['data']['items'] == []


def test_preference_tool_replay_and_observation_have_real_receipts(memory):
    import json
    from app.self_learning.agent_runtime import LearningAgentRuntime
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.self_learning.enrichment_models import LearningObservation
    from tests.self_learning.test_agent_runtime import accept, request, Model
    svc = memory.learning
    first = accept(svc, request('以后都先举例'))
    call = {'id':'pref', 'type':'function', 'function':{'name':'update_learning_preference',
        'arguments':json.dumps({'operation':'set','field':'example_order','scope':'global','value':'先举例','source_quote':'以后都先举例'})}}
    model = Model([{'content':'', 'calls':[call]}, {'calls':[], 'content':json.dumps({'answer_markdown':'已保存偏好', 'citation_ids':['ctx_01'],
        'observation':{'kind':'helpful_explanation','text':'用户希望先看例子','source_message_ids':[first['turn_id']+':user'],'objective_ids':[]}})}])
    LearningAgentRuntime(svc, svc.turn_repository, lambda _:model).run_once()
    result = svc.turn_repository.get('alice', first['turn_id'])
    assert result['status'] == 'succeeded', result
    assert memory.read('alice', 'course')['items'][0]['revision'] == 1
    with Session(memory.engine) as db:
        observation = db.scalar(select(LearningObservation))
        assert observation.status == 'hypothesis' and observation.owner == 'alice'
    assert '有效长期偏好' in model.messages[-1]

def test_crash_after_preference_commit_reconciles_receipt_before_epoch_check(memory):
    import asyncio
    import copy
    import json
    from app.self_learning.agent_runtime import LearningAgentRuntime
    from app.self_learning.context_builder import ContextBuilder
    from app.self_learning.tools import LearningTools
    from app.self_learning.turn_repository import TurnRepository
    from tests.self_learning.test_agent_runtime import accept, request, Model
    svc, clock = memory.learning, [100.]
    repo = TurnRepository(memory.engine, clock=lambda: clock[0])
    first = accept(svc, request('以后都先举例'))
    claim = repo.claim()
    packet = ContextBuilder(svc).build(claim)
    call = {'id':'pref', 'type':'function', 'function':{'name':'update_learning_preference',
        'arguments':json.dumps({'operation':'set','field':'example_order','scope':'global','value':'先举例','source_quote':'以后都先举例'})}}
    packet['messages'].append({'role':'assistant','content':None,'tool_calls':[call]})
    repo.save(claim, {'packet':copy.deepcopy(packet),'rounds':1,'tools':0,'pending':[call],'repair_used':False})
    assert asyncio.run(LearningTools(svc,claim,packet).dispatch_write(call))['ok']
    clock[0] = 116.
    LearningAgentRuntime(svc, repo, lambda _:Model()).run_once()
    result = repo.get('alice', first['turn_id'])
    assert result['status'] == 'succeeded', result
    assert memory.read('alice','course')['items'][0]['revision'] == 1

def test_deleting_one_field_does_not_delete_another_from_same_message(memory):
    first = put(memory, source='two-fields:user')
    memory.update('alice','course','language','course','中文',0,operation_id='language',source_id='two-fields:user',source_quote='以后用中文',explicit=True)
    memory.delete('alice','course','example_order','course',first['revision'],operation_id='one-field-delete')
    assert [p['field'] for p in memory.read('alice','course')['items']] == ['language']
    assert memory.suppressed('alice','two-fields:user')  # omit ambiguous raw message span

def test_saved_preference_is_visible_when_answer_fails(memory):
    import json
    from app.self_learning.agent_runtime import LearningAgentRuntime
    from app.self_learning.turn_contracts import AgentFailure
    from tests.self_learning.test_agent_runtime import accept, request
    svc = memory.learning
    first = accept(svc, request('以后都先举例'))
    class Model:
        calls=0
        async def complete(self, messages, tools, deadline):
            self.calls += 1
            if self.calls > 1:
                raise AgentFailure('MODEL_UNAVAILABLE')
            return {'content':'','calls':[{'id':'save','type':'function','function':{'name':'update_learning_preference',
                'arguments':json.dumps({'operation':'set','field':'example_order','scope':'global','value':'先举例','source_quote':'以后都先举例'})}}]}
    LearningAgentRuntime(svc,svc.turn_repository,lambda _:Model()).run_once()
    result = svc.turns.get('alice',first['turn_id'])
    assert result['status'] == 'failed'
    assert result['committed_effects'] == [{'kind':'preference','field':'example_order','scope':'global'}]
