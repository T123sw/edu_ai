import asyncio
from copy import deepcopy
import json
import time
from types import SimpleNamespace
from uuid import uuid4
import httpx
import pytest
from app.practice import service
from app.practice.experiment.repository import Conflict, ExperimentRepository, Missing, SaveRun
from app.practice.experiment.tutor import TutorQuestion, TutorRepository, stream_turn
from app.practice.experiment.tutor_transport import TutorModel
from tests.practice.test_experiment import advanced, package, view

@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_STATE_PERSISTENCE_MODE', 'json')
    return TutorRepository(ExperimentRepository(service.PracticeStore(root=tmp_path)))
def question(v=None, **kw):
    return TutorQuestion(request_id=uuid4(), question='这一步为什么这样做？', view=v or advanced(view()), **kw)

def test_freezes_old_or_unsynced_view_without_moving_run(repo):
    initial = advanced(view()); newer = advanced(initial)
    repo.repo.save('alice', 'lab', package(), SaveRun(expected_seq=-1, view=newer))
    row, execute = repo.prepare('alice', 'lab', package(), question(initial))
    assert execute and row['state_revision'] == 1
    assert repo.repo.latest('alice', 'lab')['view'] == newer
    assert repo.model_context('alice', 'lab', row)[0]['target']['facts']['focus']['after_action']['values'] == initial['state']
    latest = advanced(newer); repo.prepare('alice', 'lab', package(), question(latest))
    assert repo.repo.latest('alice', 'lab')['view'] == newer
    changed = deepcopy(latest); changed['events'][0]['actor'] = 'user'
    with pytest.raises(Conflict): repo.prepare('alice', 'lab', package(), question(changed))

def test_reply_uses_original_question_evidence_after_new_run(repo):
    old = advanced(view()); row, _ = repo.prepare('alice', 'lab', package(), question(old))
    repo.finish('alice', 'lab', row, answer='这里基准是最右元素。为什么这样选？')
    current = view(); child, _ = repo.prepare('alice', 'lab', package(), question(current, reply_to=row['request_id']))
    packet, contexts = repo.model_context('alice', 'lab', child)
    assert packet['reply_to']['answer'].endswith('为什么这样选？')
    assert packet['target']['scope']['run_id'] == old['run_id']
    assert packet['current']['scope']['run_id'] == current['run_id']
    assert contexts['target']['context_id'] == row['context_id']
    assert repo.repo.latest('alice', 'lab') is None
    with pytest.raises(Missing): repo.get('bob', 'lab', row['request_id'])
    with pytest.raises(Missing): repo.prepare('alice', 'other', package(), question(reply_to=row['request_id']))

def test_wrong_action_and_rollback_remain_distinct(repo):
    v = advanced(view()); v['phase'] = 'guided'; v['events'][0].update(phase='guided', actor='user')
    for kind, state in [('attempt_submitted', v['state']), ('retry_started', v['snapshots']['0'])]:
        n = v['seq'] + 1
        v['snapshots'][f'{n}:before'] = deepcopy(v['state']); v['snapshots'][str(n)] = deepcopy(state)
        v['state'] = deepcopy(state); v['seq'] = n
        v['events'].append(dict(id=str(uuid4()), seq=n, actor='system', phase='guided', type=kind, attempt_id=v['attempt_id'], before=f'{n}:before', after=str(n), verdict='fail', feedback='选错了'))
    row, _ = repo.prepare('alice', 'lab', package(), question(v)); packet = repo.model_context('alice', 'lab', row)[0]['target']
    assert packet['facts']['focus']['seq'] == 1
    assert packet['facts']['focus']['after_action']['values']['selected'] == 4 and packet['facts']['current']['values'] != packet['facts']['focus']['after_action']['values']
    assert packet['facts']['focus']['assessment']['verdict'] == 'fail'

