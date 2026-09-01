import pytest

from app.chat.tasks.task_store import TaskStore
from app.services.job_completion_service import JobCompletionService
from app.services.job_store import JobKind, JobStatus, create_job, get_job
from core import Config
from core.course_storage import CourseStorageManager


@pytest.fixture()
def completion_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "app-storage")
    manager = CourseStorageManager(root_path=str(tmp_path / "course-storage"))
    manager.create_course_structure("course-1")
    store = TaskStore(str(tmp_path / "tasks.db"))
    store.enqueue(
        task_id="job-1",
        workflow_type="report_direct",
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command={"title": "Report"},
        config_snapshot_id="cfg-1",
        idempotency_key=None,
        max_attempts=3,
    )
    task = store.claim_next(
        lease_owner="worker-a",
        lease_seconds=45,
    )
    assert task is not None
    create_job(
        kind=JobKind.GENERATE_REPORT,
        edu_job_id=task.task_id,
        owner_user_id=task.owner_user_id,
        course_id=task.course_id,
        input_summary={"title": "Report"},
    )
    service = JobCompletionService(
        task_store=store,
        course_storage_manager=manager,
    )
    yield service, store, manager, task
    store.close()


def result_ref(material_id: str = "report-1") -> dict:
    return {
        "resource_type": "course_material",
        "course_id": "course-1",
        "material_type": "report",
        "material_id": material_id,
    }


def test_success_requires_owner_scoped_material_readback(completion_runtime):
    service, store, manager, task = completion_runtime
    assert manager.save_generated_material(
        "course-1",
        "report",
        "report-1",
        {"title": "Report"},
        owner_user_id="teacher-a",
        source_job_id=task.task_id,
    )

    service.finish(
        task,
        lease_owner="worker-a",
        generated_result={"saved": True, "result_ref": result_ref()},
    )

    durable = store.get_durable(task.task_id)
    public = get_job(task.task_id)
    assert durable is not None
    assert durable.status == "succeeded"
    assert durable.result_ref == result_ref()
    assert public is not None
    assert public.status == JobStatus.SUCCEEDED
    assert public.result_ref == result_ref()
    assert public.message == "生成完成，已保存到“我的资源”，仅你可见。"


def test_missing_material_becomes_partial_success(completion_runtime):
    service, store, _, task = completion_runtime

    service.finish(
        task,
        lease_owner="worker-a",
        generated_result={"saved": True, "result_ref": result_ref("missing")},
    )

    durable = store.get_durable(task.task_id)
    public = get_job(task.task_id)
    assert durable is not None
    assert durable.status == "partially_succeeded"
    assert durable.error_code == "RESOURCE_READBACK_FAILED"
    assert public is not None
    assert public.status == JobStatus.PARTIALLY_SUCCEEDED
    assert public.error_code == "RESOURCE_READBACK_FAILED"


def test_wrong_owner_cannot_pass_material_readback(completion_runtime):
    service, store, manager, task = completion_runtime
    assert manager.save_generated_material(
        "course-1",
        "report",
        "report-1",
        {"title": "Another teacher report"},
        owner_user_id="teacher-b",
        source_job_id=task.task_id,
    )

    service.finish(
        task,
        lease_owner="worker-a",
        generated_result={"saved": True, "result_ref": result_ref()},
    )

    durable = store.get_durable(task.task_id)
    public = get_job(task.task_id)
    assert durable is not None
    assert durable.status == "partially_succeeded"
    assert public is not None
    assert public.status == JobStatus.PARTIALLY_SUCCEEDED


def test_mismatched_source_job_cannot_pass_material_readback(
    completion_runtime,
):
    service, store, manager, task = completion_runtime
    assert manager.save_generated_material(
        "course-1",
        "report",
        "report-1",
        {"title": "Stale report"},
        owner_user_id="teacher-a",
        source_job_id="job-older",
    )

    service.finish(
        task,
        lease_owner="worker-a",
        generated_result={"saved": True, "result_ref": result_ref()},
    )

    durable = store.get_durable(task.task_id)
    assert durable is not None
    assert durable.status == "partially_succeeded"
    assert durable.error_code == "RESOURCE_PROVENANCE_MISMATCH"
