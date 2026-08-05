import sys
import time
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.chat.tasks import background_runner
from app.chat.tasks.task_store import TaskStore
from app.services import job_store
from app.services.job_store import JobKind, JobStatus
from core import Config


@pytest.fixture()
def isolated_stores(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "storage")
    task_store = TaskStore(str(tmp_path / "tasks.db"))
    monkeypatch.setattr(background_runner, "get_task_store", lambda: task_store)
    return task_store


def test_owner_scoped_task_store_rejects_another_teacher(isolated_stores):
    task_id = isolated_stores.create(
        workflow_type="report_direct",
        owner_user_id="teacher-a",
    )

    assert isolated_stores.get(task_id, owner_user_id="teacher-a") is not None
    assert isolated_stores.get(task_id, owner_user_id="teacher-b") is None


def test_callable_task_is_mirrored_to_the_global_job_ledger(isolated_stores):
    task_id = background_runner.submit_callable_task(
        fn=lambda: {
            "status": "completed",
            "artifacts": [{"artifact_type": "report", "id": "report-1"}],
        },
        workflow_type="report_direct",
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"title": "课堂观察报告"},
    )

    deadline = time.time() + 3
    task = None
    while time.time() < deadline:
        task = isolated_stores.get(task_id, owner_user_id="teacher-a")
        if task and task["status"] == "completed":
            break
        time.sleep(0.02)

    mirrored = job_store.get_job(task_id)
    assert task is not None and task["status"] == "completed"
    assert mirrored is not None
    assert mirrored.kind == JobKind.GENERATE_REPORT
    assert mirrored.owner_user_id == "teacher-a"
    assert mirrored.course_id == "course-1"
    assert mirrored.status == JobStatus.SUCCEEDED
    assert mirrored.result_ref["resource_type"] == "course_material"
    assert mirrored.result_ref["course_id"] == "course-1"


def test_callable_failure_is_visible_in_the_global_job_ledger(isolated_stores):
    def fail():
        raise RuntimeError("provider unavailable")

    task_id = background_runner.submit_callable_task(
        fn=fail,
        workflow_type="quiz_direct",
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"title": "章节练习"},
    )

    deadline = time.time() + 3
    mirrored = None
    while time.time() < deadline:
        mirrored = job_store.get_job(task_id)
        if mirrored and mirrored.status == JobStatus.FAILED:
            break
        time.sleep(0.02)

    assert mirrored is not None
    assert mirrored.kind == JobKind.GENERATE_QUIZ
    assert mirrored.status == JobStatus.FAILED
    assert mirrored.error_message == "provider unavailable"