def test_idempotence_failure_retry_fences_late_completion(repo):
    request = question(); row, _ = repo.prepare('alice', 'lab', package(), request)
    duplicate, execute = repo.prepare('alice', 'lab', package(), request)
    assert not execute and duplicate == row
    with pytest.raises(Conflict): repo.prepare('alice', 'lab', package(), request.model_copy(update={'question': '不同问题'}))
    with pytest.raises(Conflict): repo.retry('alice', 'lab', package(), row['request_id'])
    repo.finish('alice', 'lab', row, error='超时'); retried, execute = repo.retry('alice', 'lab', package(), row['request_id'])
    assert execute and retried['context_id'] == row['context_id']
    with pytest.raises(Conflict): repo.finish('alice', 'lab', row, answer='旧结果')
    repo.finish('alice', 'lab', retried, answer='新结果')
    assert len(repo.history('alice', 'lab')['items']) == 1
    assert not repo.retry('alice', 'lab', package(), row['request_id'])[1]

def test_scope_validation_and_history_pagination(repo):
    with pytest.raises(ValueError): repo.prepare('alice', 'lab', package(), question(focus_event_id='missing'))
    altered = view(); altered['revision'] = 'b' * 64
    with pytest.raises(Conflict): repo.prepare('alice', 'lab', package(), question(altered))
    ids = [repo.prepare('alice', 'lab', package(), question())[0]['request_id'] for _ in range(4)]
    page = repo.history('alice', 'lab', limit=2)
    assert [r['request_id'] for r in page['items']] == ids[2:]
    assert [r['request_id'] for r in repo.history('alice', 'lab', before=page['next_cursor'])['items']] == ids[:2]
    with pytest.raises(Missing): repo.history('bob', 'lab', before=ids[0])

class FakeModel:
    def __init__(self, fail=False): self.rounds = []; self.fail = fail
    async def stream(self, messages, tools):
        self.rounds.append(deepcopy(messages))
        if len(self.rounds) == 1:
            yield {'type': 'result', 'content': '', 'calls': [{'id': 'call-1', 'type': 'function', 'function': {'name': 'read_experiment_evidence', 'arguments': json.dumps({'scope': 'target', 'request': {'tool': 'get_snapshot', 'snapshot_id': '0'}})}}]}
        else:
            yield {'type': 'delta', 'text': '根据刚才的操作，'}
            if self.fail: raise RuntimeError('模拟断线')
            yield {'type': 'delta', 'text': '应该选择约定的基准。'}
            yield {'type': 'result', 'content': '根据刚才的操作，应该选择约定的基准。', 'calls': []}

@pytest.mark.parametrize('fail', [False, True])
def test_stream_tools_persistence_and_failure(repo, fail):
    row, _ = repo.prepare('alice', 'lab', package(), question()); model = FakeModel(fail)
    async def run(): return [json.loads(item[6:]) async for item in stream_turn(repo, 'alice', 'lab', row, True, model=model)]
    events = asyncio.run(run()); assert events[0]['type'] == 'accepted'
    assert events[-1]['type'] == ('error' if fail else 'done') and model.rounds[1][-1]['role'] == 'tool'
    assert model.rounds[0][-1] == {'role':'user','content':row['question']}
    saved = repo.get('alice', 'lab', row['request_id']); assert saved['status'] == ('failed' if fail else 'complete')
    assert bool(saved['answer']) is not fail and repo.repo.latest('alice', 'lab') is None

def test_long_history_can_be_read_without_claiming_all_loaded(repo):
    v = view()
    for _ in range(30): v = advanced(v)
    row, _ = repo.prepare('alice', 'lab', package(), question(v)); packet, contexts = repo.model_context('alice', 'lab', row)
    assert packet['target']['facts']['coverage']['history_details_partial'] and len(contexts['target']['events']) == 30

def test_interrupted_execution_expires_and_can_retry(repo):
    row, _ = repo.prepare('alice', 'lab', package(), question()); row['lease_until'] = time.time() - 1
    repo.store.put('alice', 'lab:tutor:' + row['request_id'], row)
    assert repo.history('alice', 'lab')['items'][0]['status'] == 'failed'
    assert repo.retry('alice', 'lab', package(), row['request_id'])[1]

def gateway():
    return SimpleNamespace(candidates=[{'model_name': 'test', 'api_base': 'https://model.test/v1', 'api_key': 'unused'}], _thinking_params=lambda _: {}, _build_headers=lambda _: {})

