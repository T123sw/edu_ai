import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services import job_store
from app.services.job_store import JobKind, JobStatus
from core import Config


@pytest.fixture(autouse=True)
def _isolated_jobs(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path)


def test_v2_job_records_owner_scope_safe_input_and_version():
    created = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"title": "二分查找", "api_key": "must-not-persist"},
    )

    assert created.schema_version == 2
    assert created.owner_user_id == "teacher-a"
    assert created.owner == "teacher-a"
    assert created.course_id == "course-1"
    assert created.input_summary == {"title": "二分查找"}
    assert created.version == 1
    stored = json.loads(
        (Config.STORAGE_ROOT / "jobs" / f"{created.edu_job_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert "must-not-persist" not in json.dumps(stored)


def test_reads_v1_owner_and_normalizes_legacy_classroom_result():
    jobs_root = Config.STORAGE_ROOT / "jobs"
    jobs_root.mkdir(parents=True)
    (jobs_root / "legacy.json").write_text(
        json.dumps(
            {
                "edu_job_id": "legacy",
                "kind": "generate_classroom",
                "status": "succeeded",
                "step": "completed",
                "progress": 100,
                "message": "done",
                "owner": "teacher-a",
                "result_ref": {
                    "course_id": "course-1",
                    "classroom_id": "classroom-1",
                    "scenes_count": 3,
                },
                "created_at": "2026-08-06T00:00:00+00:00",
                "updated_at": "2026-08-06T00:01:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    loaded = job_store.get_job("legacy")

    assert loaded is not None
    assert loaded.schema_version == 1
    assert loaded.owner_user_id == "teacher-a"
    assert loaded.result_ref["resource_type"] == "course_material"
    assert loaded.result_ref["material_type"] == "classroom"
    assert loaded.result_ref["material_id"] == "classroom-1"


def test_owner_filters_active_status_and_cursor_pagination():
    first = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM, owner_user_id="teacher-a"
    )
    second = job_store.create_job(
        kind=JobKind.RENDER_VIDEO, owner_user_id="teacher-a"
    )
    job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM, owner_user_id="teacher-b"
    )
    job_store.update_job(first.edu_job_id, status=JobStatus.FAILED)

    active_page = job_store.list_job_page(
        owner_user_id="teacher-a", active_only=True, limit=10
    )
    assert [item.edu_job_id for item in active_page.items] == [second.edu_job_id]

    page_one = job_store.list_job_page(owner_user_id="teacher-a", limit=1)
    page_two = job_store.list_job_page(
        owner_user_id="teacher-a", limit=1, cursor=page_one.next_cursor
    )
    assert len(page_one.items) == len(page_two.items) == 1
    assert page_one.items[0].edu_job_id != page_two.items[0].edu_job_id


def test_cancel_and_retry_keep_history_and_relationship():
    running = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"title": "课堂一"},
    )
    running = job_store.update_job(running.edu_job_id, status=JobStatus.RUNNING)
    canceled = job_store.cancel_job(running.edu_job_id, owner_user_id="teacher-a")
    assert canceled.status == JobStatus.CANCEL_REQUESTED

    failed = job_store.create_job(
        kind=JobKind.RENDER_VIDEO,
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"classroom_id": "classroom-1"},
    )
    job_store.update_job(failed.edu_job_id, status=JobStatus.FAILED)
    retried = job_store.retry_job(failed.edu_job_id, owner_user_id="teacher-a")

    assert retried.edu_job_id != failed.edu_job_id
    assert retried.retry_of_job_id == failed.edu_job_id
    assert retried.input_summary == {"classroom_id": "classroom-1"}
    assert job_store.get_job(failed.edu_job_id).status == JobStatus.FAILED


def test_wrong_owner_cannot_cancel_or_retry():
    job = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM, owner_user_id="teacher-a"
    )
    with pytest.raises(PermissionError):
        job_store.cancel_job(job.edu_job_id, owner_user_id="teacher-b")
    job_store.update_job(job.edu_job_id, status=JobStatus.FAILED)
    with pytest.raises(PermissionError):
        job_store.retry_job(job.edu_job_id, owner_user_id="teacher-b")


def test_concurrent_updates_produce_one_complete_json_record():
    created = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM, owner_user_id="teacher-a"
    )

    def update(progress):
        return job_store.update_job(
            created.edu_job_id,
            status=JobStatus.RUNNING,
            progress=progress,
            message=f"progress-{progress}",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(update, range(1, 41)))

    loaded = job_store.get_job(created.edu_job_id)
    assert loaded is not None
    assert all(result is not None for result in results)
    assert loaded.version == 41
    assert 1 <= loaded.progress <= 40


def test_failed_atomic_replace_preserves_the_previous_record(monkeypatch):
    created = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM, owner_user_id="teacher-a"
    )

    def fail_replace(source, target):
        raise OSError("disk unavailable")

    monkeypatch.setattr(job_store.os, "replace", fail_replace)
    with pytest.raises(OSError):
        job_store.update_job(created.edu_job_id, progress=50)

    loaded = job_store.get_job(created.edu_job_id)
    assert loaded is not None
    assert loaded.progress == 0
    assert loaded.version == 1


def test_corrupt_json_is_skipped_without_breaking_the_list():
    valid = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM, owner_user_id="teacher-a"
    )
    (Config.STORAGE_ROOT / "jobs" / "corrupt.json").write_text(
        '{"edu_job_id":', encoding="utf-8"
    )

    page = job_store.list_job_page(owner_user_id="teacher-a")
    assert [item.edu_job_id for item in page.items] == [valid.edu_job_id]
