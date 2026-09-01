from __future__ import annotations

import threading
import time

import pytest

from app.chat.tasks.task_store import TaskStore
from app.services.durable_executor_pool import DurableExecutorPool
from app.services.durable_task_handlers import DurableTaskHandlerRegistry
from app.services.job_completion_service import JobCompletionService
from core.course_storage import CourseStorageManager


def _enqueue(store: TaskStore, task_id: str, workflow_type: str):
    return store.enqueue(
        task_id=task_id,
        workflow_type=workflow_type,
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command={"task_id": task_id},
        config_snapshot_id=None,
        idempotency_key=None,
        max_attempts=1,
    )


def _wait_for_status(
    store: TaskStore,
    task_id: str,
    status: str,
    timeout: float = 2,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = store.get_durable(task_id)
        if current is not None and current.status == status:
            return True
        time.sleep(0.01)
    return False


@pytest.fixture()
def pool_fixture(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    registry = DurableTaskHandlerRegistry()
    completion = JobCompletionService(
        task_store=store,
        course_storage_manager=CourseStorageManager(
            root_path=str(tmp_path / "courses")
        ),
    )
    pool = DurableExecutorPool(
        task_store=store,
        handler_registry=registry,
        completion_service=completion,
        worker_count=2,
        poll_interval=0.01,
        lease_seconds=2,
        heartbeat_interval=0.2,
    )
    yield store, registry, pool
    pool.stop(timeout_seconds=2)
    store.close()


def test_blocked_job_does_not_block_second_job(pool_fixture):
    store, registry, pool = pool_fixture
    blocker_started = threading.Event()
    release_blocker = threading.Event()

    def blocking_handler(command, context):
        blocker_started.set()
        assert release_blocker.wait(timeout=3)
        return {
            "saved": True,
            "result_ref": {"resource_type": "synthetic", "id": "blocking"},
        }

    def fast_handler(command, context):
        return {
            "saved": True,
            "result_ref": {"resource_type": "synthetic", "id": "fast"},
        }

    registry.register("blocking", 1, blocking_handler)
    registry.register("fast", 1, fast_handler)
    _enqueue(store, "job-blocking", "blocking")
    _enqueue(store, "job-fast", "fast")

    try:
        pool.start()
        assert blocker_started.wait(timeout=2)
        assert _wait_for_status(store, "job-fast", "succeeded", timeout=2)
        assert store.get_durable("job-blocking").status == "leased"
    finally:
        release_blocker.set()

    assert _wait_for_status(store, "job-blocking", "succeeded", timeout=2)


def test_pool_start_is_idempotent_and_worker_ids_are_unique(pool_fixture):
    _store, _registry, pool = pool_fixture

    pool.start()
    first_ids = pool.worker_ids
    pool.start()

    assert pool.worker_count == 2
    assert pool.worker_ids == first_ids
    assert len(set(first_ids)) == 2
    assert pool.stop(timeout_seconds=2) == ()


def test_shared_atomic_lease_executes_each_task_once(pool_fixture):
    store, registry, pool = pool_fixture
    calls = 0
    calls_lock = threading.Lock()

    def handler(command, context):
        nonlocal calls
        with calls_lock:
            calls += 1
        return {
            "saved": True,
            "result_ref": {"resource_type": "synthetic", "id": "once"},
        }

    registry.register("once", 1, handler)
    _enqueue(store, "job-once", "once")
    pool.start()

    assert _wait_for_status(store, "job-once", "succeeded", timeout=2)
    assert calls == 1


def test_pool_reports_worker_that_misses_shared_shutdown_deadline(pool_fixture):
    store, registry, pool = pool_fixture
    blocker_started = threading.Event()
    release_blocker = threading.Event()

    def blocking_handler(command, context):
        blocker_started.set()
        release_blocker.wait(timeout=3)
        return {
            "saved": True,
            "result_ref": {"resource_type": "synthetic", "id": "blocking"},
        }

    registry.register("blocking", 1, blocking_handler)
    _enqueue(store, "job-blocking", "blocking")
    pool.start()
    assert blocker_started.wait(timeout=2)

    stuck = pool.stop(timeout_seconds=0.01)
    release_blocker.set()

    assert len(stuck) == 1
    assert stuck[0] in pool.worker_ids
    assert pool.stop(timeout_seconds=2) == ()
