import asyncio
import base64
import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from app.database.models import AppStateRecord
from app.exam_generation.repository import GenerationRepository, GenerationNotFound, GenerationConflict
from app.exam_generation.schemas import CreateGeneration
from app.exam_generation.snapshots import SnapshotCodec
from app.exam_generation.sources import GenerationSources
from app.exam_generation.service import ExamGenerationHandler
from app.services.runtime_config_store import RuntimeConfigStore
from app.services.durable_task_handlers import DurableExecutionContext, DurableTaskExecutionError
from app.integrations.deeptutor.client import DeepTutorError


@pytest.fixture
def repo(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'generation.db'), connect_args={'check_same_thread': False})
    AppStateRecord.__table__.create(engine)
    yield GenerationRepository(engine)
    engine.dispose()


@pytest.fixture
def codec(tmp_path):
    store = RuntimeConfigStore(root=tmp_path / 'settings', master_key='isolated')
    class Resolver:
        def capture_snapshot(self, owner): return {'llm': 'revision-1'}
        def resolve(self, provider, **kwargs):
            return {'model': 'model-' + kwargs['owner_user_id'], 'api_key': 'PRIVATE_KEY', 'base_url': 'https://model.invalid/v1'}
    resolver = Resolver()
    resolver.store = store
    return SnapshotCodec(resolver)


def request():
    return CreateGeneration(request_id=uuid4(), requirement='排序练习', num_questions=1).model_dump(mode='json')


def create(repo, codec, owner='alice', payload=None):
    return repo.create(owner, payload or request(), sources=[], encrypted_snapshot=codec.capture(owner))


def context(row, *, attempt=1, cancel=lambda: False):
    return DurableExecutionContext(task_id=row['id'], owner_user_id=row['owner'], course_id=None,
        config_snapshot_id=None, progress=lambda *args: None, is_cancel_requested=cancel,
        attempt_count=attempt, is_lease_valid=lambda: True)


class Client:
    def __init__(self, fail=False, hanging=False):
        self.starts = 0
        self.submissions = []
        self.cursors = []
        self.fail, self.hanging, self.canceled = fail, hanging, False
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def start(self, *, owner, request):
        self.starts += 1
        self.submissions.append(request)
        assert request['runtime_model']['model'] == 'model-' + owner
        assert request['runtime_text_model']['model'] == 'model-' + owner
        return {'session_id': 's', 'turn_id': 't'}
    async def status(self, **kwargs): return {'status': 'completed'}
    async def cancel(self, **kwargs): self.canceled = True
    async def internal_events(self, *, after_seq, **kwargs):
        self.cursors.append(after_seq)
        if self.hanging:
            await asyncio.sleep(10)
        for event in [{'seq': 1, 'type': 'result', 'metadata': {'answer': 'PRIVATE_ANSWER', 'summary': {'success': True, 'completed': 1, 'failed': 0, 'template_count': 1, 'results': [{'qa_pair': {'correct_answer': 'PRIVATE_ANSWER'}}]}}},
                      {'seq': 2, 'type': 'done', 'metadata': {'status': 'completed'}}]:
            if event['seq'] > after_seq:
                yield event
                if self.fail:
                    self.fail = False
                    raise DeepTutorError(503, 'connection interrupted')


def test_owner_idempotency_and_conflicting_request(repo, codec):
    r = request()
    row = create(repo, codec, payload=r)
    assert create(repo, codec, payload=r)['id'] == row['id']
    with pytest.raises(GenerationConflict): create(repo, codec, payload={**r, 'requirement': 'different'})
    with pytest.raises(GenerationNotFound): repo.get('bob', row['id'])
    assert create(repo, codec, 'bob', r)['id'] != row['id']


def test_frozen_configuration_is_encrypted_and_bound_to_owner(codec):
    encrypted = codec.capture('alice')
    assert 'PRIVATE_KEY' not in encrypted
    codec.resolver.resolve = lambda *args, **kwargs: {'model': 'changed'}
    assert codec.read('alice', encrypted)['llm']['model'] == 'model-alice'
    with pytest.raises(PermissionError): codec.read('bob', encrypted)


