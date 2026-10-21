"""Real authorization with a deliberately saturated pool; no production DB."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from app.database import Base, User
from app.database.models import Conversation, ConversationMessage
from app.course_preparation.adapters.document_store import DocumentStore
from app.course_preparation.adapters.targets import TargetStore
from app.course_preparation.artifact_store import ArtifactStore
from app.course_preparation.authorizer import PreparationReferenceAuthorizer
from app.course_preparation.lifecycle_repository import LifecycleRepository, StaleLease
from app.course_preparation.runtime_contracts import BudgetCost
from app.course_preparation.schemas import PreparationRequest
from tests.course_preparation.test_generation_adapter import spec


@pytest.fixture
def single_connection(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "single.db"}', poolclass=QueuePool,
                           pool_size=1, max_overflow=0, pool_timeout=2)
    @event.listens_for(engine, 'connect')
    def configure(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA synchronous=OFF')
        connection.execute('PRAGMA journal_mode=MEMORY')
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        for owner in ('alice', 'bob'):
            session.add(User(user_id=owner, username=owner, password_hash='test-only', role='student'))
    yield engine
    assert engine.pool.checkedout() == 0
    engine.dispose()


def request(**kwargs):
    return PreparationRequest(request_id=uuid4(), operation='create_course', goal='并发连接验证', **kwargs)


def repository(engine, documents=None):
    return LifecycleRepository(engine, authorizer=PreparationReferenceAuthorizer(
        engine, documents, targets=TargetStore(engine)))


def running_child(engine):
    repo = repository(engine)
    task = repo.submit('alice', request())
    context = repo.claim('worker', preparation_id=task['preparation_id'])
    action = repo.begin_action(context, 'generate', 'generate_resource', spec(), BudgetCost(calls=1))
    store = ArtifactStore(repo)
    artifact = store.create(context, action['action_id'], spec())
    return repo, context, store, store.claim('alice', artifact['artifact_id'])


def test_lifecycle_does_not_checkout_a_second_connection(single_connection):
    repo = repository(single_connection)
    task = repo.submit('alice', request())
    context = repo.claim('worker', preparation_id=task['preparation_id'])
    repo.heartbeat(context)
    repo.get(owner_user_id='alice', preparation_id=context.preparation_id)
    repo.checkpoint(context, {'saved': True})
    repo.fail(context, 'TEST_FAILURE')
    assert repo.retry('alice', context.preparation_id)['attempt_no'] == 2
    assert repo.claim('worker-2').checkpoint == {'saved': True}


def test_child_heartbeat_accounting_and_cancellation_keep_fences(single_connection):
    repo, context, store, child = running_child(single_connection)
    store.heartbeat(child)
    action = store.begin_action(child, 'call', 'model_completion', {}, BudgetCost(calls=1, tokens=10))
    store.finish_action(child, action['action_id'], {}, BudgetCost(calls=1, tokens=7))
    assert repo.get_public('alice', context.preparation_id)['budget']['consumed']['tokens'] == 7
    repo.cancel('alice', context.preparation_id)
    with pytest.raises(StaleLease, match='PARENT_NOT_ACTIVE'):
        store.heartbeat(child)


def test_sixteen_simultaneous_guards_fit_one_database_connection(single_connection):
    repo, context, store, child = running_child(single_connection)
    barrier = Barrier(16)
    def heartbeat():
        barrier.wait(timeout=5)
        store.heartbeat(child)
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(heartbeat) for _ in range(16)]
        for future in futures:
            future.result(timeout=5)
    assert repo.get_public('alice', context.preparation_id)['status'] == 'running'


def test_reused_session_still_refreshes_disabled_user(single_connection):
    repo = repository(single_connection)
    with Session(single_connection) as session, session.begin():
        cached = session.get(User, 'alice')
        session.execute(update(User).where(User.user_id == 'alice').values(is_disabled=True),
                        execution_options={'synchronize_session': False})
        assert not cached.is_disabled
        with pytest.raises(PermissionError, match='OWNER_UNAVAILABLE'):
            repo._authorize(session, 'alice', request())


def test_upload_hash_and_ownership_are_checked_on_the_existing_connection(single_connection):
    data = [b'original bytes']
    reader = SimpleNamespace(read_bytes=lambda owner, doc: ({'filename': 'test.txt'}, data[0]))
    documents = DocumentStore(single_connection, reader)
    ref = documents.register('alice', 'doc')
    req = request(uploads=[ref])
    repo = repository(single_connection, documents)
    task = repo.submit('alice', req)
    context = repo.claim('worker', preparation_id=task['preparation_id'])
    repo.heartbeat(context)
    data[0] = b'changed bytes'
    with pytest.raises(PermissionError, match='DOCUMENT_VERSION_CHANGED'):
        repo.heartbeat(context)
    with pytest.raises(PermissionError, match='DOCUMENT_VERSION_UNAVAILABLE'):
        repo.submit('bob', req)


def test_origin_ownership_is_not_bypassed(single_connection):
    with Session(single_connection) as session, session.begin():
        session.add(Conversation(conversation_id='chat', owner='alice'))
        session.add(ConversationMessage(message_id='msg', conversation_id='chat', position=0,
                    role='user', message_kind='text', content='test', occurred_at=datetime.now(timezone.utc)))
    req = request(origin={'conversation_id': 'chat', 'message_id': 'msg'})
    repo = repository(single_connection)
    task = repo.submit('alice', req)
    context = repo.claim('worker', preparation_id=task['preparation_id'])
    repo.heartbeat(context)
    with Session(single_connection) as session, session.begin():
        session.get(Conversation, 'chat').owner = 'bob'
    with pytest.raises(PermissionError, match='ORIGIN_UNAVAILABLE'):
        repo.heartbeat(context)


def test_existing_course_validation_uses_same_connection(single_connection, tmp_path):
    from app.chat.tasks.task_store import TaskStore
    from app.course_preparation.adapters.generation import GenerationAdapter
    from tests.course_preparation.test_delivery import ready
    repo = repository(single_connection)
    task = repo.submit('alice', request())
    context = repo.claim('worker', preparation_id=task['preparation_id'])
    adapter = GenerationAdapter(repo, TaskStore(db_path=str(tmp_path / 'queue.db')))
    _, context, delivery = ready.__wrapped__((repo, context, adapter))
    course = delivery.commit(context).result_ref['course_id']
    req = PreparationRequest(request_id=uuid4(), operation='supplement_node', goal='more',
        target={'course_id': course, 'base_manifest_version': 1, 'node_id': 'tools'})
    task = repo.submit('alice', req)
    context = repo.claim('worker', preparation_id=task['preparation_id'])
    repo.heartbeat(context)
    with pytest.raises(PermissionError, match='TARGET_COURSE_UNAVAILABLE'):
        repo.submit('bob', req)
