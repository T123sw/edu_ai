from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock
import pytest
from app.pbl import service
from app.pbl.repository import PblRepository,StaleGeneration
from app.pbl.contracts import public_artifact
from app.services.durable_task_handlers import DurableTaskExecutionError
from .test_generation import context,command,spies,install_pipeline
from app.pbl import project_service

@pytest.mark.asyncio
@pytest.mark.parametrize('template',['js-function-v1','outdated'])
async def test_unpublished_legacy_checkpoint_enters_unified_planning(repository,exercise,command,context,spies,candidate,template):
    repository.save_checkpoint('alice',exercise.id,context.task_id,{'stage':'validated','candidate':candidate.model_dump(mode='json'),
        'validation_report':{'passed':True,'templateVersion':template}})
    await service.generate_exercise(command,context,repository=repository)
    assert [call.args[2] for call in spies[0].call_args_list]==['plan','build_step','build_checks']
    assert repository.get_owned('alice',exercise.id).artifact_public['schemaVersion']==2

@pytest.mark.asyncio
async def test_retry_same_exercise_claim_updates_visible_job(repository,exercise,command,context,spies,monkeypatch):
    original=context.task_id
    context.task_id='retry-job'
    monkeypatch.setattr(service,'get_job',lambda _:SimpleNamespace(retry_of_job_id=original))
    await service.generate_exercise(command,context,repository=repository)
    assert repository.get_owned('alice',exercise.id).current_job_id=='retry-job'
    with pytest.raises(StaleGeneration):repository.save_checkpoint('alice',exercise.id,original,{})


def test_same_job_old_attempt_lease_fenced(engine,repository,exercise,context,candidate,validation_report):
    guarded=PblRepository(engine=engine,lease_context=context)
    assert guarded.claim_generation('alice',exercise.id,context.task_id)
    context.is_lease_valid=lambda:False
    with pytest.raises(StaleGeneration):guarded.save_checkpoint('alice',exercise.id,context.task_id,{})
    artifact=public_artifact(candidate,exercise_id=exercise.id,artifact_version=1,validation_summary=validation_report)
    with pytest.raises(StaleGeneration):guarded.publish('alice',exercise.id,context.task_id,artifact,{},validation_report)

@pytest.mark.asyncio
async def test_cancel_before_publish_does_not_expose_artifact(repository,exercise,command,context,spies,validation_report):
    canceled=False
    def validation(files,checks):
        nonlocal canceled
        canceled=True
        return validation_report
    spies[1].side_effect=validation
    context.is_cancel_requested=lambda:canceled
    with pytest.raises(DurableTaskExecutionError):await service.generate_exercise(command,context,repository=repository)
    assert repository.get_owned('alice',exercise.id).artifact_public is None


def build_executor(tmp_path,monkeypatch,repository,exercise,candidate,validation_report):
    from app.chat.tasks.task_store import TaskStore
    from app.services.durable_task_executor import DurableTaskExecutor
    from app.services.durable_task_handlers import DurableTaskHandlerRegistry
    from app.services.job_completion_service import JobCompletionService
    from app.services.job_store import create_job,JobKind
    from core.course_storage import CourseStorageManager
    store=TaskStore(db_path=str(tmp_path/'durable.db'))
    job=create_job(kind=JobKind.GENERATE_PBL,edu_job_id=exercise.id,owner_user_id='alice',scope_type='pbl',scope_id=exercise.id)
    store.enqueue(task_id=job.edu_job_id,workflow_type='pbl_generate',handler_version=1,owner_user_id='alice',course_id=None,
        scope_type='pbl',scope_id=exercise.id,command={'exercise_id':exercise.id,'topic':'快速排序'},
        config_snapshot_id=None,idempotency_key=job.edu_job_id,max_attempts=3)
    registry=DurableTaskHandlerRegistry()
    registry.register('pbl_generate',1,service.PblTaskHandler())
    monkeypatch.setattr(service,'PblRepository',lambda lease_context:PblRepository(engine=repository.engine,lease_context=lease_context))
    install_pipeline(monkeypatch)
    executor=DurableTaskExecutor(task_store=store,handler_registry=registry,
        completion_service=JobCompletionService(task_store=store,course_storage_manager=CourseStorageManager(root_path=str(tmp_path/'courses'))),
        worker_id='pbl-worker',lease_seconds=5,heartbeat_interval=.1)
    return store,executor,job