def test_parser_receives_authorized_immutable_bytes_and_preserves_artifacts():
    data = b'# Sorting\nQuick sort partitions elements around a pivot.'
    class Reader:
        def read_bytes(self, owner, doc):
            if owner != 'alice': raise PermissionError()
            return {'filename': 'sorting.md'}, data
    sources = GenerationSources(reader=Reader())
    refs = sources.freeze('alice', [{'document_id': 'd', 'role': 'context'}])
    parsed = sources.parse('alice', refs, {}, canceled=lambda: False, on_remote_task=lambda t: None)
    assert parsed[0]['content'].encode() == data
    with pytest.raises(PermissionError): sources.freeze('bob', [{'document_id': 'd', 'role': 'context'}])
    refs[0]['source_hash'] = '0' * 64
    with pytest.raises(PermissionError): sources.parse('alice', refs, {}, canceled=lambda: False, on_remote_task=lambda t: None)


def test_replay_after_transport_failure_uses_persisted_turn_and_cursor(repo, codec):
    row = create(repo, codec)
    client = Client(fail=True)
    handler = ExamGenerationHandler(repo, GenerationSources(), codec, lambda: client)
    with pytest.raises(DeepTutorError): asyncio.run(handler.run({'generation_id': row['id']}, context(row)))
    assert repo.get('alice', row['id'])['last_seq'] == 1
    # Reconstruct repository/handler as after a worker restart.
    handler = ExamGenerationHandler(GenerationRepository(repo.engine), GenerationSources(), codec, lambda: client)
    result = asyncio.run(handler.run({'generation_id': row['id']}, context(row, attempt=2)))
    assert result['saved'] and client.starts == 1 and client.cursors == [0, 1]
    assert len(repo.get('alice', row['id'])['events']) == 2
    assert 'PRIVATE_ANSWER' not in json.dumps(result)
    with pytest.raises(GenerationConflict): repo.event('alice', row['id'], 1, {'seq': 3})


def test_cancel_during_silent_stream_reaches_original_turn(repo, codec):
    row = create(repo, codec)
    client = Client(hanging=True)
    calls = 0
    def cancel():
        nonlocal calls
        calls += 1
        return calls >= 3
    handler = ExamGenerationHandler(repo, GenerationSources(), codec, lambda: client)
    result = asyncio.run(handler.run({'generation_id': row['id']}, context(row, cancel=cancel)))
    assert client.canceled and not result['saved']


def test_new_task_retry_keeps_old_result_and_uses_new_submission(repo, codec):
    row = create(repo, codec)
    repo.claim('alice', row['id'], 3)
    client = Client()
    ctx = context(row)
    from dataclasses import replace
    ctx = replace(ctx, task_id='new-retry-job')
    result = asyncio.run(ExamGenerationHandler(repo, GenerationSources(), codec, lambda: client).run({'generation_id': row['id']}, ctx))
    assert result['result_ref']['generation_id'] != row['id']
    assert repo.get('alice', row['id'])['turn_id'] is None
    assert client.submissions[0]['checkpoint_id'] == row['request']['request_id']
    assert client.submissions[0]['request_id'] != row['request']['request_id']


def test_failed_service_turn_cannot_be_reported_as_saved(repo, codec):
    row = create(repo, codec)
    client = Client()
    async def failed(**kwargs): return {'status': 'failed'}
    client.status = failed
    with pytest.raises(DurableTaskExecutionError):
        asyncio.run(ExamGenerationHandler(repo, GenerationSources(), codec, lambda: client).run({'generation_id': row['id']}, context(row)))


