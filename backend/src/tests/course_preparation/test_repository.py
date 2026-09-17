from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.course_preparation.contracts import IdempotencyConflict, PreparationNotFound
from app.course_preparation.repository import PreparationRepository
from app.course_preparation.schemas import PreparationRequest
from app.database import CoursePreparationRecord, CoursePreparationAttemptRecord, CoursePreparationEventRecord


class Authorizer:
    def __init__(self):
        self.denied = False
        self.calls = []

    def authorize(self, owner_user_id, request):
        self.calls.append((owner_user_id, request))
        if self.denied:
            raise PermissionError('revoked')


@pytest.fixture
def authorizer():
    return Authorizer()


@pytest.fixture
def repo(db_engine, authorizer):
    return PreparationRepository(db_engine, authorizer=authorizer)


def request(**changes):
    return PreparationRequest.model_validate({
        'request_id': str(uuid4()), 'operation': 'create_course', 'goal': '学习递归', **changes,
    })


def counts(engine):
    with Session(engine) as session:
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in (
            CoursePreparationRecord, CoursePreparationAttemptRecord, CoursePreparationEventRecord,
        ))


def test_idempotency_and_restart(repo, db_engine, authorizer):
    payload = request()
    first = repo.accept(owner_user_id='alice', request=payload)
    again = repo.accept(owner_user_id='alice', request=payload)
    assert first == again
    db_engine.dispose()  # Reopen real connections; state must not live in a process-local dictionary.
    restarted = PreparationRepository(db_engine, authorizer=authorizer)
    assert restarted.get(owner_user_id='alice', preparation_id=first.preparation_id) == first
    assert first.status == 'accepted'
    assert first.attempt_no == first.revision == 1
    events = repo.events(owner_user_id='alice', preparation_id=first.preparation_id)
    assert len(events) == 1 and events[0].type == 'accepted'
    assert events[0].attempt_no == 1
    assert repo.events(owner_user_id='alice', preparation_id=first.preparation_id, after=1) == []
    assert counts(db_engine) == (1, 1, 1)


def test_idempotency_conflict_and_owner_isolation(repo, db_engine):
    payload = request()
    first = repo.accept(owner_user_id='alice', request=payload)
    changed = request(**{**payload.model_dump(mode='json'), 'goal': '改学图论'})
    with pytest.raises(IdempotencyConflict):
        repo.accept(owner_user_id='alice', request=changed)
    second = repo.accept(owner_user_id='bob', request=payload)
    assert first.preparation_id != second.preparation_id
    for method in (repo.get, repo.events):
        with pytest.raises(PreparationNotFound):
            method(owner_user_id='bob', preparation_id=first.preparation_id)
    assert counts(db_engine) == (2, 2, 2)


def test_revoked_access_rejects_replay_and_reads(repo, authorizer, db_engine):
    payload = request()
    first = repo.accept(owner_user_id='alice', request=payload)
    authorizer.denied = True
    with pytest.raises(PermissionError):
        repo.accept(owner_user_id='alice', request=payload)
    with pytest.raises(PermissionError):
        repo.get(owner_user_id='alice', preparation_id=first.preparation_id)
    with pytest.raises(PermissionError):
        repo.events(owner_user_id='alice', preparation_id=first.preparation_id)
    assert counts(db_engine) == (1, 1, 1)


def test_denied_accept_has_no_side_effect(repo, authorizer, db_engine):
    authorizer.denied = True
    with pytest.raises(PermissionError):
        repo.accept(owner_user_id='alice', request=request())
    assert counts(db_engine) == (0, 0, 0)


def test_failure_writing_event_rolls_back_entire_accept(repo, db_engine):
    def fail_event(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('INSERT INTO COURSE_PREPARATION_EVENTS'):
            raise RuntimeError('simulated event storage failure')

    event.listen(db_engine, 'before_cursor_execute', fail_event)
    try:
        with pytest.raises(RuntimeError, match='simulated'):
            repo.accept(owner_user_id='alice', request=request())
    finally:
        event.remove(db_engine, 'before_cursor_execute', fail_event)
    assert counts(db_engine) == (0, 0, 0)


def test_concurrent_accept_creates_one_task(repo, db_engine, monkeypatch):
    if db_engine.dialect.name != 'postgresql':
        pytest.skip('row/unique-conflict concurrency is verified on PostgreSQL')
    payload = request()
    barrier = Barrier(6)
    original = repo._request_record

    def race_first_lookup(*args):
        result = original(*args)
        if result is None:
            barrier.wait(timeout=15)
        return result

    monkeypatch.setattr(repo, '_request_record', race_first_lookup)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: repo.accept(owner_user_id='alice', request=payload), range(6)))
    assert len({r.preparation_id for r in results}) == 1
    assert counts(db_engine) == (1, 1, 1)


@pytest.mark.parametrize('after,limit', [(-1, 100), (0, 0), (0, 501)])
def test_invalid_event_pagination(repo, after, limit):
    first = repo.accept(owner_user_id='alice', request=request())
    with pytest.raises(ValueError):
        repo.events(owner_user_id='alice', preparation_id=first.preparation_id, after=after, limit=limit)


def test_unknown_database_owner_is_not_swallowed_as_idempotency(repo, db_engine):
    with pytest.raises(IntegrityError):
        repo.accept(owner_user_id='missing-user', request=request())
    assert counts(db_engine) == (0, 0, 0)


def test_database_rejects_invalid_state_and_event_attempt(repo, db_engine):
    first = repo.accept(owner_user_id='alice', request=request())
    with pytest.raises(IntegrityError), Session(db_engine) as session, session.begin():
        attempt = session.get(CoursePreparationAttemptRecord, (first.preparation_id, 1))
        attempt.status = 'waiting_for_user'
    with pytest.raises(IntegrityError), Session(db_engine) as session, session.begin():
        session.add(CoursePreparationEventRecord(
            event_id='bad-event', preparation_id=first.preparation_id, attempt_no=99,
            sequence=2, event_type='stage_changed', revision=1, payload={}, occurred_at=first.created_at,
        ))
    assert repo.get(owner_user_id='alice', preparation_id=first.preparation_id).status == 'accepted'
    assert counts(db_engine) == (1, 1, 1)


def test_events_retain_origin_and_page_in_sequence_order(repo, db_engine):
    first = repo.accept(owner_user_id='alice', request=request(origin={
        'conversation_id': 'conversation-1', 'message_id': 'message-1',
    }))
    with Session(db_engine) as session, session.begin():
        for sequence in (3, 2):
            session.add(CoursePreparationEventRecord(
                event_id=f'event-{sequence}', preparation_id=first.preparation_id,
                attempt_no=1, sequence=sequence, event_type='stage_changed', revision=sequence,
                payload={'stage': 'ingest'}, occurred_at=first.created_at,
            ))
    page = repo.events(owner_user_id='alice', preparation_id=first.preparation_id, after=1, limit=1)
    assert [item.sequence for item in page] == [2]
    assert page[0].origin_ref == first.request.origin
    next_page = repo.events(owner_user_id='alice', preparation_id=first.preparation_id, after=2)
    assert [item.sequence for item in next_page] == [3]
