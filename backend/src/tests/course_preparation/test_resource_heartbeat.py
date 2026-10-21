from datetime import timedelta
from threading import Event
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.database.models import PreparationArtifact
from app.course_preparation.lifecycle_repository import StaleLease
from app.course_preparation.repository import aware
from app.course_preparation.resource_heartbeat import ResourceHeartbeat
from tests.course_preparation.test_generation_adapter import generation, submit


def test_long_blocking_work_renews_and_stops_without_checkpoint_calls():
    calls = []
    renewed = Event()
    def heartbeat(artifact):
        calls.append(artifact)
        if len(calls) >= 3:
            renewed.set()
    worker = ResourceHeartbeat(SimpleNamespace(heartbeat=heartbeat), {'artifact_id': 'a'},
        SimpleNamespace(is_cancel_requested=lambda: False, is_lease_valid=lambda: True), interval=.01)
    worker.start()
    try:
        assert renewed.wait(2)
        worker.check()
    finally:
        worker.close()
    assert not worker.thread.is_alive()


@pytest.mark.parametrize('canceled,valid', [(True, True), (False, False)])
def test_stopped_execution_cannot_renew(canceled, valid):
    calls = []
    worker = ResourceHeartbeat(SimpleNamespace(heartbeat=lambda a: calls.append(a)), {},
        SimpleNamespace(is_cancel_requested=lambda: canceled, is_lease_valid=lambda: valid))
    with pytest.raises(StaleLease):
        worker.start()
    assert calls == []


def test_heartbeat_failure_is_returned_to_generation():
    called = Event()
    calls = []
    def heartbeat(artifact):
        calls.append(artifact)
        if len(calls) > 1:
            called.set()
            raise StaleLease('lost')
    worker = ResourceHeartbeat(SimpleNamespace(heartbeat=heartbeat), {},
        SimpleNamespace(is_cancel_requested=lambda: False), interval=.01)
    worker.start()
    assert called.wait(2)
    worker.close()
    with pytest.raises(StaleLease, match='lost'):
        worker.check()


def test_database_renewal_preserves_expiry_and_parent_fencing(generation):
    repo, parent, adapter = generation
    _, receipt = submit(generation)
    store = adapter.artifacts
    child = store.claim('alice', receipt['artifact_id'])
    initial = repo.clock()
    repo.clock = lambda: initial + timedelta(seconds=150)
    store.heartbeat(child)
    with Session(repo.engine) as session:
        until = aware(session.get(PreparationArtifact, child['artifact_id']).lease_until)
    assert until == repo.clock() + timedelta(seconds=180)
    with pytest.raises(StaleLease):
        store.heartbeat({**child, 'lease_token': 'another-worker'})
    repo.clock = lambda: until + timedelta(seconds=1)
    with pytest.raises(StaleLease):
        store.heartbeat(child)
