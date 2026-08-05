import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.api import jobs as jobs_api
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
    return TestClient(app)


def test_list_api_is_owner_scoped_and_paginated(client):
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
