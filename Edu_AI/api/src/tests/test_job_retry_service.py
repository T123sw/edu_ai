import asyncio

from app.services import job_retry_service, job_store
from app.chat.tasks.task_store import TaskStore
from app.services.job_store import JobKind, JobStatus
from core import Config


def test_standard_resource_durable_retry_replaces_expired_batch_deadline(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "jobs")
    store = TaskStore(str(tmp_path / "tasks.db"))
    original = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id="teacher-a",
        course_id="course-1",
    )
    job_store.update_job(
        original.edu_job_id,
        status=JobStatus.FAILED,
        retryable=True,
    )
    store.enqueue(
        task_id=original.edu_job_id,
        workflow_type="classroom_generate",
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="knowledge_point",
        scope_id="abstraction",
        command={
            "deadline_seconds": 300,
            "material_metadata": {
                "origin_type": "standard",
                "standard_kind": "classroom",
                "generation_batch_id": "standard-batch-old",
            },
        },
        config_snapshot_id=None,
        idempotency_key=original.edu_job_id,
    )

    retried = job_retry_service.retry_durable_job(
        original,
        owner_user_id="teacher-a",
        task_store=store,
    )

    assert retried is not None
    retried_task = store.get_durable(retried.edu_job_id)
    assert retried_task is not None
    assert retried_task.command["deadline_seconds"] == 86400
    assert retried_task.command["execution_timeout_seconds"] == 3600
    store.close()


def test_classroom_retry_calls_original_business_submitter(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path)
    retried = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={
            "requirement": "围绕勾股定理生成课堂",
            "enable_web_search": True,
            "enable_tts": False,
        },
    )
    captured = {}

    async def fake_submit(**kwargs):
        captured.update(kwargs)
        return kwargs["existing_job"]

    monkeypatch.setattr(
        job_retry_service,
        "submit_classroom_generation_job",
        fake_submit,
    )

    dispatched = asyncio.run(
        job_retry_service.dispatch_retry_job(
            retried,
            auth_token="token",
            current_user={"username": "teacher-a"},
            course_storage_manager=object(),
        )
    )

    assert dispatched.edu_job_id == retried.edu_job_id
    assert captured["course_id"] == "course-1"
    assert captured["requirement"] == "围绕勾股定理生成课堂"
    assert captured["enable_web_search"] is True
    assert captured["enable_tts"] is False
    assert captured["existing_job"].edu_job_id == retried.edu_job_id
