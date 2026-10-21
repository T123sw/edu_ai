import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import course_preparations as api
from app.database import Base
from app.database.models import DurableTaskModel
from app.chat.tasks.postgres_task_store import PostgresTaskStore
from app.course_preparation.cancellation import cancel_preparation_tasks
from app.course_preparation.lifecycle_repository import RevisionConflict
from app.course_preparation.service import PreparationService
from tests.course_preparation.test_runtime_foundation import repo, request
from tests.course_preparation.test_generation_adapter import generation, submit


@pytest.fixture
def queued(runtime_engine):
    Base.metadata.create_all(runtime_engine, tables=[DurableTaskModel.__table__])
    repository = repo(runtime_engine)
    repository.cancel_tasks = cancel_preparation_tasks
    task = repository.submit('alice', request())
    context = repository.claim('parent', preparation_id=task['preparation_id'])
    queue = PostgresTaskStore(runtime_engine)
    def enqueue(task_id, *, owner='alice', scope=None, workflow='preparation_resource'):
        return queue.enqueue(task_id=task_id, workflow_type=workflow, handler_version=1,
            owner_user_id=owner, course_id=None, scope_type='preparation',
            scope_id=scope or task['preparation_id'], command={}, config_snapshot_id=None,
            idempotency_key=task_id, max_attempts=1)
    return repository, context, queue, enqueue


def test_cancel_signals_running_and_queued_children_but_preserves_other_work(queued):
    repository, context, queue, enqueue = queued
    enqueue('running')
    running = queue.claim_next(lease_owner='worker', lease_seconds=180)
    assert running.task_id == 'running'
    enqueue('pending')
    enqueue('control', workflow='preparation_step')
    enqueue('completed')
    enqueue('other-course', scope='another-preparation')
    enqueue('other-owner', owner='bob')
    with Session(repository.engine) as session, session.begin():
        session.get(DurableTaskModel, 'completed').status = 'succeeded'
    result = repository.cancel('alice', context.preparation_id, expected_attempt_no=1)
    assert result['status'] == 'canceled'
    assert queue.is_cancel_requested('running')
    assert queue.get_durable('running').status == 'leased'
    assert queue.get_durable('pending').status == 'canceled'
    assert queue.get_durable('control').status == 'canceled'
    for key in ('completed', 'other-course', 'other-owner'):
        assert not queue.is_cancel_requested(key)
    assert queue.get_durable('completed').status == 'succeeded'
    assert queue.mark_canceled('running', lease_owner='worker')
    assert repository.cancel('alice', context.preparation_id, expected_attempt_no=1)['revision'] == result['revision']


def test_http_cancel_tolerates_progress_but_rejects_old_attempt(queued):
    repository, context, queue, enqueue = queued
    enqueue('child')
    old = repository.get_public('alice', context.preparation_id)
    repository.checkpoint(context, {'brief': {'goal': 'test'}})
    repository.transition(context, 'research_scope', reason='NO_UPLOADS')
    with pytest.raises(RevisionConflict):
        repository.cancel('alice', context.preparation_id, expected_revision=old['revision'])
    app = FastAPI(); app.include_router(api.router)
    app.state.preparation_service = PreparationService(repository)
    app.dependency_overrides[api.owner] = lambda: 'alice'
    client = TestClient(app)
    url = f'/api/course-preparations/{context.preparation_id}/cancel'
    response = client.post(url, json={'expected_attempt_no': old['attempt_no']})
    assert response.status_code == 200 and response.json()['status'] == 'canceled'
    assert queue.get_durable('child').status == 'canceled'
    repository.retry('alice', context.preparation_id)
    assert client.post(url, json={'expected_attempt_no': 1}).status_code == 409
    assert repository.get_public('alice', context.preparation_id)['status'] == 'accepted'
    app.dependency_overrides[api.owner] = lambda: 'bob'
    assert client.post(url, json={'expected_attempt_no': 2}).status_code == 404


def test_cancel_rolls_back_parent_and_queue_together_on_error(queued):
    repository, context, queue, enqueue = queued
    enqueue('pending')
    def broken(*args):
        cancel_preparation_tasks(*args)
        raise RuntimeError('database failure')
    repository.cancel_tasks = broken
    with pytest.raises(RuntimeError, match='database failure'):
        repository.cancel('alice', context.preparation_id, expected_attempt_no=1)
    assert repository.get_public('alice', context.preparation_id)['status'] == 'running'
    assert not queue.is_cancel_requested('pending')
    assert queue.get_durable('pending').status == 'pending'


def test_cancel_between_artifact_creation_and_enqueue_stops_late_job(generation):
    repository, context, adapter = generation
    original = adapter.task_store.enqueue
    def late_enqueue(**kwargs):
        repository.cancel('alice', context.preparation_id)
        return original(**kwargs)
    adapter.task_store.enqueue = late_enqueue
    _, receipt = submit(generation)
    assert adapter.task_store.get_durable(receipt['job_id']).status == 'canceled'
    assert adapter.task_store.is_cancel_requested(receipt['job_id'])