def test_actual_executor_and_job_retry_preserve_exercise(tmp_path,monkeypatch,repository,exercise,candidate,validation_report):
    from app.services.job_store import get_job
    from app.services.job_retry_service import retry_durable_job
    store,executor,job=build_executor(tmp_path,monkeypatch,repository,exercise,candidate,validation_report)
    model=project_service.generate_project_phase
    original=model.side_effect
    model.side_effect=TimeoutError('private model information')
    assert executor.run_once()
    failed=get_job(job.edu_job_id)
    assert failed.status.value=='failed' and failed.error_code=='PBL_MODEL_UNAVAILABLE'
    retried=retry_durable_job(failed,owner_user_id='alice',task_store=store)
    assert retried.edu_job_id!=job.edu_job_id and retried.retry_of_job_id==job.edu_job_id
    assert store.get_durable(retried.edu_job_id).command['exercise_id']==exercise.id
    assert store.get_durable(retried.edu_job_id).command['execution_timeout_seconds']==1800
    model.side_effect=original
    assert executor.run_once()
    assert get_job(retried.edu_job_id).status.value=='succeeded'
    assert store.get_durable(retried.edu_job_id).result_ref=={'resource_type':'pbl_exercise','exercise_id':exercise.id}
    assert repository.get_owned('alice',exercise.id).current_job_id==retried.edu_job_id


def test_actual_executor_cancel_during_model_is_canceled(tmp_path,monkeypatch,repository,exercise,candidate,validation_report):
    from app.services.job_store import get_job
    store,executor,job=build_executor(tmp_path,monkeypatch,repository,exercise,candidate,validation_report)
    async def cancel(*args,**kwargs):
        store.request_cancel(job.edu_job_id,owner_user_id='alice')
        return candidate
    project_service.generate_project_phase.side_effect=cancel
    assert executor.run_once()
    assert get_job(job.edu_job_id).status.value=='canceled'
    assert store.get_durable(job.edu_job_id).status=='canceled'
    assert repository.get_owned('alice',exercise.id).artifact_public is None


def test_superseded_retry_job_fails_without_overwriting_winner(tmp_path,monkeypatch,repository,exercise,candidate,validation_report):
    from app.services.job_store import get_job
    store,executor,job=build_executor(tmp_path,monkeypatch,repository,exercise,candidate,validation_report)
    assert repository.claim_generation('alice',exercise.id,'winning-retry',exercise.id)
    assert executor.run_once()
    assert get_job(job.edu_job_id).status.value=='failed'
    assert get_job(job.edu_job_id).error_code=='PBL_STALE_ATTEMPT'
    assert repository.get_owned('alice',exercise.id).current_job_id=='winning-retry'


def test_explicit_retry_refreshes_exhausted_budget_but_recovery_does_not(tmp_path,monkeypatch,repository,exercise,candidate,validation_report):
    from app.services.job_store import get_job
    from app.services.job_retry_service import retry_durable_job
    store,executor,job=build_executor(tmp_path,monkeypatch,repository,exercise,candidate,validation_report)
    model=project_service.generate_project_phase
    original=model.side_effect
    target=''
    async def invalid_step(owner,snapshot,phase,data):
        nonlocal target
        if phase in {'build_step','repair_step'}:
            target=data['step']['id']
            raise ValueError('broken implementation')
        return await original(owner,snapshot,phase,data)
    model.side_effect=invalid_step
    assert executor.run_once()
    failed=get_job(job.edu_job_id)
    assert failed.error_code=='PBL_VALIDATION_FAILED'
    checkpoint=repository.get_owned('alice',exercise.id).checkpoint
    assert checkpoint['repairs'][target]==3
    retried=retry_durable_job(failed,owner_user_id='alice',task_store=store)
    assert executor.run_once()
    again=get_job(retried.edu_job_id)
    assert again.error_code=='PBL_VALIDATION_FAILED'
    checkpoint=repository.get_owned('alice',exercise.id).checkpoint
    assert checkpoint['repairs'][target]==3 and checkpoint['repairTotals'][target]==6
    assert checkpoint['generationJobId']==retried.edu_job_id
    successful=retry_durable_job(again,owner_user_id='alice',task_store=store)
    model.side_effect=original
    before=model.call_count
    assert executor.run_once()
    assert model.call_count>before
    assert get_job(successful.edu_job_id).status.value=='succeeded'
    assert repository.get_owned('alice',exercise.id).artifact_public
