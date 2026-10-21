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
    Base.metadata.create_all(live_service.session_repository.engine, tables=[Base.metadata.tables[n] for n in ('learning_answer_runs', 'learning_agent_tool_calls', 'learning_agent_outbox')])
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
    history = json.loads(model.messages[-1])
    assistant_call = next(m for m in history if 'tool_calls' in m)
    assert assistant_call['tool_calls'] == [call]
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

def test_context_selection_and_course_history_shared(agent_service):
    svc = agent_service
    svc.session_repository.ensure_session('alice', 'course', 'b', 'B', [{'question': 'B秘密原文标记', 'answer_text': 'secret'}])
    first = accept(svc, request(selected='Hello'))
    packet = ContextBuilder(svc).build(svc.turn_repository.get('alice', first['turn_id']))
    assert 'B秘密原文标记' in str(packet['messages'])
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

def test_cancel_interrupts_inflight_model_and_cannot_append(agent_service):
    import asyncio
    from threading import Event, Thread
    started, stopped = Event(), Event()
    class Slow(Model):
        async def complete(self, *args, **kwargs):
            started.set()
            try:
                await asyncio.sleep(30)
            finally:
                stopped.set()
    first = accept(agent_service)
    runtime = LearningAgentRuntime(agent_service, agent_service.turn_repository, lambda _: Slow())
    worker = Thread(target=runtime.run_once)
    worker.start()
    assert started.wait(3)
    agent_service.turn_repository.control('alice', first['turn_id'], 'cancel')
    worker.join(timeout=3)
    assert not worker.is_alive() and stopped.is_set()
    assert agent_service.turns.get('alice', first['turn_id'])['status'] == 'canceled'
    assert len(agent_service.session_repository.messages('alice', first['session_id'])['items']) == 2


def test_revocation_before_work_fails_without_model(agent_service):
    svc = agent_service
    first = accept(svc)
    original = svc.require
    def denied(course, owner):
        raise HTTPException(404)
    svc.require = denied
    model = Model()
    LearningAgentRuntime(svc, svc.turn_repository, lambda _: model).run_once()
    assert not model.messages
    assert svc.turn_repository.get('alice', first['turn_id'])['error_code'] == 'CONTEXT_UNAVAILABLE'
    svc.require = original


def test_final_message_and_outbox_are_atomic(agent_service):
    from sqlalchemy import event as hook, select, func
    from sqlalchemy.orm import Session
    from app.self_learning.db_models import LearningAgentOutbox
    first = accept(agent_service)
    claim = agent_service.turn_repository.claim()
    def fail(*_):
        raise RuntimeError('outbox unavailable')
    hook.listen(LearningAgentOutbox, 'before_insert', fail)
    try:
        with pytest.raises(RuntimeError):
            agent_service.turn_repository.finish(claim, result={'answer_markdown': 'answer'})
    finally:
        hook.remove(LearningAgentOutbox, 'before_insert', fail)
    assert agent_service.turn_repository.get('alice', first['turn_id'])['status'] == 'running'
    assert len(agent_service.session_repository.messages('alice', first['session_id'])['items']) == 2
    agent_service.turn_repository.finish(claim, result={'answer_markdown': 'answer'})
    with Session(agent_service.turn_repository.engine) as db:
        assert db.scalar(select(func.count()).select_from(LearningAgentOutbox)) == 1

def test_history_search_paginates_and_scopes_to_owner(agent_service):
    svc = agent_service
    svc.session_repository.ensure_session('alice', 'course', 'b', 'B', [
        {'question': f'needle question {i}', 'answer_text': f'answer {i}'} for i in range(7)])
    svc.session_repository.ensure_session('bob', 'course', 'b', 'B', [{'question': 'needle private bob', 'answer_text': 'private'}])
    first = accept(svc)
    claim = svc.turn_repository.get('alice', first['turn_id'])
    tools = LearningTools(svc, claim, ContextBuilder(svc).build(claim))
    args = {'query': 'needle', 'limit': 4, 'topic_ids': ['b']}
    def search(params):
        return tools.dispatch({'function': {'name': 'search_learning_history', 'arguments': json.dumps(params)}})
    page = search(args)
    assert page['ok'] and len(page['data']['items']) == 4 and page['next_cursor']
    second = search({**args, 'cursor': page['next_cursor']})
    assert len(second['data']['items']) == 3 and not second['next_cursor']
    assert 'private bob' not in str([page, second])
    assert search({**args, 'scope_handle': 'foreign'})['error']['code'] == 'INVALID_ARGUMENTS'