@pytest.mark.parametrize('finish', ['stop', None, 'length'])
def test_transport_real_sse_requires_completion(finish):
    def handler(request):
        payload = json.loads(request.content); assert payload['stream'] is True and 'response_format' not in payload
        rows = [{'choices': [{'delta': {'content': '交换 5 和 2'}, 'finish_reason': None}]}]
        if finish: rows.append({'choices': [{'delta': {}, 'finish_reason': finish}]})
        text = ''.join('data: ' + json.dumps(r) + '\n\n' for r in rows) + 'data: [DONE]\n\n'
        return httpx.Response(200, text=text, headers={'content-type': 'text/event-stream'})
    model = TutorModel(gateway(), lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler), **kw))
    async def run(): return [item async for item in model.stream([{'role': 'user', 'content': '为什么'}], [])]
    if finish == 'stop':
        items = asyncio.run(run()); assert items[0]['text'] == '交换 5 和 2' and items[-1]['calls'] == []
    else:
        with pytest.raises(Exception): asyncio.run(run())

def test_api_ownership(monkeypatch, repo):
    from app.api import practice as api
    from fastapi import HTTPException
    monkeypatch.setattr(api, 'get_job', lambda _: SimpleNamespace(owner_user_id='alice', kind=api.JobKind.GENERATE_PRACTICE, status=api.JobStatus.SUCCEEDED))
    monkeypatch.setattr(api, 'PracticeStore', lambda: repo.store)
    repo.store.put('alice', 'lab', {'html': 'ready', 'experiment': package()})
    with pytest.raises(HTTPException) as exc: api.experiment_tutor_ask('lab', question(), {'username': 'bob'})
    assert exc.value.status_code == 404
    row,_=repo.prepare('alice','lab',package(),question())
    monkeypatch.setattr(api,'TutorRepository',lambda:repo)
    from uuid import UUID
    result=api.experiment_tutor_message('lab',UUID(row['request_id']),{'username':'alice'})
    assert result['request_id']==row['request_id'] and 'skill' not in result and 'body_hash' not in result

def test_same_sequence_metadata_cannot_be_changed(repo):
    v=advanced(view());repo.repo.save('alice','lab',package(),SaveRun(expected_seq=-1,view=v))
    changed=deepcopy(v);changed['feedback']='不同的反馈'
    with pytest.raises(Conflict):repo.prepare('alice','lab',package(),question(changed))

def test_explicit_old_event_and_phase_boundaries(repo):
    v=advanced(advanced(view()))
    row,_=repo.prepare('alice','lab',package(),question(v,focus_event_id=v['events'][0]['id']))
    assert repo.model_context('alice','lab',row)[0]['target']['facts']['focus']['seq']==1
    v['events'][-1]['type']='reset'
    row,_=repo.prepare('alice','lab',package(),question(v))
    assert repo.model_context('alice','lab',row)[0]['target']['facts']['focus']['type']=='reset'

def test_closed_stream_marks_question_retryable(repo):
    row,_=repo.prepare('alice','lab',package(),question())
    async def run():
        stream=stream_turn(repo,'alice','lab',row,True,model=FakeModel())
        await anext(stream)
        await stream.aclose()
    asyncio.run(run())
    assert repo.get('alice','lab',row['request_id'])['status']=='failed'

def test_transport_fragmented_tools_and_payment_failover():
    calls=[]
    def handler(request):
        calls.append(request.headers['Authorization'])
        if len(calls)==1:return httpx.Response(402)
        rows=[{'choices':[{'delta':{'tool_calls':[{'index':0,'id':'c','function':{'name':'read_experiment_', 'arguments':'{"scope":'}}]},'finish_reason':None}]},
              {'choices':[{'delta':{'tool_calls':[{'index':0,'function':{'name':'evidence','arguments':'"target","request":{"tool":"list_events"}}'}}]},'finish_reason':'tool_calls'}]}]
        return httpx.Response(200,text=''.join('data: '+json.dumps(r)+'\n\n' for r in rows)+'data: [DONE]\n\n',headers={'content-type':'text/event-stream'})
    g=gateway();g.candidates[0]['api_key']='primary';g.candidates.append({**g.candidates[0],'api_key':'backup','only_after_status':402});g._build_headers=lambda key:{'Authorization':key}
    model=TutorModel(g,lambda **kw:httpx.AsyncClient(transport=httpx.MockTransport(handler),**kw))
    async def run():return [r async for r in model.stream([{'role':'user','content':'history'}],[])][-1]
    result=asyncio.run(run())
    assert calls==['primary','backup']
    assert result['calls'][0]['function']['name']=='read_experiment_evidence'
    assert json.loads(result['calls'][0]['function']['arguments'])['scope']=='target'

