import pytest

from app.chat.tasks.task_store import TaskStore
from app.services.job_reconciliation_service import JobReconciliationService
from app.services.job_store import (
    JobKind,
    JobStatus,
    create_job,
    get_job,
)
from core import Config
from core.course_storage import CourseStorageManager


@pytest.fixture()
def reconciliation_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "app-storage")
    store = TaskStore(str(tmp_path / "tasks.db"))
    manager = CourseStorageManager(root_path=str(tmp_path / "course-storage"))
    manager.create_course_structure("course-1")
    service = JobReconciliationService(
        task_store=store,
        course_storage_manager=manager,
        now_provider=lambda: 200.0,
    )
    yield service, store, manager
    store.close()


def enqueue_report(store: TaskStore, *, max_attempts: int = 3):
    return store.enqueue(
        task_id="job-1",
        workflow_type="report_direct",
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command={
            "resource_type": "report",
            "course_id": "course-1",
            "material_id": "report-1",
        },
        config_snapshot_id="cfg-1",
        idempotency_key="request-1",
        max_attempts=max_attempts,
        available_at=100.0,
    )


def create_report_job():
    return create_job(
        kind=JobKind.GENERATE_REPORT,
        edu_job_id="job-1",
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"title": "Report"},
    )


def test_startup_requeues_an_expired_lease_and_repairs_public_status(
    reconciliation_runtime,
):
    service, store, _ = reconciliation_runtime
    enqueue_report(store)
    create_report_job()
    assert store.claim_next(
        lease_owner="dead-worker",
        lease_seconds=10,
        now=100,
    )

    service.reconcile_startup()

    durable = store.get_durable("job-1")
    public = get_job("job-1")
    assert durable is not None
    assert durable.status == "pending"
    assert durable.error_code == "LEASE_EXPIRED"
    assert public is not None
    assert public.status == JobStatus.QUEUED
    assert public.step == "recovered"


def test_startup_fails_an_expired_lease_after_max_attempts(
    reconciliation_runtime,
):
    service, store, _ = reconciliation_runtime
    enqueue_report(store, max_attempts=1)
    create_report_job()
    assert store.claim_next(
        lease_owner="dead-worker",
        lease_seconds=10,
        now=100,
    )

    service.reconcile_startup()

    durable = store.get_durable("job-1")
    public = get_job("job-1")
    assert durable is not None
    assert durable.status == "failed"
    assert durable.error_code == "WORKER_LOST"
    assert public is not None
    assert public.status == JobStatus.FAILED
    assert public.error_code == "WORKER_LOST"


def test_startup_finishes_an_already_published_resource_without_rerunning(
    reconciliation_runtime,
):
    service, store, manager = reconciliation_runtime
    enqueue_report(store)
    create_report_job()
    assert store.claim_next(
        lease_owner="dead-worker",
        lease_seconds=10,
        now=100,
    )
    assert manager.save_generated_material(
        "course-1",
        "report",
        "report-1",
        {"title": "Recovered report"},
        owner_user_id="teacher-a",
        source_job_id="job-1",
        config_snapshot_id="cfg-1",
    )

    service.reconcile_startup()

    durable = store.get_durable("job-1")
    public = get_job("job-1")
    assert durable is not None
    assert durable.status == "succeeded"
    assert public is not None
    assert public.status == JobStatus.SUCCEEDED
    assert public.result_ref == {
        "resource_type": "course_material",
        "course_id": "course-1",
        "material_type": "report",
        "material_id": "report-1",
    }


def test_another_owners_resource_cannot_finish_the_task(
    reconciliation_runtime,
):
    service, store, manager = reconciliation_runtime
    enqueue_report(store)
    create_report_job()
    assert manager.save_generated_material(
        "course-1",
        "report",
        "report-1",
        {"title": "Other report"},
        owner_user_id="teacher-b",
        source_job_id="job-1",
    )

    service.reconcile_startup()

    durable = store.get_durable("job-1")
    public = get_job("job-1")
    assert durable is not None
    assert durable.status == "pending"
    assert public is not None
    assert public.status == JobStatus.QUEUED
