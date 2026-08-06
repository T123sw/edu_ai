import threading

import pytest

from app.chat.tasks.task_store import TaskStore
from app.services.durable_task_executor import (
    DurableTaskExecutor,
    RetryableTaskError,
)
from app.services.durable_task_handlers import (
    DurableTaskHandlerRegistry,
    UnsupportedTaskHandler,
)
from app.services.job_completion_service import JobCompletionService
from app.services.job_store import JobKind, JobStatus, create_job, get_job
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
