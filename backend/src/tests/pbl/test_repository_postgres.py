"""Explicit opt-in test database; each test owns a random PostgreSQL schema."""
import importlib.util
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import create_engine,text,update
from sqlalchemy.orm import Session
from app.database.models import DurableTaskModel
from app.pbl.db_models import PblExercise,PblWorkspace,PblRun
from app.pbl.repository import PblRepository,WorkspaceConflict,StaleGeneration
from app.pbl.contracts import public_artifact

@pytest.fixture
def pg_engine():
    url=os.getenv('PBL_TEST_DATABASE_URL','')
    if not url: pytest.skip('PBL_TEST_DATABASE_URL explicitly required')
    if not url.startswith('postgresql') or not any(tag in url.rsplit('/',1)[-1] for tag in ('test','acceptance')):
        pytest.fail('PBL_TEST_DATABASE_URL must name an explicit test/acceptance PostgreSQL database')
    admin=create_engine(url)
    schema='pbl_test_'+uuid4().hex
    with admin.begin() as connection:connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine=create_engine(url,connect_args={'options':f'-csearch_path={schema}'})
    yield engine
    engine.dispose()
    with admin.begin() as connection:connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()

@pytest.fixture
def pg_repository(pg_engine):
    for model in (PblExercise,PblWorkspace,PblRun,DurableTaskModel):model.__table__.create(pg_engine)
    return PblRepository(engine=pg_engine)


def test_two_transactions_exactly_one_workspace_cas_wins(pg_repository,candidate,validation_report):
    repository=pg_repository
    exercise=repository.create_or_get('alice',str(uuid4()),'快速排序')
    artifact=public_artifact(candidate,exercise_id=exercise.id,artifact_version=1,validation_summary=validation_report)
    repository.publish('alice',exercise.id,exercise.current_job_id,artifact,{},validation_report)
    repository.get_or_create_workspace('alice',exercise.id)
    barrier=threading.Barrier(2)
    def save(code):
        barrier.wait()
        try:
            return repository.save_workspace('alice',exercise.id,{'artifactVersion':1,'expectedRevision':0,
                'mutationId':str(uuid4()),'files':{'/src/algorithm.js':code},'activeTaskId':'implement-sort','customInputText':'[]'}).files
        except WorkspaceConflict:return None
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(save,['first','second']))
    assert sum(result is not None for result in results)==1
    workspace=repository.get_or_create_workspace('alice',exercise.id)
    assert workspace.revision==1 and workspace.files==next(result for result in results if result)


def test_concurrent_retry_claim_one_winner(pg_repository):
    exercise=pg_repository.create_or_get('alice',str(uuid4()),'快速排序')
    barrier=threading.Barrier(2)
    def claim(job):
        barrier.wait()
        return pg_repository.claim_generation('alice',exercise.id,job,exercise.current_job_id)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(claim,['retry-a','retry-b']))
    assert results.count(True)==1


def insert_lease(engine,identifier):
    with Session(engine) as session:
        session.add(DurableTaskModel(task_id=identifier,workflow_type='pbl_generate',handler_version=1,
            owner_user_id='alice',scope_type='pbl',status='leased',attempt_count=2,max_attempts=3,
            available_at=time.time(),lease_owner='new-worker',lease_expires_at=time.time()+60,
            cancel_requested=False,created_at='test',updated_at=time.time()))
        session.commit()


def test_same_job_stale_attempt_cannot_checkpoint_or_publish(pg_repository,pg_engine,candidate,validation_report):
    exercise=pg_repository.create_or_get('alice',str(uuid4()),'快速排序')
    insert_lease(pg_engine,exercise.id)
    context=SimpleNamespace(task_id=exercise.id,owner_user_id='alice',lease_owner='old-worker',attempt_count=1,
        is_cancel_requested=lambda:False,is_lease_valid=lambda:True)
    guarded=PblRepository(engine=pg_engine,lease_context=context)
    artifact=public_artifact(candidate,exercise_id=exercise.id,artifact_version=1,validation_summary=validation_report)
    with pytest.raises(StaleGeneration):guarded.save_checkpoint('alice',exercise.id,exercise.id,{})
    with pytest.raises(StaleGeneration):guarded.publish('alice',exercise.id,exercise.id,artifact,{},validation_report)
    context.lease_owner='new-worker'
    with pytest.raises(StaleGeneration):guarded.save_checkpoint('alice',exercise.id,exercise.id,{})
    context.attempt_count=2
    guarded.save_checkpoint('alice',exercise.id,exercise.id,{'stage':'validated'})
    # Cancellation/deadline/lease are checked in the same locked DB transaction.
    with pg_engine.begin() as connection:
        connection.execute(update(DurableTaskModel).where(DurableTaskModel.task_id==exercise.id).values(cancel_requested=True))
    with pytest.raises(StaleGeneration):guarded.publish('alice',exercise.id,exercise.id,artifact,{},validation_report)
    with pg_engine.begin() as connection:
        connection.execute(update(DurableTaskModel).where(DurableTaskModel.task_id==exercise.id).values(cancel_requested=False,lease_expires_at=time.time()-1))
    with pytest.raises(StaleGeneration):guarded.publish('alice',exercise.id,exercise.id,artifact,{},validation_report)
    with pg_engine.begin() as connection:
        connection.execute(update(DurableTaskModel).where(DurableTaskModel.task_id==exercise.id).values(lease_expires_at=time.time()+60))
    guarded.publish('alice',exercise.id,exercise.id,artifact,{},validation_report)
    assert pg_repository.get_owned('alice',exercise.id).artifact_version==1


def test_migration_upgrade_downgrade_only_isolated_schema(pg_engine):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    migration_path=Path(__file__).parents[2]/'alembic/versions/20261013_0038_pbl_practice.py'
    spec=importlib.util.spec_from_file_location('pbl_migration',migration_path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pg_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            names=set(connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()" )).scalars())
            assert {'pbl_exercises','pbl_workspaces','pbl_runs'}<=names
            module.downgrade()
            assert not list(connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()" )).scalars())
            module.upgrade()
