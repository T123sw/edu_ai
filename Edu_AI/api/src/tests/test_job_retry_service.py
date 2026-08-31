import asyncio

from app.services import job_retry_service, job_store
from app.services.job_store import JobKind
from core import Config


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
