from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import Base
from app.self_learning.progress_contracts import LearningEvent
from app.self_learning.progress_repository import ProgressRepository, ProgressConflict, TABLES
from app.self_learning.db_models import LearningEventRecord, LearningProgressOutbox
from tests.self_learning.test_session_repository import repository


@pytest.fixture
def progress(repository):
    Base.metadata.create_all(repository.engine, tables=[Base.metadata.tables[n] for n in TABLES])
    return ProgressRepository(repository.engine)


def event(kind='resource_completion_set', version=1, revision=0, **payload):
    return LearningEvent(event_id=uuid4(), type=kind, occurred_at=datetime.now(timezone.utc),
        resource_ref=None if kind == 'self_assessment_set' else dict(course_id='course', material_type='report', material_id='doc', version=version),
        expected_revision=revision if kind in {'resource_completion_set', 'self_assessment_set'} else None,
        payload=payload or {'completed': True})


def test_replay_conflict_undo_version_and_user(progress):
    e = event()
    first = progress.record('alice', 'course', 'a', e)
    assert progress.record('alice', 'course', 'a', e) == first
    with pytest.raises(ProgressConflict):
        progress.record('alice', 'course', 'a', e.model_copy(update={'payload': {'completed': False}}))
    with pytest.raises(ProgressConflict):
        progress.record('alice', 'course', 'a', event())
    progress.record('alice', 'course', 'a', event(revision=1, completed=False))
    progress.record('alice', 'course', 'a', event(version=2))
    snapshot = progress.read('alice', 'course')
    states = {s['resource_ref']['version']: s for s in snapshot['resources']}
    assert not states[1]['completed'] and states[2]['completed']
    assert snapshot['facts_revision'] == 3
    assert progress.read('bob', 'course')['resources'] == []


def test_reading_sequence_can_move_back_without_completion(progress):
    stream = str(uuid4())
    def position(seq, offset):
        return event('reading_position_set', stream_id=stream, sequence=seq, locator={'kind': 'document', 'scroll_top': offset})
    progress.record('alice', 'course', 'a', position(2, 200))
    stale = progress.record('alice', 'course', 'a', position(1, 400))
    assert not stale['applied'] and stale['reason'] == 'stale_position'
    progress.record('alice', 'course', 'a', position(3, 10))
    progress.record('alice', 'course', 'a', event('resource_end_reached', locator={'kind': 'document', 'scroll_top': 900}))
    state = progress.read('alice', 'course')['resources'][0]
    assert state['locator']['scroll_top'] == 10 and state['reached_end'] and not state['completed']


def test_self_assessment_revision_is_independent(progress):
    progress.record('alice', 'course', 'a', event())
    progress.record('alice', 'course', 'a', event('self_assessment_set', value='understood'))
    with pytest.raises(ProgressConflict):
        progress.record('alice', 'course', 'a', event('self_assessment_set', value='needs_review'))
    progress.record('alice', 'course', 'a', event('self_assessment_set', revision=1, value='unset'))
    assert progress.read('alice', 'course')['self_assessments'] == {'a': 'unset'}


def test_concurrent_replay_is_once_and_rollback_is_atomic(progress):
    e = event()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: progress.record('alice', 'course', 'a', e), range(6)))
    assert all(r == results[0] for r in results)
    with Session(progress.engine) as db:
        assert db.scalar(select(func.count()).select_from(LearningEventRecord)) == 1
        assert db.scalar(select(func.count()).select_from(LearningProgressOutbox)) == 1
    def failed(_):
        raise RuntimeError('projection failure')
    with pytest.raises(RuntimeError):
        progress.record('alice', 'course', 'a', event(revision=1, completed=False), failed)
    assert progress.read('alice', 'course')['facts_revision'] == 1
    assert progress.read('alice', 'course')['resources'][0]['completed']


def test_strict_event_rejects_bad_payload():
    from pydantic import ValidationError
    for value in [dict(completed='true'), dict(completed=True, mastery=True)]:
        with pytest.raises(ValidationError):
            event(**value)
    with pytest.raises(ValidationError):
        event('reading_position_set', stream_id=str(uuid4()), sequence=0, locator={'kind': 'document'})
