import json
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.database import Base
from app.self_learning.agent_runtime import LearningAgentRuntime
from app.self_learning.turn_repository import TurnRepository, LostLease
from app.self_learning.turn_service import TurnService
from app.self_learning.turn_contracts import AnswerRequest
from app.self_learning.context_builder import ContextBuilder
from app.self_learning.tools import LearningTools
from tests.self_learning.test_session_api import live_service, repository, client
from tests.self_learning.test_progress_api import enable

@pytest.fixture
def agent_service(live_service):
    enable(live_service)
    Base.metadata.create_all(live_service.session_repository.engine, tables=[Base.metadata.tables[n] for n in ('learning_answer_runs', 'learning_agent_tool_calls')])
    live_service.turn_repository = TurnRepository(live_service.session_repository.engine)
    live_service.turns = TurnService(live_service, live_service.turn_repository)
    return live_service

def request(question='解释内容', selected=''):
    return AnswerRequest(request_id=uuid4(), question=question, reading_context={
        'resource_ref': {'course_id': 'course', 'material_type': 'report', 'material_id': 'doc', 'version': 1}, 'selected_text': selected})

class Model:
    def __init__(self, replies=None):
        self.replies, self.messages = replies or [], []
    async def complete(self, messages, tools, deadline):
        self.messages.append(json.dumps(messages, ensure_ascii=False))
        return self.replies.pop(0) if self.replies else {'content': json.dumps({'answer_markdown': '可以这样理解。', 'citation_ids': ['ctx_01']}), 'calls': []}

def accept(svc, req=None):
    return svc.turns.accept('alice', 'course', 'a', req or request())

def test_accept_replay_scope_and_durable_restart(agent_service):
    svc, req = agent_service, request()
    first = accept(svc, req)
    assert first['status'] == 'accepted' and accept(svc, req)['turn_id'] == first['turn_id']
    with pytest.raises(HTTPException) as conflict:
        accept(svc, req.model_copy(update={'question': 'different'}))
    assert conflict.value.status_code == 409
    with pytest.raises(HTTPException):
        svc.turns.get('bob', first['turn_id'])
    restarted = LearningAgentRuntime(svc, TurnRepository(svc.turn_repository.engine), lambda _: Model())
    assert restarted.run_once()
    result = svc.turns.get('alice', first['turn_id'])
    assert result['status'] == 'succeeded', result
    assert result['result']['citations'][0]['resource_ref']['version'] == 1
    assert not restarted.run_once()
    assert len(svc.session_repository.messages('alice', first['session_id'])['items']) == 3

def test_read_tools_and_unknown_tool_budget(agent_service):
    svc = agent_service
    call = {'id': 'one', 'type': 'function', 'function': {'name': 'read_resource_excerpt', 'arguments': '{"resource_handle":"resource_01"}'}}
    model = Model([{'content': 'unpublished intermediate', 'calls': [call]}])
    first = accept(svc)
    LearningAgentRuntime(svc, svc.turn_repository, lambda _: model).run_once()
    result = svc.turns.get('alice', first['turn_id'])
    assert result['status'] == 'succeeded' and result['result']['tool_attempts'] == 1, result
    assert 'tool_call_id' in model.messages[-1]
    claim = svc.turn_repository.get('alice', first['turn_id'])
    tools = LearningTools(svc, claim, ContextBuilder(svc).build(claim))
    call['function']['name'] = 'submit_preparation_request'
    assert tools.dispatch(call)['error']['code'] == 'UNKNOWN_TOOL'
    call['function'] = {'name': 'read_resource_excerpt', 'arguments': '{"resource_handle":"resource_01","owner":"bob"}'}
    assert tools.dispatch(call)['error']['code'] == 'INVALID_ARGUMENTS'

def test_lease_fencing_cancel_retry_without_duplicate_user(agent_service):
    svc, clock = agent_service, [100.]
    repo = TurnRepository(svc.turn_repository.engine, clock=lambda: clock[0])
    first = accept(svc)
    old = repo.claim()
    clock[0] = 116
    reclaimed = repo.claim()
    assert reclaimed['attempt'] == 2
    with pytest.raises(LostLease):
        repo.finish(old, result={'answer_markdown': 'stale'})
    repo.control('alice', first['turn_id'], 'cancel')
    with pytest.raises(LostLease):
        repo.finish(reclaimed, result={'answer_markdown': 'canceled'})
    repo.control('alice', first['turn_id'], 'retry')
    LearningAgentRuntime(svc, repo, lambda _: Model()).run_once()
    assert repo.get('alice', first['turn_id'])['status'] == 'succeeded'
    assert len(svc.session_repository.messages('alice', first['session_id'])['items']) == 3

