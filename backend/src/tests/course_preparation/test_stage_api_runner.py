from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api import course_preparations as api
from app.course_preparation.runner import PreparationRunner, StepResult
from app.course_preparation.service import PreparationService
from app.course_preparation.queue_bridge import PreparationQueueBridge
from tests.course_preparation.test_runtime_foundation import repo, request


def test_authenticated_api_events_retry_and_http_independent_worker(runtime_engine):
    repository = repo(runtime_engine)
    app = FastAPI()
    app.include_router(api.router)
    app.state.preparation_service = PreparationService(repository)
    app.dependency_overrides[api.owner] = lambda: 'alice'
    client = TestClient(app)
    result = client.post('/api/course-preparations', json=request().model_dump(mode='json'))
    assert result.status_code == 202
    prep_id = result.json()['preparation_id']
    runner = PreparationRunner(repository, {'normalize': lambda ctx: StepResult(
        {'brief': {'goal': 'interview'}}, 'research_scope', 'no uploads')})
    assert runner.run_step(prep_id, worker_id='background')['stage'] == 'research_scope'
    base = '/api/course-preparations/' + prep_id
    assert client.get(base).json()['stage'] == 'research_scope'
    events = client.get(base + '/events').json()['events']
    assert [e['sequence'] for e in events] == list(range(1, len(events) + 1))
    assert client.get(base + '/events', params={'after': events[-1]['sequence']}).json()['events'] == []
    assert client.post(base + '/cancel', json={}).json()['status'] == 'canceled'
    assert client.post(base + '/retry').json()['attempt_no'] == 2
    app.dependency_overrides[api.owner] = lambda: 'bob'
    assert client.get(base).status_code == 404


def test_waiting_step_releases_execution_slot(runtime_engine):
    repository = repo(runtime_engine)
    value = repository.submit('alice', request())
    runner = PreparationRunner(repository, {'normalize': lambda ctx: StepResult({'waiting_for': 'child'}, wait_seconds=30)})
    assert runner.run_step(value['preparation_id'], worker_id='background')['waiting']
    assert repository.claim('other') is None


def test_queue_reconciliation_replays_stable_ticket_and_foreign_owner_is_rejected(runtime_engine):
    repository = repo(runtime_engine)
    value = repository.submit('alice', request())
    class Queue:
        def __init__(self): self.keys = set()
        def enqueue(self, **kwargs): self.keys.add(kwargs['idempotency_key'])
    queue = Queue()
    bridge = PreparationQueueBridge(repository, queue)
    assert bridge.reconcile() == bridge.reconcile() == 1
    assert len(queue.keys) == 1
    runner = PreparationRunner(repository, {})
    import pytest
    with pytest.raises(LookupError):
        runner.run_step(value['preparation_id'], worker_id='malformed-ticket', expected_owner='bob')


def test_complete_service_disabled_by_default():
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.owner] = lambda: 'alice'
    assert TestClient(app).post('/api/course-preparations', json=request().model_dump(mode='json')).status_code == 503
