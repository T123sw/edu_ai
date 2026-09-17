from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from app.database import Base
from app.self_learning.postgres_repository import SessionRepository, SessionConflict, SessionMissing


@pytest.fixture(params=['sqlite', 'postgresql'])
def repository(request, tmp_path):
    admin = None
    if request.param == 'postgresql':
        url = os.getenv('LEARNING_TEST_DATABASE_URL')
        if not url:
            pytest.skip('isolated LEARNING_TEST_DATABASE_URL required')
        schema = 'learning_test_' + uuid4().hex
        admin = create_engine(url)
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA {schema}'))
        engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    else:
        engine = create_engine(f'sqlite:///{tmp_path / "sessions.db"}')
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in (
        'conversations', 'conversation_messages', 'learning_topic_sessions', 'learning_agent_turns')])
    yield SessionRepository(engine)
    engine.dispose()
    if admin is not None:
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


def enter(repo, owner='alice', topic='a', legacy=None):
    return repo.ensure_session(owner, 'course', topic, '导学', legacy or [])


def test_enter_idempotent_and_owner_isolated(repository):
    first = enter(repository)
    assert enter(repository)['session_id'] == first['session_id']
    assert enter(repository, 'bob')['session_id'] != first['session_id']
    assert enter(repository, topic='b')['session_id'] != first['session_id']
    assert len(repository.messages('alice', first['session_id'])['items']) == 1
    with pytest.raises(SessionMissing):
        repository.messages('bob', first['session_id'])


def test_full_history_pagination_import_and_restart(repository):
    turns = [dict(turn_id=f'old{i}', client_turn_id=f'req{i}', question=f'q{i}', answer_text=f'a{i}', resource_id='res') for i in range(150)]
    sid = enter(repository, legacy=turns)['session_id']
    enter(repository, legacy=turns)
    restarted = SessionRepository(repository.engine)
    items, cursor = [], None
    while True:
        page = restarted.messages('alice', sid, before=cursor, limit=37)
        items = page['items'] + items
        cursor = page['next_cursor']
        if not cursor:
            break
    assert len(items) == 301
    assert len({m['id'] for m in items}) == 301
    assert [m['position'] for m in items] == list(range(301))
    assert items[1]['text'] == 'q0' and items[-1]['text'] == 'a149'
    other = enter(repository, topic='b')['session_id']
    cursor = repository.messages('alice', sid, limit=2)['next_cursor']
    with pytest.raises(ValueError):
        repository.messages('alice', other, before=cursor)


def test_turn_retry_conflict_and_fencing(repository):
    sid = enter(repository)['session_id']
    first = repository.begin_turn('alice', sid, 'r1', 'question', 'res', now=100)
    with pytest.raises(SessionConflict):
        repository.begin_turn('alice', sid, 'r1', 'changed', 'res', now=101)
    with pytest.raises(SessionConflict):
        repository.begin_turn('alice', sid, 'r2', 'another', 'res', now=101)
    resumed = repository.begin_turn('alice', sid, 'r1', 'question', 'res', now=500)
    assert not repository.finish_turn('alice', sid, 'r1', first['token'], answer='late')
    assert repository.finish_turn('alice', sid, 'r1', resumed['token'], error='unavailable', now=500)
    retry = repository.begin_turn('alice', sid, 'r1', 'question', 'res', now=501)
    assert repository.finish_turn('alice', sid, 'r1', retry['token'], answer='saved', now=501)
    assert repository.begin_turn('alice', sid, 'r1', 'question', 'res')['status'] == 'succeeded'
    page = repository.messages('alice', sid)
    assert [m['text'] for m in page['items']] == ['导学', 'question', 'saved']


def test_concurrent_enter_and_turn_claim(repository):
    with ThreadPoolExecutor(max_workers=6) as pool:
        sessions = list(pool.map(lambda _: enter(repository), range(6)))
    assert len({s['session_id'] for s in sessions}) == 1
    sid = sessions[0]['session_id']
    def claim(i):
        try:
            return repository.begin_turn('alice', sid, f'req-{i}', 'q', 'r')
        except SessionConflict:
            return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        claims = list(pool.map(claim, range(6)))
    assert sum(c is not None for c in claims) == 1
    assert len(repository.messages('alice', sid)['items']) == 2


def test_failed_import_rolls_back_session_and_messages(repository, monkeypatch):
    original = repository._append
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('injected write failure')
    monkeypatch.setattr(repository, '_append', fail)
    with pytest.raises(RuntimeError):
        enter(repository)
    assert repository.find('alice', 'course', 'a') is None
    monkeypatch.setattr(repository, '_append', original)
    assert enter(repository)['message_count'] == 1


def test_legacy_conversation_writer_cannot_replace_learning_history(repository):
    from app.persistence.postgres_conversation_repository import PostgresConversationRepository
    sid = enter(repository)['session_id']
    with pytest.raises(ValueError, match='append-only'):
        PostgresConversationRepository(repository.engine).upsert({
            'conversation_id': sid, 'owner': 'alice', 'messages': []})
    assert repository.messages('alice', sid)['message_count'] == 1


def test_appending_more_than_100_turns_never_truncates(repository):
    sid = enter(repository)['session_id']
    for i in range(105):
        claim = repository.begin_turn('alice', sid, str(i), f'q{i}', 'res')
        assert repository.finish_turn('alice', sid, str(i), claim['token'], answer=f'a{i}')
    page = repository.messages('alice', sid, limit=100)
    assert page['message_count'] == 211
    while page['next_cursor']:
        page = repository.messages('alice', sid, page['next_cursor'], limit=100)
    assert page['items'][0]['kind'] == 'introduction'
    assert page['items'][1]['text'] == 'q0'


def _process_enter(url, schema):
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        return enter(SessionRepository(engine))['session_id']
    finally:
        engine.dispose()


def test_postgres_separate_workers(repository):
    if repository.engine.dialect.name != 'postgresql':
        pytest.skip('PostgreSQL process isolation test')
    from concurrent.futures import ProcessPoolExecutor
    from multiprocessing import get_context
    with repository.engine.connect() as connection:
        schema = connection.scalar(text('SELECT current_schema()'))
    with ProcessPoolExecutor(max_workers=4, mp_context=get_context('spawn')) as pool:
        futures = [pool.submit(_process_enter, os.environ['LEARNING_TEST_DATABASE_URL'], schema) for _ in range(4)]
        ids = [f.result(timeout=30) for f in futures]
    assert len(set(ids)) == 1
    assert repository.messages('alice', ids[0])['message_count'] == 1
