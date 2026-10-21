import time

import pytest

from app.chat.tasks.task_store import TaskStore
from app.services import job_store
from app.services.job_retry_service import retry_durable_job
from app.services.platform_task_handlers import enqueue_platform_task
from core import Config


@pytest.fixture
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv('JOB_PERSISTENCE_MODE', 'json')
    monkeypatch.setattr(Config, 'STORAGE_ROOT', tmp_path / 'jobs')
    store = TaskStore(str(tmp_path / 'tasks.db'))
    yield store
    store.close()


def test_native_generation_receives_full_execution_window_after_queue(isolated_store):
    job = job_store.create_job(kind=job_store.JobKind.GENERATE_CLASSROOM,
                              owner_user_id='teacher', course_id='course')
    enqueue_platform_task(job=job, workflow_type='classroom_generate',
                          command={'deadline_seconds': 300, 'execution_timeout_seconds': None},
                          task_store=isolated_store)
    now = time.time() + 3500
    task = isolated_store.claim_next(lease_owner='worker', lease_seconds=60, now=now)
    assert task is not None
    assert task.deadline_at == pytest.approx(now + 3600)


@pytest.mark.parametrize('standard', [False, True])
def test_retry_upgrades_legacy_deadline_and_preserves_batch_window(isolated_store, standard):
    job = job_store.create_job(kind=job_store.JobKind.GENERATE_CLASSROOM,
                              owner_user_id='teacher', course_id='course')
    job_store.update_job(job.edu_job_id, status=job_store.JobStatus.FAILED, retryable=True)
    command = {'deadline_seconds': 300}
    if standard:
        command['material_metadata'] = {'origin_type': 'standard', 'standard_kind': 'classroom'}
    isolated_store.enqueue(task_id=job.edu_job_id, workflow_type='classroom_generate',
                           handler_version=1, owner_user_id='teacher', course_id='course',
                           scope_type='course', scope_id=None, command=command,
                           config_snapshot_id=None, idempotency_key=job.edu_job_id)
    retried = retry_durable_job(job, owner_user_id='teacher', task_store=isolated_store)
    task = isolated_store.get_durable(retried.edu_job_id)
    assert task.command['deadline_seconds'] == (86400 if standard else 3600)
    assert task.command['execution_timeout_seconds'] == 3600
