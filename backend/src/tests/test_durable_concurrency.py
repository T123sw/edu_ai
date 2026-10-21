"""Verify actual overlap, reserved scheduling capacity and atomic selection."""
import threading
import time
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from app.chat.tasks.postgres_task_store import PostgresTaskStore
from app.chat.tasks.task_store import TaskStore
from app.database.models import DurableTaskModel
from app.services.durable_executor_pool import DurableExecutorPool
from app.services.durable_task_handlers import DurableTaskHandlerRegistry
from app.services.job_completion_service import JobCompletionService
from tests.test_durable_executor_pool import _enqueue, _wait_for_status


@pytest.fixture(params=['sqlite', 'sqlalchemy', 'postgresql'])
def store(request, tmp_path):
    if request.param == 'sqlite':
        value = TaskStore(str(tmp_path / 'tasks.db'))
        yield value
        value.close()
    elif request.param == 'sqlalchemy':
        engine = create_engine('sqlite+pysqlite:///' + str(tmp_path / 'tasks.db'))
        DurableTaskModel.__table__.create(engine)
        yield PostgresTaskStore(engine)
        engine.dispose()
    else:
        url = os.getenv('CONCURRENCY_TEST_DATABASE_URL')
        if not url:
            pytest.skip('Explicit PostgreSQL URL required; all tables use an isolated temporary schema')
        schema = 'concurrency_test_' + uuid4().hex
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
        engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
        try:
            DurableTaskModel.__table__.create(engine)
            yield PostgresTaskStore(engine)
        finally:
            engine.dispose()
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            admin.dispose()


def test_workflow_selection_is_atomic_and_does_not_claim_other_lane(store):
    _enqueue(store, 'generation', 'generate')
    _enqueue(store, 'schedule', 'preparation_step')
    assert store.claim_next(lease_owner='none', lease_seconds=10, workflow_types=()) is None
    control = store.claim_next(lease_owner='control', lease_seconds=10,
                               workflow_types=('preparation_step',))
    assert control.task_id == 'schedule'
    assert store.get_durable('generation').attempt_count == 0
    assert store.claim_next(lease_owner='control2', lease_seconds=10,
                            workflow_types=('preparation_step',)) is None
    job = store.claim_next(lease_owner='generation', lease_seconds=10,
                           excluded_workflow_types=('preparation_step',))
    assert job.task_id == 'generation'
    assert store.claim_next(lease_owner='other', lease_seconds=10) is None


def test_saturated_generation_pool_keeps_scheduler_live_and_jobs_overlap(store, monkeypatch):
    if isinstance(store, PostgresTaskStore) and store._sessions.kw['bind'].dialect.name != 'postgresql':
        pytest.skip('Concurrent SQL row claims require PostgreSQL SKIP LOCKED')
    monkeypatch.setattr('app.services.durable_task_executor.update_job', lambda *a, **k: None)
    monkeypatch.setattr('app.services.job_completion_service.update_job', lambda *a, **k: None)
    registry = DurableTaskHandlerRegistry()
    release = threading.Event()
    all_started = threading.Barrier(4)
    lock = threading.Lock()
    calls = []
    intervals = {}

    def generate(command, context):
        with lock:
            calls.append(context.task_id)
            intervals[context.task_id] = [time.monotonic()]
        context.progress(10, 'working', 'running')
        all_started.wait(timeout=5)
        assert release.wait(timeout=8)
        intervals[context.task_id].append(time.monotonic())
        return {'saved': True, 'result_ref': {'resource_type': 'synthetic'}}

    registry.register('generate', 1, generate)
    registry.register('preparation_step', 1, lambda *args: {'saved': True, 'result_ref': {'resource_type': 'synthetic'}})
    pool = DurableExecutorPool(task_store=store, handler_registry=registry,
        completion_service=JobCompletionService(task_store=store),
        worker_count=3, control_worker_count=1, poll_interval=.01,
        lease_seconds=2, heartbeat_interval=.2)
    for i in range(3):
        _enqueue(store, f'g{i}', 'generate')
    try:
        pool.start()
        all_started.wait(timeout=5)
        _enqueue(store, 'fourth', 'generate')
        _enqueue(store, 'parent', 'preparation_step')
        assert _wait_for_status(store, 'parent', 'succeeded', timeout=3)
        assert store.get_durable('fourth').status == 'pending'
        assert all(store.get_durable(f'g{i}').status == 'leased' for i in range(3))
        store.request_cancel('fourth', owner_user_id='teacher-a')
        release.set()
        for i in range(3):
            assert _wait_for_status(store, f'g{i}', 'succeeded', timeout=3)
        assert sorted(calls) == ['g0', 'g1', 'g2']
        assert max(v[0] for v in intervals.values()) < min(v[1] for v in intervals.values())
    finally:
        release.set()
        pool.stop(timeout_seconds=5)