def test_saved_checkpoint_resumes_tool_intent(agent_service):
    svc, clock = agent_service, [100.]
    repo = TurnRepository(svc.turn_repository.engine, clock=lambda: clock[0])
    first = accept(svc)
    claim = repo.claim()
    packet = ContextBuilder(svc).build(claim)
    call = {'id': 'pending', 'type': 'function', 'function': {'name': 'read_resource_excerpt', 'arguments': '{"resource_handle":"resource_01"}'}}
    packet['messages'].append({'role': 'assistant', 'content': None, 'tool_calls': [call]})
    repo.save(claim, {'packet': packet, 'rounds': 1, 'tools': 0, 'pending': [call], 'repair_used': False})
    clock[0] = 116
    model = Model()
    LearningAgentRuntime(svc, repo, lambda _: model).run_once()
    result = repo.get('alice', first['turn_id'])
    assert result['status'] == 'succeeded' and result['attempt'] == 2
    assert 'tool_call_id' in model.messages[0]
    assert len(svc.session_repository.messages('alice', first['session_id'])['items']) == 3

def test_long_document_selection_is_bounded_and_pixel_location_is_approximate():
    from app.self_learning.resource_reader import excerpt
    material = {'content': ('preface ' * 10000) + 'unique needle' + (' suffix' * 10000)}
    selected = excerpt(material, selected_text='unique needle', max_chars=3000)
    assert selected['location_quality'] == 'exact'
    assert 'unique needle' in selected['excerpt'] and len(selected['excerpt']) <= 3000
    assert excerpt(material, locator={'kind': 'document', 'scroll_top': 900})['location_quality'] == 'approximate'
    classroom = {'scenes': [{'id': 's1', 'title': 'first'}, {'id': 's2', 'title': 'second'}]}
    scene = excerpt(classroom, locator={'kind': 'classroom', 'scene_id': 's2', 'action_id': 'invented'})
    assert 'second' in scene['excerpt'] and 'first' not in scene['excerpt']
    assert scene['resolved_locator'] == {'kind': 'classroom', 'scene_id': 's2'}

def test_concurrent_accept_and_claim_are_unique(agent_service):
    from concurrent.futures import ThreadPoolExecutor
    svc = agent_service
    sid = svc.sessions.enter('alice', 'course', 'a')['session_id']
    req = request()
    with ThreadPoolExecutor(max_workers=6) as pool:
        runs = list(pool.map(lambda _: svc.turn_repository.accept('alice', sid, req), range(6)))
    assert len({r['turn_id'] for r in runs}) == 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed = list(pool.map(lambda _: svc.turn_repository.claim(), range(4)))
    assert sum(c is not None for c in claimed) == 1
    assert len(svc.session_repository.messages('alice', sid)['items']) == 2

def test_model_history_preserves_json_protocol_without_reusing_old_reference_ids(agent_service):
    svc=agent_service
    accept(svc)
    LearningAgentRuntime(svc,svc.turn_repository,lambda _:Model()).run_once()
    second=accept(svc,request('再给一步提示'))
    packet=ContextBuilder(svc).build(svc.turn_repository.get('alice',second['turn_id']))
    history=[json.loads(m['content']) for m in packet['messages'] if m['role']=='assistant']
    assert history and history[-1]['answer_markdown']=='可以这样理解。'
    assert all(m['citation_ids']==[] and m['suggested_action_ids']==[] for m in history)

def test_empty_response_has_one_bounded_retry_without_repeating_effects(agent_service):
    from app.self_learning.turn_contracts import AgentFailure
    first=accept(agent_service)
    class EmptyOnce(Model):
        attempts=0
        async def complete(self,messages,tools,deadline):
            self.attempts+=1
            if self.attempts==1:raise AgentFailure('MODEL_EMPTY_RESPONSE')
            return await super().complete(messages,tools,deadline)
    model=EmptyOnce()
    LearningAgentRuntime(agent_service,agent_service.turn_repository,lambda _:model).run_once()
    result=agent_service.turns.get('alice',first['turn_id'])
    assert result['status']=='succeeded' and result['result']['model_rounds']==2 and model.attempts==2
    class AlwaysEmpty(Model):
        async def complete(self,messages,tools,deadline):raise AgentFailure('MODEL_EMPTY_RESPONSE')
    second=accept(agent_service,request('空响应重复时明确失败'))
    LearningAgentRuntime(agent_service,agent_service.turn_repository,lambda _:AlwaysEmpty()).run_once()
    result=agent_service.turns.get('alice',second['turn_id'])
    assert result['status']=='failed' and result['error_code']=='MODEL_EMPTY_RESPONSE'