def test_unknown_citation_repaired_once_then_failed(agent_service):
    invalid = {'content': json.dumps({'answer_markdown': 'fake', 'citation_ids': ['made-up']}), 'calls': []}
    first = accept(agent_service)
    LearningAgentRuntime(agent_service, agent_service.turn_repository, lambda _: Model([invalid, invalid])).run_once()
    result = agent_service.turns.get('alice', first['turn_id'])
    assert result['status'] == 'failed' and result['error_code'] == 'ANSWER_SCHEMA_INVALID'
    assert len(agent_service.session_repository.messages('alice', first['session_id'])['items']) == 2

def test_context_selection_and_foreign_history_excluded(agent_service):
    svc = agent_service
    svc.session_repository.ensure_session('alice', 'course', 'b', 'B', [{'question': 'B秘密原文标记', 'answer_text': 'secret'}])
    first = accept(svc, request(selected='Hello'))
    packet = ContextBuilder(svc).build(svc.turn_repository.get('alice', first['turn_id']))
    assert 'B秘密原文标记' not in str(packet['messages'])
    assert '"selection_verified": true' in str(packet['messages'])
    assert packet['citations']['ctx_01']['locator']['offset'] == 0
    assert packet['input_bytes'] <= 24000

def test_api_accept_is_async_and_legacy_writer_disabled(agent_service, client):
    req = request().model_dump(mode='json')
    url = '/api/self-learning/courses/course/topics/a/agent-turns'
    accepted = client.post(url, json=req)
    assert accepted.status_code == 202, accepted.text
    tid = accepted.json()['turn_id']
    assert client.get('/api/self-learning/agent-turns/' + tid).json()['status'] == 'accepted'
    assert client.get('/api/self-learning/agent-turns/' + tid, headers={'x-user': 'bob'}).status_code == 404
    assert client.post('/api/self-learning/courses/course/topics/a/turns', json={'question': 'old', 'resource_id': 'doc', 'request_id': str(uuid4())}).status_code == 409
    LearningAgentRuntime(agent_service, agent_service.turn_repository, lambda _: Model()).run_once()
    assert client.get(url).json()[0]['status'] == 'succeeded'
    assert client.get('/api/self-learning/courses/course/materials/report/doc/versions/2').status_code == 409


def test_exact_old_version_and_no_fallback(agent_service):
    from app.self_learning.resource_reader import exact_material
    from app.self_learning.contracts import ResourceRef
    svc = agent_service
    old = svc.material('course', 'report', 'doc', 'alice')
    svc.manager.save_generated_material('course', 'report', 'doc', {**old, 'version': 2, 'content': 'NEW BODY', 'revision_history': {'1': old}},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    ref = ResourceRef(course_id='course', material_type='report', material_id='doc', version=1)
    assert exact_material(svc, 'alice', ref)['content'] == 'Hello'
    with pytest.raises(HTTPException):
        exact_material(svc, 'alice', ref.model_copy(update={'version': 77}))
    first = accept(svc, request(selected='Hello'))
    packet = ContextBuilder(svc).build(svc.turn_repository.get('alice', first['turn_id']))
    assert 'NEW BODY' not in str(packet)


def test_tool_budget_and_checkpoint_recovery(agent_service):
    svc = agent_service
    call = lambda i: {'id': str(i), 'type': 'function', 'function': {'name': 'unknown', 'arguments': '{}'}}
    model = Model([{'content': '', 'calls': [call(i)]} for i in range(8)])
    first = accept(svc)
    LearningAgentRuntime(svc, svc.turn_repository, lambda _: model).run_once()
    assert svc.turns.get('alice', first['turn_id'])['error_code'] == 'TOOL_BUDGET_EXHAUSTED'
    assert len(model.messages) == 7