def test_sql_store_persists_teaching(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from app.database import AppStateRecord
    from app.persistence.postgres_app_state_repository import PostgresAppStateRepository
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    AppStateRecord.__table__.create(engine)
    try:
        repo=TutorRepository(ExperimentRepository(service.PracticeStore(root=tmp_path,repository=PostgresAppStateRepository(engine))))
        row,_=repo.prepare('alice','lab',package(),question());repo.finish('alice','lab',row,answer='已回应')
        assert repo.history('alice','lab')['items'][0]['answer']=='已回应'
        assert repo.history('bob','lab')['items']==[]
    finally:engine.dispose()

def test_design_initial_is_not_presented_as_an_observation(repo):
    p=package();p['spec']['tasks'][0]['initial']='设计示例数值，不是当前测量'
    v=view();v['phase']='guided'
    row,_=repo.prepare('alice','lab',p,question(v))
    packet,contexts=repo.model_context('alice','lab',row)
    assert 'initial' not in packet['target']['reference_material']['task']
    assert contexts['target']['design']['tasks'][0]['initial']=='设计示例数值，不是当前测量'

def test_actual_user_reply_is_last_message_with_original_teacher_role(repo):
    from app.practice.experiment.tutor import teach
    row,_=repo.prepare('alice','lab',package(),question())
    repo.finish('alice','lab',row,answer='如果前小后大，还需要交换吗？')
    follow=question(reply_to=row['request_id']).model_copy(update={'question':'仍然要交换'})
    child,_=repo.prepare('alice','lab',package(),follow)
    packet,contexts=repo.model_context('alice','lab',child);model=FakeModel()
    async def run():return [item async for item in teach('alice',packet,contexts,child['skill'],model=model)]
    asyncio.run(run())
    assert model.rounds[0][-2:]==[{'role':'assistant','content':'如果前小后大，还需要交换吗？'},{'role':'user','content':'仍然要交换'}]

def test_retry_receipt_repairs_interrupted_history_index(repo):
    request=question();row,_=repo.prepare('alice','lab',package(),request)
    repo.store.put('alice','lab:tutor-index',{'ids':[]})
    same,execute=repo.prepare('alice','lab',package(),request)
    assert same['request_id']==row['request_id'] and not execute
    assert repo.history('alice','lab')['items'][0]['request_id']==row['request_id']


@pytest.mark.parametrize('batches', [(8,), (7, 2)])
def test_evidence_budget_ends_in_answer_instead_of_failing_question(repo, batches):
    from app.practice.experiment.tutor import teach
    row, _ = repo.prepare('alice', 'lab', package(), question())
    packet, contexts = repo.model_context('alice', 'lab', row)
    class Model:
        rounds = 0
        async def stream(self, messages, tools):
            self.rounds += 1
            if self.rounds <= len(batches):
                assert tools
                yield {'type': 'result', 'content': '', 'calls': [
                    {'id': f'call-{self.rounds}-{i}', 'type': 'function', 'function': {
                        'name': 'read_experiment_evidence', 'arguments': json.dumps({'scope': 'target', 'request': {'tool': 'get_snapshot', 'snapshot_id': '0'}})}}
                    for i in range(batches[self.rounds - 1])]}
            else:
                assert tools == []
                replies = [json.loads(m['content']) for m in messages if m['role'] == 'tool']
                assert len(replies) == sum(batches)
                assert sum('error' not in value for value in replies) == 8
                yield {'type': 'delta', 'text': '已记录当前状态，但结束原因未知。'}
                yield {'type': 'result', 'content': '已记录当前状态，但结束原因未知。', 'calls': []}
    model = Model()
    async def run():
        return [event async for event in teach('alice', packet, contexts, row['skill'], model=model)]
    events = asyncio.run(run())
    assert model.rounds == len(batches) + 1
    assert events[-1]['text'] == '已记录当前状态，但结束原因未知。'