def test_course_dispatches_four_independent_resources_without_restarting_existing_work(monkeypatch):
    from app.course_preparation.production_stages import ProductionStages
    from app.course_preparation.tool_registry import digest
    monkeypatch.setattr('core.config.Config.COURSE_PREPARATION_RESOURCE_CONCURRENCY', 4)
    specs = [{'title': f'lesson-{i}', 'resource_type':'report', 'node_id':f'n{i}'} for i in range(5)]
    submitted = []
    repo = SimpleNamespace(
        begin_action=lambda *args: {'status': 'pending', 'replay': False, 'action_id': args[1]},
        finish_action=lambda *args: None)
    def submit(context, spec, action):
        submitted.append(spec['title'])
        return {'artifact_id': action}
    stages = ProductionStages(repo, SimpleNamespace(submit=submit,
        read_result=lambda *args: {'status': 'running'}), None)
    checkpoint = {'resource_specs': specs,
                  'generation_receipts': {digest(specs[0]): {'artifact_id': 'existing'}}}
    stages.prepare_specifications = lambda ctx: checkpoint
    result = stages.produce(SimpleNamespace(owner_user_id='owner'))
    assert submitted == ['lesson-1', 'lesson-2', 'lesson-3']
    assert len(result.checkpoint['generation_receipts']) == 4
    assert result.checkpoint['generation_receipts'][digest(specs[0])] == {'artifact_id': 'existing'}


def test_light_lane_skips_waiting_videos_before_atomic_claim(store):
    for task_id, kind in [('video','classroom'), ('report','report'), ('quiz','quiz')]:
        store.enqueue(task_id=task_id, workflow_type='preparation_resource', handler_version=1,
            owner_user_id='teacher-a', course_id=None, scope_type='preparation', scope_id='p',
            command={'artifact_id':task_id, 'resource_type':kind}, config_snapshot_id=None,
            idempotency_key=task_id)
    store.enqueue(task_id='exam-help', workflow_type='exam_practice', handler_version=1,
        owner_user_id='teacher-a', course_id=None, scope_type='exam_generation', scope_id='paper',
        command={'operation':'chat'}, config_snapshot_id=None, idempotency_key='exam-help')
    for expected in ('report','quiz','exam-help'):
        task = store.claim_next(lease_owner='light', lease_seconds=10, light_resources_only=True)
        assert task.task_id == expected
    assert store.claim_next(lease_owner='light', lease_seconds=10, light_resources_only=True) is None
    assert store.get_durable('video').attempt_count == 0
    assert store.claim_next(lease_owner='general', lease_seconds=10).task_id == 'video'


def test_report_finishes_while_general_worker_is_busy_with_video(store, monkeypatch):
    if isinstance(store, PostgresTaskStore) and store._sessions.kw['bind'].dialect.name != 'postgresql':
        pytest.skip('Concurrent claims require PostgreSQL SKIP LOCKED')
    monkeypatch.setattr('app.services.durable_task_executor.update_job', lambda *a, **k:None)
    monkeypatch.setattr('app.services.job_completion_service.update_job', lambda *a, **k:None)
    started, release = threading.Event(), threading.Event()
    registry = DurableTaskHandlerRegistry()
    def handler(command, context):
        if command['resource_type'] == 'classroom':
            started.set()
            assert release.wait(8)
        return {'saved':True, 'result_ref':{'resource_type':'synthetic'}}
    registry.register('preparation_resource', 1, handler)
    def enqueue(key, kind):
        store.enqueue(task_id=key, workflow_type='preparation_resource', handler_version=1,
            owner_user_id='teacher-a', course_id=None, scope_type='preparation', scope_id='p',
            command={'resource_type':kind}, config_snapshot_id=None, idempotency_key=key)
    pool = DurableExecutorPool(task_store=store, handler_registry=registry,
        completion_service=JobCompletionService(task_store=store), worker_count=1,
        light_worker_count=1, poll_interval=.01, lease_seconds=2, heartbeat_interval=.2)
    enqueue('video','classroom')
    try:
        pool.start()
        assert started.wait(5)
        enqueue('report','report')
        assert _wait_for_status(store, 'report', 'succeeded', timeout=3)
        assert store.get_durable('video').status == 'leased'
    finally:
        release.set(); pool.stop(timeout_seconds=5)
