from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.database.models import CourseResearchRunRecord as Run, User
from app.database import Base
from app.course_preparation.research_repository import ResearchRepository, LostResearchLease
from app.course_preparation.research_runtime import ResearchRuntime
from app.course_preparation.research_agent import ResearchAgent
from app.course_preparation.contracts import IdempotencyConflict, PreparationNotFound
from tests.course_preparation.test_research_flow import request, Model, Sources


def test_durable_complete_and_owner_isolation(db_engine):
    repo = ResearchRepository(db_engine)
    req = request()
    accepted = repo.submit('alice', req)
    assert accepted == repo.submit('alice', req)
    with pytest.raises(IdempotencyConflict):
        repo.submit('alice', req.model_copy(update={'goal': '不同需求'}))
    with pytest.raises(PreparationNotFound):
        repo.get('bob', accepted['run_id'])
    with pytest.raises(PreparationNotFound):
        repo.get('bob', accepted['run_id'], cancel=True)
    runtime = ResearchRuntime(repo, lambda *_: ResearchAgent(model=Model(), sources=Sources()))
    assert runtime.run_once()
    value = repo.get('alice', accepted['run_id'])
    assert value['status'] == 'succeeded' and value['course_ready'] is False
    assert value['result']['learning_path']['nodes'][0]['node_id'].startswith('pathnode_')
    assert value['result']['sources'][0]['url'] == 'https://example.edu/recursion'
    assert 'content' not in value['result']['sources'][0]
    assert repo.get('alice', accepted['run_id']) == value
    assert not runtime.run_once()


def test_cancel_fences_active_worker(db_engine):
    repo = ResearchRepository(db_engine)
    run = repo.submit('alice', request())
    claim = repo.claim()
    assert repo.get('alice', run['run_id'], cancel=True)['status'] == 'canceled'
    with pytest.raises(LostResearchLease):
        repo.save(claim, claim['state'])
    assert not repo.claim()


def test_restart_recovers_checkpoint_and_fences_previous_lease(db_engine):
    now = [datetime.now(timezone.utc)]
    repo = ResearchRepository(db_engine, clock=lambda: now[0])
    run = repo.submit('alice', request())
    claim = repo.claim()
    agent = ResearchAgent(model=Model(), sources=Sources())
    state = agent.step(claim['request'], claim['state'])
    repo.save(claim, state)
    assert repo.claim() is None
    now[0] += timedelta(seconds=151)
    restored = repo.claim()
    assert restored['state'].brief == state.brief
    assert restored['state'].calls == 1
    with pytest.raises(LostResearchLease):
        repo.save(claim, state)
    repo.save(restored, state)
    now[0] += timedelta(seconds=500)
    assert repo.claim() is None
    assert repo.get('alice', run['run_id'])['status'] == 'failed'


def test_disabled_owner_cannot_publish_or_read(db_engine):
    repo = ResearchRepository(db_engine)
    run = repo.submit('alice', request())
    claim = repo.claim()
    with Session(db_engine) as session, session.begin():
        session.get(User, 'alice').is_disabled = True
    assert repo.save(claim, claim['state']) == 'failed'
    with pytest.raises(PreparationNotFound):
        repo.get('alice', run['run_id'])


def test_failed_provider_preserves_spent_budget(db_engine):
    from app.course_preparation.research_agent import ResearchError
    class Broken(Model):
        def decide(self, *args, **kwargs):
            raise ResearchError('PROVIDER_UNAVAILABLE', 'test')
    repo = ResearchRepository(db_engine)
    run = repo.submit('alice', request())
    ResearchRuntime(repo, lambda *_: ResearchAgent(model=Broken(), sources=Sources())).run_once()
    value = repo.get('alice', run['run_id'])
    assert value['status'] == 'failed' and value['progress']['model_calls'] == 1
    assert value['result'] is None and value['error_code'] == 'PROVIDER_UNAVAILABLE'


def test_postgres_concurrent_intake_and_claim(db_engine):
    if db_engine.dialect.name != 'postgresql':
        pytest.skip('row-lock race requires PostgreSQL')
    repo, req, barrier = ResearchRepository(db_engine), request(), Barrier(2)
    def submit(_):
        barrier.wait()
        return repo.submit('alice', req)['run_id']
    with ThreadPoolExecutor(2) as pool:
        ids = list(pool.map(submit, range(2)))
    assert ids[0] == ids[1]
    def claim(_):
        barrier.wait()
        return repo.claim()
    with ThreadPoolExecutor(2) as pool:
        claims = list(pool.map(claim, range(2)))
    assert sum(c is not None for c in claims) == 1


def test_research_migration_roundtrip(db_engine):
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/20260917_0025_course_research_runs.py'
    spec = importlib.util.spec_from_file_location('research_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with db_engine.begin() as connection:
        Run.__table__.drop(connection)
        with Operations.context(MigrationContext.configure(connection, opts={'target_metadata': Base.metadata})):
            module.upgrade()
        inspector = inspect(connection)
        assert set(c['name'] for c in inspector.get_columns('course_research_runs')) == set(Run.__table__.columns.keys())
        assert {c['name'] for c in inspector.get_check_constraints('course_research_runs')} == {c.name for c in Run.__table__.constraints if c.__class__.__name__ == 'CheckConstraint'}
    repo = ResearchRepository(db_engine)
    assert repo.submit('alice', request())['status'] == 'queued'
    with db_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection, opts={'target_metadata': Base.metadata})):
            module.downgrade()
        assert 'course_research_runs' not in inspect(connection).get_table_names()


def test_cancel_during_model_response_prevents_followup_search(db_engine):
    from threading import Event, Thread
    entered, release = Event(), Event()
    sources = Sources()
    class Paused(Model):
        def decide(self, *args, **kwargs):
            entered.set()
            assert release.wait(5)
            return super().decide(*args, **kwargs)
    repo = ResearchRepository(db_engine)
    run = repo.submit('alice', request())
    runtime = ResearchRuntime(repo, lambda *_: ResearchAgent(model=Paused(), sources=sources))
    worker = Thread(target=runtime.run_once)
    worker.start()
    try:
        assert entered.wait(5)
        repo.get('alice', run['run_id'], cancel=True)
    finally:
        release.set()
        worker.join(timeout=5)
    assert not worker.is_alive()
    value = repo.get('alice', run['run_id'])
    assert value['status'] == 'canceled' and value['result'] is None
    assert not sources.searches
