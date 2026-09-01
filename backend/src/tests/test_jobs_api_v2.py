import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.api import jobs as jobs_api
from app.chat.tasks.task_store import TaskStore
from app.services import job_store
from app.services.job_store import JobKind, JobStatus
from core import Config


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path)

    async def keep_retry_queued(job, **kwargs):
        return job

    monkeypatch.setattr(jobs_api, "dispatch_retry_job", keep_retry_queued)
    app = FastAPI()
    app.include_router(jobs_api.router)
    app.dependency_overrides[jobs_api.get_current_user] = lambda: {
        "username": "teacher-a",
        "role": "teacher",
    }
    task_store = TaskStore(str(tmp_path / "tasks.db"))
    monkeypatch.setattr(jobs_api, "get_task_store", lambda: task_store)
    with TestClient(app) as active_client:
        yield active_client, task_store
    task_store.close()


def test_list_api_is_owner_scoped_and_paginated(client):
    client, _ = client
    visible = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id="teacher-a",
        course_id="course-1",
    )
    job_store.create_job(
        kind=JobKind.RENDER_VIDEO,
        owner_user_id="teacher-b",
        course_id="course-1",
    )

    response = client.get("/api/jobs", params={"active_only": "true", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert [item["edu_job_id"] for item in payload["items"]] == [
        visible.edu_job_id
    ]
    assert payload["server_time"]
    assert payload["next_cursor"] is None


def test_detail_cancel_retry_and_cross_owner_protection(client):
    client, _ = client
    running = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM, owner_user_id="teacher-a"
    )
    job_store.update_job(running.edu_job_id, status=JobStatus.RUNNING)
    forbidden = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM, owner_user_id="teacher-b"
    )

    detail = client.get(f"/api/jobs/{running.edu_job_id}")
    canceled = client.post(f"/api/jobs/{running.edu_job_id}/cancel")
    forbidden_detail = client.get(f"/api/jobs/{forbidden.edu_job_id}")

    assert detail.status_code == 200
    assert "sidecar_job_id" not in detail.json()
    assert "provider_job_ref" not in detail.json()
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "cancel_requested"
    assert forbidden_detail.status_code == 403

    failed = job_store.create_job(
        kind=JobKind.RENDER_VIDEO,
        owner_user_id="teacher-a",
        input_summary={"classroom_id": "classroom-1"},
    )
    job_store.update_job(failed.edu_job_id, status=JobStatus.FAILED)
    retried = client.post(f"/api/jobs/{failed.edu_job_id}/retry")

    assert retried.status_code == 202
    assert retried.json()["retry_of_job_id"] == failed.edu_job_id
    assert retried.json()["edu_job_id"] != failed.edu_job_id


def test_cancel_updates_the_durable_task_before_public_status(client):
    client, task_store = client
    queued = job_store.create_job(
        kind=JobKind.GENERATE_REPORT,
        owner_user_id="teacher-a",
        course_id="course-1",
    )
    task_store.enqueue(
        task_id=queued.edu_job_id,
        workflow_type="report_direct",
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command={"resource_type": "report", "title": "Report"},
        config_snapshot_id="cfg-1",
        idempotency_key="request-1",
    )

    response = client.post(f"/api/jobs/{queued.edu_job_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
    assert task_store.get_durable(queued.edu_job_id).status == "canceled"


def test_retry_copies_the_durable_command_to_a_new_task(client):
    client, task_store = client
    failed = job_store.create_job(
        kind=JobKind.GENERATE_REPORT,
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"title": "Report"},
    )
    original_command = {
        "resource_type": "report",
        "course_id": "course-1",
        "material_id": "report-stable",
        "selected_doc_ids": ["doc-1"],
        "runtime_config_snapshot": {"llm": "revision-1"},
    }
    task_store.enqueue(
        task_id=failed.edu_job_id,
        workflow_type="report_direct",
        handler_version=1,
        owner_user_id="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        command=original_command,
        config_snapshot_id="cfg-1",
        idempotency_key="request-failed",
    )
    leased = task_store.claim_next(
        lease_owner="worker-a",
        lease_seconds=10,
    )
    assert leased is not None
    assert task_store.mark_failed(
        failed.edu_job_id,
        "provider failed",
        lease_owner="worker-a",
        error_code="PROVIDER_FAILED",
    )
    job_store.update_job(failed.edu_job_id, status=JobStatus.FAILED)

    response = client.post(f"/api/jobs/{failed.edu_job_id}/retry")

    assert response.status_code == 202
    retried_id = response.json()["edu_job_id"]
    assert retried_id != failed.edu_job_id
    retried_task = task_store.get_durable(retried_id)
    assert retried_task is not None
    assert retried_task.status == "pending"
    assert retried_task.command == original_command


def test_retry_rejects_a_job_that_did_not_enter_execution(client, monkeypatch):
    active_client, _ = client
    failed = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"requirement": "重试课堂"},
    )
    job_store.update_job(failed.edu_job_id, status=JobStatus.FAILED)

    async def reject_dispatch(job, **kwargs):
        return job_store.update_job(
            job.edu_job_id,
            status=JobStatus.FAILED,
            message="当前任务未能重新提交",
            error_message="当前任务未能重新提交",
        )

    monkeypatch.setattr(jobs_api, "dispatch_retry_job", reject_dispatch)

    response = active_client.post(f"/api/jobs/{failed.edu_job_id}/retry")

    assert response.status_code == 409
    assert response.json()["detail"] == "当前任务未能重新提交"


def test_retry_marks_new_job_failed_when_dispatch_raises(client, monkeypatch):
    active_client, _ = client
    active_client._transport.raise_server_exceptions = False
    failed = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"requirement": "重试课堂"},
    )
    job_store.update_job(failed.edu_job_id, status=JobStatus.FAILED)

    async def broken_dispatch(job, **kwargs):
        raise RuntimeError("worker unavailable")

    monkeypatch.setattr(jobs_api, "dispatch_retry_job", broken_dispatch)

    response = active_client.post(f"/api/jobs/{failed.edu_job_id}/retry")
    listed = active_client.get("/api/jobs").json()["items"]
    retry = next(
        item
        for item in listed
        if item.get("retry_of_job_id") == failed.edu_job_id
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "重试任务未能提交，请稍后再试"
    assert retry["status"] == "failed"
    assert retry["error_code"] == "RETRY_DISPATCH_FAILED"
