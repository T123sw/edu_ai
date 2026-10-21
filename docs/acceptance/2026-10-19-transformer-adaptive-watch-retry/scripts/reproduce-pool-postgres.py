"""Reproduce the exact pool/row-lock cycle in a private PostgreSQL cluster."""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

sys.path.insert(0, sys.argv[1])
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.database import Base, User
from app.chat.memory.lifecycle import lock_epoch
from app.course_preparation.authorizer import PreparationReferenceAuthorizer
from app.course_preparation.lifecycle_repository import LifecycleRepository
from app.course_preparation.schemas import PreparationRequest

root = Path(__file__).resolve().parents[1]
config = json.loads((root / 'isolated-postgres.json').read_text())
assert config['production_database_used'] is False and '/tmp/edu-pool-pg-' in config['database_url']
admin = create_engine(config['database_url'])
schema = 'pool_test_' + uuid4().hex
name = schema
with admin.begin() as connection:
    connection.execute(text(f'CREATE SCHEMA {schema}'))
engine = create_engine(config['database_url'], pool_size=3, max_overflow=0, pool_timeout=0.5,
    connect_args={'options': f'-csearch_path={schema} -cstatement_timeout=5000', 'application_name': name})
Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in ('users', 'agent_memory_epochs')])
with Session(engine) as session, session.begin():
    session.add(User(user_id='alice', username='alice', password_hash='test-only', role='student'))
    lock_epoch(session, 'alice')
repo = LifecycleRepository(engine, authorizer=PreparationReferenceAuthorizer(engine, None))
request = PreparationRequest(request_id=uuid4(), operation='create_course', goal='isolated lock validation')
locked, release = Event(), Event()
result = {'source': sys.argv[1], 'production_database_used': False, 'pool_capacity': 3}


def holder():
    try:
        with Session(engine) as session, session.begin():
            lock_epoch(session, 'alice')
            locked.set()
            if not release.wait(5):
                raise RuntimeError('test coordination timeout')
            if hasattr(repo, '_authorize'):
                repo._authorize(session, 'alice', request)
            else:
                repo.authorizer.authorize('alice', request)
        return {'status': 'succeeded'}
    except Exception as exc:
        return {'status': 'failed', 'error': type(exc).__name__, 'message': str(exc)}


def waiter():
    if not locked.wait(5):
        raise RuntimeError('holder did not acquire row lock')
    with Session(engine) as session, session.begin():
        lock_epoch(session, 'alice')
    return 'succeeded'


started = time.monotonic()
try:
    with ThreadPoolExecutor(max_workers=3) as pool:
        h = pool.submit(holder)
        waits = [pool.submit(waiter) for _ in range(2)]
        deadline = time.monotonic() + 4
        blocked = 0
        while time.monotonic() < deadline:
            with admin.connect() as connection:
                blocked = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:name AND wait_event_type='Lock'"), {'name': name})
            if blocked == 2:
                break
            time.sleep(.01)
        result['blocked_waiters_before_authorization'] = blocked
        result['checked_out_before_authorization'] = engine.pool.checkedout()
        release.set()
        result['holder'] = h.result(timeout=6)
        result['waiters'] = [f.result(timeout=6) for f in waits]
    result['seconds'] = time.monotonic()-started
    result['checked_out_after'] = engine.pool.checkedout()
finally:
    engine.dispose()
    with admin.begin() as connection:
        connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
    admin.dispose()
assert result['blocked_waiters_before_authorization'] == 2
assert result['checked_out_before_authorization'] == 3
assert result['checked_out_after'] == 0
(root / sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False))