def test_public_api_enqueues_once_and_keeps_private_records_off_wire(repo, codec, tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import exam_generations as api
    from app.auth import get_current_user
    from app.chat.tasks.task_store import TaskStore, get_task_store
    from app.services import job_store
    from core.config import Config
    monkeypatch.setenv('JOB_PERSISTENCE_MODE', 'json')
    monkeypatch.setattr(Config, 'STORAGE_ROOT', tmp_path / 'jobs')
    tasks = TaskStore(str(tmp_path / 'tasks.db'))
    app = FastAPI()
    app.include_router(api.router)
    actor = {'username': 'alice'}
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[api.repository] = lambda: repo
    app.dependency_overrides[api.snapshot_codec] = lambda: codec
    app.dependency_overrides[api.source_reader] = lambda: SimpleNamespace(freeze=lambda owner, refs: [])
    app.dependency_overrides[get_task_store] = lambda: tasks
    with TestClient(app) as client:
        payload = request()
        response = client.post('/api/exam-generations', json=payload)
        assert response.status_code == 202
        gid = response.json()['generation_id']
        assert client.post('/api/exam-generations', json=payload).json() == response.json()
        assert client.post('/api/exam-generations', json={**payload, 'requirement': 'other'}).status_code == 409
        assert tasks.get_durable(gid).command == {'generation_id': gid, 'deadline_seconds': 1800, 'execution_timeout_seconds': 1800}
        repo.claim('alice', gid, 1)
        repo.event('alice', gid, 1, {'seq': 1, 'type': 'result', 'metadata': {'answer': 'PRIVATE_ANSWER', 'summary': {'success': True, 'completed': 1, 'failed': 0, 'template_count': 1, 'results': [{'qa_pair': {'correct_answer': 'PRIVATE_ANSWER'}}]}}})
        public = client.get('/api/exam-generations/' + gid)
        assert 'PRIVATE' not in public.text and 'encrypted_snapshot' not in public.text
        assert public.json()['exam_ready'] is False
        actor['username'] = 'bob'
        assert client.get('/api/exam-generations/' + gid).status_code == 404
    tasks.close()


def test_existing_durable_executor_runs_the_registered_generation_contract(repo, codec, tmp_path, monkeypatch):
    from app.chat.tasks.task_store import TaskStore
    from app.services.durable_task_handlers import DurableTaskHandlerRegistry
    from app.services.durable_task_executor import DurableTaskExecutor
    from app.services.job_completion_service import JobCompletionService
    from app.services.job_store import create_job, get_job, JobKind, JobStatus
    from app.services.platform_task_handlers import enqueue_platform_task
    from core.config import Config
    monkeypatch.setenv('JOB_PERSISTENCE_MODE', 'json')
    monkeypatch.setattr(Config, 'STORAGE_ROOT', tmp_path / 'jobs')
    row = create(repo, codec)
    tasks = TaskStore(str(tmp_path / 'tasks.db'))
    job = create_job(edu_job_id=row['id'], owner_user_id='alice', kind=JobKind.GENERATE_EXAM)
    enqueue_platform_task(job=job, workflow_type='exam_generate', command={'generation_id': row['id']}, task_store=tasks)
    registry = DurableTaskHandlerRegistry()
    registry.register('exam_generate', 1, ExamGenerationHandler(repo, GenerationSources(), codec, lambda: Client()))
    monkeypatch.setattr('app.exam_generation.repository.GenerationRepository', lambda: repo)
    executor = DurableTaskExecutor(task_store=tasks, handler_registry=registry,
        completion_service=JobCompletionService(task_store=tasks), lease_seconds=20, heartbeat_interval=5)
    assert executor.run_once()
    durable = tasks.get_durable(row['id'])
    assert durable.status == 'succeeded' and get_job(row['id']).status == JobStatus.SUCCEEDED
    assert durable.result_ref['resource_type'] == 'exam_generation'
    assert 'PRIVATE' not in json.dumps(durable.result)
    tasks.close()


def test_mineru_adapter_retains_exact_text_layout_and_images():
    from app.integrations.pdf.base import ParsedPdf
    data = b'office-file'
    parsed = ParsedPdf(text='A table and a formula $n log n$ with ![](images/plot.png).',
        metadata={'parser': 'mineru-cloud', 'layout': [{'type': 'equation', 'text': 'n log n'}],
                  'imageMapping': {'plot.png': 'data:image/png;base64,eA=='}})
    class Reader:
        def read_bytes(self, *args): return {'filename': 'notes.docx'}, data
    class Parser:
        def parse(self, actual, **kwargs):
            assert actual == data
            return parsed
    sources = GenerationSources(Reader(), lambda config: Parser())
    refs = sources.freeze('alice', [{'document_id': 'doc', 'role': 'context'}])
    actual = sources.parse('alice', refs, {}, canceled=lambda: False, on_remote_task=lambda t: None)[0]
    assert actual['content'] == parsed.text
    assert actual['content_list'] == parsed.metadata['layout']
    assert actual['images'] == {'plot.png': 'eA=='}


def test_partial_questions_do_not_pass_even_if_turn_status_is_completed(repo, codec):
    row = create(repo, codec, payload={**request(), 'num_questions': 2})
    with pytest.raises(DurableTaskExecutionError, match='未完整生成'):
        asyncio.run(ExamGenerationHandler(repo, GenerationSources(), codec, lambda: Client()).run({'generation_id': row['id']}, context(row)))


def test_batch_and_cursor_commit_together_and_replay_has_no_duplicates(repo, codec):
    row = create(repo, codec)
    repo.claim('alice', row['id'], 1)
    events = [{'seq': n, 'type': 'progress'} for n in range(1, 101)]
    repo.events_batch('alice', row['id'], 1, events)
    repo.events_batch('alice', row['id'], 1, events)
    loaded = repo.get('alice', row['id'])
    assert loaded['last_seq'] == 100 and len(loaded['events']) == 100


def test_restart_recovers_gap_between_public_job_and_queue(repo, codec, tmp_path, monkeypatch):
    from app.chat.tasks.task_store import TaskStore
    from app.services.job_store import create_job, JobKind
    from app.services.job_reconciliation_service import JobReconciliationService
    from core.config import Config
    monkeypatch.setenv('JOB_PERSISTENCE_MODE', 'json')
    monkeypatch.setattr(Config, 'STORAGE_ROOT', tmp_path / 'jobs')
    monkeypatch.setattr('app.exam_generation.repository.GenerationRepository', lambda: repo)
    row = create(repo, codec)
    tasks = TaskStore(str(tmp_path / 'tasks.db'))
    job = create_job(edu_job_id=row['id'], owner_user_id='alice', kind=JobKind.GENERATE_EXAM)
    JobReconciliationService(task_store=tasks)._sync_public_ledger([job])
    assert tasks.get_durable(row['id']).command == {'generation_id': row['id']}
    tasks.close()


def test_exam_snapshot_freezes_local_parser_selection(codec, monkeypatch):
    original=codec.resolver.resolve
    codec.resolver.resolve=lambda name,**kw: ({'_source':'environment'} if name=='pdf_parser' else original(name,**kw))
    monkeypatch.setenv('PDF_PARSER_PROVIDER','mineru-local')
    monkeypatch.setenv('PDF_MINERU_LOCAL_BASE_URL','http://127.0.0.1:8190')
    frozen=codec.capture('alice')
    monkeypatch.setenv('PDF_PARSER_PROVIDER','mineru-cloud')
    monkeypatch.setenv('PDF_MINERU_LOCAL_BASE_URL','http://changed.test')
    from app.integrations.pdf.configuration import create_pdf_parser
    parser=create_pdf_parser(codec.read('alice',frozen)['pdf_parser'])
    assert parser.provider_id=='mineru-local' and parser.base_url=='http://127.0.0.1:8190'


def test_history_and_paper_are_owner_scoped_and_hide_all_answer_fields(repo, codec):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import exam_generations as api
    from app.auth import get_current_user
    alice=create(repo,codec);create(repo,codec,'bob')
    repo.claim('alice',alice['id'],1)
    qa={'question_id':'q1','question_type':'short_answer','question':'Question',
        'correct_answer':'PRIVATE_ANSWER','explanation':'PRIVATE_REASON',
        'metadata':{'source':'PRIVATE_SOURCE'},'children':[{'question_id':'c1','question':'Child','correct_answer':'PRIVATE_CHILD'}]}
    repo.event('alice',alice['id'],1,{'seq':1,'type':'result','metadata':{'summary':{'success':True,'completed':1,'failed':0,'results':[{'qa_pair':qa}]}}})
    app=FastAPI();app.include_router(api.router);actor={'username':'alice'}
    app.dependency_overrides[get_current_user]=lambda:actor
    app.dependency_overrides[api.repository]=lambda:repo
    with TestClient(app) as client:
        history=client.get('/api/exam-generations');assert history.status_code==200
        assert [x['generation_id'] for x in history.json()['items']]==[alice['id']]
        response=client.get('/api/exam-generations/'+alice['id']+'/paper')
        assert response.status_code==200 and 'PRIVATE' not in response.text
        assert response.json()['questions'][0]['children'][0]['question']=='Child'
        actor['username']='bob'
        assert client.get('/api/exam-generations/'+alice['id']+'/paper').status_code==404


def test_partial_paper_cannot_be_previewed(repo, codec):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import exam_generations as api
    from app.auth import get_current_user
    row=create(repo,codec);app=FastAPI();app.include_router(api.router)
    app.dependency_overrides[get_current_user]=lambda:{'username':'alice'}
    app.dependency_overrides[api.repository]=lambda:repo
    with TestClient(app) as client:
        assert client.get('/api/exam-generations/'+row['id']+'/paper').status_code==409


def test_event_cursor_does_not_rewrite_large_source_and_rejects_stale_attempt(repo, codec):
    from sqlalchemy import select
    from app.database.session import database_session
    row = create(repo, codec)
    gid = row['id']
    repo.claim('alice', gid, 1)
    repo.update('alice', gid, 1, {'parsed_sources': [{'images': {'scan.png': 'IMAGE' * 100000}}]})
    repo.events_batch('alice', gid, 1, [{'seq': i, 'type': 'thinking'} for i in range(1,1001)])
    with database_session(engine=repo.engine) as session:
        persisted = session.scalar(select(AppStateRecord.payload).where(AppStateRecord.namespace=='exam_generation_v1',AppStateRecord.record_key==gid))
    assert persisted['last_seq'] == 0  # High-frequency cursor is stored separately.
    assert repo.get('alice', gid, include_events=False)['last_seq'] == 1000
    repo.claim('alice', gid, 2)
    with pytest.raises(GenerationConflict):repo.events_batch('alice', gid, 1, [{'seq':1001,'type':'thinking'}])
    assert len(repo.get('alice', gid)['events']) == 1000
    repo.events_batch('alice', gid, 2, [{'seq':1000,'type':'thinking'},{'seq':1001,'type':'done'}])
    assert len(repo.get('alice', gid)['events']) == 1001
    with pytest.raises(GenerationNotFound):repo.events_batch('bob',gid,2,[{'seq':1002,'type':'done'}])


def test_event_cursor_and_insert_rollback_on_changed_blueprint(repo, codec):
    row=create(repo,codec);gid=row['id'];repo.claim('alice',gid,1)
    repo.events_batch('alice',gid,1,[{'seq':1,'type':'progress','metadata':{'exam_blueprint':{'version':1}}}])
    with pytest.raises(GenerationConflict):
        repo.events_batch('alice',gid,1,[{'seq':2,'type':'thinking'},{'seq':3,'type':'progress','metadata':{'exam_blueprint':{'version':2}}}])
    stored=repo.get('alice',gid)
    assert stored['last_seq']==1 and len(stored['events'])==1


def test_streamed_tokens_do_not_poll_control_storage_per_token(repo, codec):
    row=create(repo,codec);calls={'lease':0,'cancel':0}
    class Many(Client):
        async def internal_events(self,**kwargs):
            for i in range(1,2001):yield {'seq':i,'type':'thinking'}
            async for event in super().internal_events(after_seq=0):yield {**event,'seq':event['seq']+2000}
    def lease():calls['lease']+=1;return True
    def cancel():calls['cancel']+=1;return False
    from dataclasses import replace
    ctx=replace(context(row),is_lease_valid=lease,is_cancel_requested=cancel)
    result=asyncio.run(ExamGenerationHandler(repo,GenerationSources(),codec,Many).run({'generation_id':row['id']},ctx))
    assert result['saved'] and len(repo.get('alice',row['id'])['events'])==2002
    assert calls['lease']<100 and calls['cancel']<100
