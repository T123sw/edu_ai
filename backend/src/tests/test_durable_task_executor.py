import threading
import time

import pytest

from app.chat.tasks.task_store import TaskStore
from app.services.durable_task_executor import (
    DurableTaskExecutor,
    RetryableTaskError,
)
from app.services.durable_task_handlers import (
    DurableTaskExecutionError,
    DurableTaskHandlerRegistry,
    UnsupportedTaskHandler,
)
from app.services.job_completion_service import JobCompletionService
from app.services.job_store import JobKind, JobStatus, create_job, get_job
from app.chat.model_gateway import ModelUnavailableError
from core import Config
from core.course_storage import CourseStorageManager


class ObservingTaskStore(TaskStore):
    def __init__(self, db_path: str):
        self.heartbeat_seen = threading.Event()
        super().__init__(db_path)

    def heartbeat(self, *args, **kwargs):
        result = super().heartbeat(*args, **kwargs)
        if result:
            self.heartbeat_seen.set()
        return result


def build_runtime(monkeypatch, tmp_path, *, observing: bool = False):
    monkeypatch.setenv("JOB_PERSISTENCE_MODE", "json")
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "app-storage")
    store_class = ObservingTaskStore if observing else TaskStore
    store = store_class(str(tmp_path / "tasks.db"))
    manager = CourseStorageManager(root_path=str(tmp_path / "course-storage"))
    manager.create_course_structure("course-1")
    store.enqueue(
        task_id="job-1",
        workflow_type="report_direct",
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command={"title": "Report", "runtime_config_snapshot": {}},
        config_snapshot_id="cfg-1",
        idempotency_key=None,
        max_attempts=3,
    )
    create_job(
        kind=JobKind.GENERATE_REPORT,
        edu_job_id="job-1",
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"title": "Report"},
    )
    registry = DurableTaskHandlerRegistry()
    completion = JobCompletionService(
        task_store=store,
        course_storage_manager=manager,
    )
    executor = DurableTaskExecutor(
        task_store=store,
        handler_registry=registry,
        completion_service=completion,
        worker_id="worker-a",
        lease_seconds=1,
        heartbeat_interval=0.01,
        poll_interval=0.01,
    )
    return store, manager, registry, executor


def publish_report(manager, context):
    assert manager.save_generated_material(
        "course-1",
        "report",
        "report-1",
        {"title": "Report"},
        owner_user_id=context.owner_user_id,
        source_job_id=context.task_id,
        config_snapshot_id=context.config_snapshot_id,
    )
    return {
        "saved": True,
        "result_ref": {
            "resource_type": "course_material",
            "course_id": "course-1",
            "material_type": "report",
            "material_id": "report-1",
        },
    }


def test_registry_resolves_exact_workflow_and_version():
    registry = DurableTaskHandlerRegistry()
    handler = lambda command, context: {"saved": True}
    registry.register("report_direct", 1, handler)

    assert registry.resolve("report_direct", 1) is handler
    with pytest.raises(UnsupportedTaskHandler):
        registry.resolve("report_direct", 2)


def test_executor_claims_runs_and_completes_a_registered_task(
    monkeypatch,
    tmp_path,
):
    store, manager, registry, executor = build_runtime(monkeypatch, tmp_path)
    registry.register(
        "report_direct",
        1,
        lambda command, context: publish_report(manager, context),
    )

    assert executor.run_once() is True

    task = store.get_durable("job-1")
    job = get_job("job-1")
    assert task is not None
    assert task.status == "succeeded"
    assert job is not None
    assert job.status == JobStatus.SUCCEEDED
    store.close()


def test_unknown_handler_fails_without_retrying(monkeypatch, tmp_path):
    store, _, _, executor = build_runtime(monkeypatch, tmp_path)

    assert executor.run_once() is True

    task = store.get_durable("job-1")
    job = get_job("job-1")
    assert task is not None
    assert task.status == "failed"
    assert task.error_code == "UNSUPPORTED_HANDLER_VERSION"
    assert job is not None
    assert job.status == JobStatus.FAILED
    store.close()


def test_retryable_error_requeues_with_backoff(monkeypatch, tmp_path):
    store, _, registry, executor = build_runtime(monkeypatch, tmp_path)

    def unavailable(command, context):
        raise RetryableTaskError("provider unavailable", code="PROVIDER_UNAVAILABLE")

    registry.register("report_direct", 1, unavailable)

    assert executor.run_once() is True

    task = store.get_durable("job-1")
    job = get_job("job-1")
    assert task is not None
    assert task.status == "pending"
    assert task.error_code == "PROVIDER_UNAVAILABLE"
    assert task.available_at > task.updated_at
    assert job is not None
    assert job.status == JobStatus.QUEUED
    store.close()


def test_executor_heartbeats_while_handler_is_blocked(monkeypatch, tmp_path):
    store, manager, registry, executor = build_runtime(
        monkeypatch,
        tmp_path,
        observing=True,
    )
    assert isinstance(store, ObservingTaskStore)

    def wait_for_heartbeat(command, context):
        assert store.heartbeat_seen.wait(timeout=1)
        return publish_report(manager, context)

    registry.register("report_direct", 1, wait_for_heartbeat)

    assert executor.run_once() is True
    assert store.heartbeat_seen.is_set()
    assert store.get_durable("job-1").status == "succeeded"
    store.close()


