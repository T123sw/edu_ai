import json
import pytest
from app.self_learning.agent_runtime import LearningAgentRuntime
from app.self_learning.context_builder import ContextBuilder
from app.self_learning.check_service import CheckService
from app.self_learning.summary_service import SummaryService
from app.self_learning.enrichment_models import LearningObservation, LearningContextSummary
from app.self_learning.tools import LearningTools, ReadSummary
from tests.self_learning.test_agent_runtime import accept, request, Model
from tests.self_learning.test_memory_lifecycle import memory, agent_service, live_service, repository
from tests.self_learning.test_session_api import client
from tests.self_learning.test_summary_service import histories


@pytest.fixture
def noted(memory):
    svc = memory.learning
    svc.checks = CheckService(svc, memory.engine)
    svc.summaries = SummaryService(svc, memory.engine, memory)
    turn = accept(svc, request(question='我还是不理解变量绑定'))
    answer = {'answer_markdown': '可以把变量名理解为标签。', 'citation_ids': ['ctx_01'],
              'observation': {'kind': 'difficulty', 'text': '用户表示还不理解变量绑定',
                              'source_message_ids': [turn['turn_id'] + ':user']}}
    model = Model([{'content': json.dumps(answer, ensure_ascii=False), 'calls': []}])
    LearningAgentRuntime(svc, svc.turn_repository, lambda _: model).run_once()
    assert svc.turns.get('alice', turn['turn_id'])['status'] == 'succeeded'
    return svc, turn


def test_notes_show_owned_source_and_corrections_fence_context(noted, client):
    svc, turn = noted
    path = '/api/self-learning/courses/course/topics/a/observations'
    note = client.get(path).json()['items'][0]
    assert note['sources'][0]['quote'] == '我还是不理解变量绑定'
    assert note['resource_ref']['material_id'] == 'doc'
    assert client.get(path, headers={'x-user': 'bob'}).json()['items'] == []
    assert client.post('/api/self-learning/observations/' + turn['turn_id'], json={'status': 'resolved'}, headers={'x-user': 'bob'}).status_code == 404
    before = svc.memory.epoch('alice')
    url = '/api/self-learning/observations/' + turn['turn_id']
    assert client.post(url, json={'status': 'resolved'}).status_code == 200
    assert svc.memory.epoch('alice') == before + 1
    assert client.post(url, json={'status': 'resolved'}).status_code == 200
    assert svc.memory.epoch('alice') == before + 1
    another = accept(svc, request(question='继续举个例子'))
    packet = ContextBuilder(svc).build(svc.turn_repository.get('alice', another['turn_id']))
    assert '"status": "resolved"' in packet['messages'][-3]['content']
    assert '本轮课程归属' in packet['messages'][-2]['content']
    assert not any(m['content'] == '我还是不理解变量绑定' for m in packet['messages'])
    tools = LearningTools(svc, svc.turn_repository.get('alice', another['turn_id']), packet)
    assert tools.summary(ReadSummary())['data']['teaching_notes'] == []
    assert all(not r.get('completed') for r in svc.progress_service.repository.read('alice', 'course')['resources'])


def test_correction_during_answer_rejects_stale_publication(noted, client):
    svc, previous = noted
    turn = accept(svc, request(question='回顾上次困难'))
    class CorrectDuringCall:
        async def complete(self, messages, tools, deadline):
            assert client.post('/api/self-learning/observations/' + previous['turn_id'], json={'status': 'retracted'}).status_code == 200
            return {'content': json.dumps({'answer_markdown': '过时的困难描述', 'citation_ids': []}), 'calls': []}
    LearningAgentRuntime(svc, svc.turn_repository, lambda _: CorrectDuringCall()).run_once()
    result = svc.turns.get('alice', turn['turn_id'])
    assert result['status'] == 'failed' and result['error_code'] == 'MEMORY_CONTEXT_CHANGED'
    assert all('过时的困难描述' not in m['text'] for m in svc.sessions.messages('alice', 'course', 'a')['items'])


def test_summary_labels_assistant_claims_and_omits_withdrawn_sources(memory):
    sid = histories(memory)
    summaries = SummaryService(memory.learning, memory.engine, memory)
    packet = summaries.prepare('alice', sid)
    assert summaries.commit(packet, {'items': [{'text': '助手称课程未知', 'source_ids': ['a0'], 'kind': 'fact'}]})
    item = summaries.read('alice', sid)['items'][0]
    assert item['kind'] == 'hypothesis' and item['sources'][0]['role'] == 'assistant'
    with memory._write('withdraw-test') as db:
        db.add(LearningObservation(turn_id='withdrawn', owner='alice', course_id='course', topic_id='a',
            payload={'source_message_ids': ['u0']}, status='retracted'))
        row = db.get(LearningContextSummary, sid)
        row.status = 'invalidated'
    updated = summaries.prepare('alice', sid)
    assert all(m['id'] not in {'u0', 'a0'} for m in updated['messages'])


def test_related_topic_notes_are_opt_in_and_user_scoped(noted):
    svc, turn = noted
    packet = ContextBuilder(svc).build(svc.turn_repository.get('alice', turn['turn_id']))
    tools = LearningTools(svc, svc.turn_repository.get('alice', turn['turn_id']), packet)
    assert len(tools.summary(ReadSummary(topic_ids=['a']))['data']['teaching_notes']) == 1
    assert tools.summary(ReadSummary(topic_ids=['a'], include_open_questions=False))['data']['teaching_notes'] == []
    assert tools.summary(ReadSummary(topic_ids=['b']))['data']['teaching_notes'] == []