def test_deadline_fails_blocked_handler_and_rejects_late_progress(monkeypatch, tmp_path):
    store, _, registry, executor = build_runtime(monkeypatch, tmp_path)
    started, release = threading.Event(), threading.Event()
    observed = {}

    def blocked_provider(command, context):
        observed["context"] = context
        started.set()
        assert release.wait(timeout=5)
        context.progress(80, "saving", "late provider response")
        return {"saved": True, "result_ref": {"resource_type": "test"}}

    registry.register("report_direct", 1, blocked_provider)
    store._conn.execute(
        "UPDATE tasks SET deadline_at=? WHERE task_id='job-1'", (time.time() + 0.5,)
    )
    store._conn.commit()
    executor.start()
    try:
        assert started.wait(timeout=2)
        end = time.monotonic() + 2
        while get_job("job-1").status != JobStatus.FAILED and time.monotonic() < end:
            time.sleep(0.01)
        assert not release.is_set()
        assert store.get_durable("job-1").status == "failed"
        assert get_job("job-1").error_code == "GENERATION_DEADLINE_EXCEEDED"
        assert observed["context"].is_cancel_requested()
        release.set()
        executor.stop(grace_seconds=2)
        assert not executor.is_running
        assert get_job("job-1").status == JobStatus.FAILED
        assert get_job("job-1").progress == 100
        assert store.get_durable("job-1").status == "failed"
    finally:
        release.set()
        executor.stop(grace_seconds=2)
        store.close()


def test_business_failure_preserves_its_stable_error_code(monkeypatch, tmp_path):
    store, _, registry, executor = build_runtime(monkeypatch, tmp_path)

    def indexing_failed(command, context):
        raise DurableTaskExecutionError("RAG_INDEX_FAILED", "embedding unavailable")

    registry.register("report_direct", 1, indexing_failed)

    assert executor.run_once() is True

    task = store.get_durable("job-1")
    job = get_job("job-1")
    assert task is not None
    assert task.status == "failed"
    assert task.error_code == "RAG_INDEX_FAILED"
    assert task.error == "embedding unavailable"
    assert job is not None
    assert job.status == JobStatus.FAILED
    assert job.error_code == "RAG_INDEX_FAILED"
    assert job.error_message == "embedding unavailable"
    store.close()


def test_model_unavailable_is_a_retryable_provider_failure(monkeypatch, tmp_path):
    store, _, registry, executor = build_runtime(monkeypatch, tmp_path)

    def unavailable(command, context):
        raise ModelUnavailableError("模型服务暂时不可用")

    registry.register("report_direct", 1, unavailable)

    assert executor.run_once() is True

    task = store.get_durable("job-1")
    job = get_job("job-1")
    assert task is not None
    assert task.status == "failed"
    assert task.error_code == "PROVIDER_UNAVAILABLE"
    assert job is not None
    assert job.status == JobStatus.FAILED
    assert job.error_code == "PROVIDER_UNAVAILABLE"
    assert job.retryable is True
    store.close()


def test_run_once_recovers_an_expired_lease_before_claiming(
    monkeypatch,
    tmp_path,
):
    store, _, _, executor = build_runtime(monkeypatch, tmp_path)
    connection = store._conn
    connection.execute(
        "UPDATE tasks SET max_attempts=1, available_at=100, deadline_at=500 "
        "WHERE task_id='job-1'"
    )
    connection.commit()
    assert store.claim_next(
        lease_owner="dead-worker",
        lease_seconds=10,
        now=100.0,
    )

    assert executor.run_once(now=111.0) is False

    task = store.get_durable("job-1")
    assert task is not None
    assert task.status == "failed"
    assert task.error_code == "WORKER_LOST"
    store.close()


def test_worker_loop_survives_a_transient_claim_failure(
    monkeypatch,
    tmp_path,
):
    store, _, _, executor = build_runtime(monkeypatch, tmp_path)
    original_claim = store.claim_next
    claim_attempts = 0

    def flaky_claim(*args, **kwargs):
        nonlocal claim_attempts
        claim_attempts += 1
        if claim_attempts == 1:
            raise RuntimeError("temporary sqlite failure")
        return original_claim(*args, **kwargs)

    monkeypatch.setattr(store, "claim_next", flaky_claim)
    executor.start()
    deadline = time.monotonic() + 1
    while claim_attempts < 2 and time.monotonic() < deadline:
        time.sleep(0.01)

    assert claim_attempts >= 2
    assert executor.is_running is True
    executor.stop(grace_seconds=1)
    store.close()


def test_handler_cooperative_stop_on_deadline_is_timeout_not_user_cancel(monkeypatch,tmp_path):
    store,manager,registry,executor=build_runtime(monkeypatch,tmp_path)
    expired=False
    monkeypatch.setattr(executor,'_deadline_exceeded',lambda *args,**kwargs:expired)
    def handler(command,context):
        nonlocal expired
        expired=True
        assert context.is_cancel_requested()
        raise DurableTaskExecutionError('GENERATION_CANCELLED','stopped')
    registry.register('report_direct',1,handler)
    assert executor.run_once()
    assert get_job('job-1').error_code=='GENERATION_DEADLINE_EXCEEDED'
    assert store.get_durable('job-1').status=='failed'
