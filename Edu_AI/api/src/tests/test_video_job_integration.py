import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services import job_store, video_service
from app.services.job_store import JobKind, JobStatus
from core import Config


@pytest.fixture(autouse=True)
def _isolated_storage(monkeypatch, tmp_path):
    from app.chat.tasks.task_store import TaskStore

    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "storage")
    monkeypatch.setattr(Config, "VIDEOS_ROOT", tmp_path / "videos")
    monkeypatch.setattr(Config, "VIDEO_CHUNKS_ROOT", tmp_path / "chunks")
    task_store = TaskStore(str(tmp_path / "tasks.db"))
    monkeypatch.setattr(
        "app.services.platform_task_handlers.get_task_store",
        lambda: task_store,
    )
    yield task_store
    task_store.close()


def test_video_ingestion_uses_durable_global_job_and_relative_path():
    video_path = Config.VIDEOS_ROOT / "teacher-a" / "course-1" / "lesson.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"video")

    created = video_service.create_video_ingestion_job(
        video_path=video_path,
        course_id="course-1",
        owner="teacher-a",
        original_filename="lesson.mp4",
        window_seconds=30,
        stride_seconds=20,
        config_snapshot={"embedding": "user:rev-1"},
    )

    assert created.kind == JobKind.INGEST_VIDEO
    assert created.owner_user_id == "teacher-a"
    assert created.input_summary["video_rel_path"] == "course-1/lesson.mp4"
    assert str(Config.VIDEOS_ROOT) not in str(created.input_summary)
    assert job_store.get_job(created.edu_job_id) is not None


def test_video_ingestion_publishes_terminal_result(monkeypatch):
    video_path = Config.VIDEOS_ROOT / "teacher-a" / "course-1" / "lesson.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"video")
    created = video_service.create_video_ingestion_job(
        video_path=video_path,
        course_id="course-1",
        owner="teacher-a",
        original_filename="lesson.mp4",
        window_seconds=30,
        stride_seconds=20,
    )

    class FakeIngester:
        def ingest(self, *, video_path, course_id):
            assert Path(video_path) == video_path_obj
            assert course_id == "course-1"
            return {"chunks": 4}

    video_path_obj = video_path.resolve()
    monkeypatch.setattr(video_service, "make_ingester", lambda **kwargs: FakeIngester())

    video_service.run_video_ingestion_job(created.edu_job_id)

    finished = job_store.get_job(created.edu_job_id)
    assert finished is not None
    assert finished.status == JobStatus.SUCCEEDED
    assert finished.result_ref == {
        "resource_type": "video_document",
        "course_id": "course-1",
        "video_rel_path": "course-1/lesson.mp4",
        "chunks": 4,
    }


def test_video_ingestion_honors_cancel_before_start(monkeypatch):
    video_path = Config.VIDEOS_ROOT / "teacher-a" / "course-1" / "lesson.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"video")
    created = video_service.create_video_ingestion_job(
        video_path=video_path,
        course_id="course-1",
        owner="teacher-a",
        original_filename="lesson.mp4",
        window_seconds=30,
        stride_seconds=20,
    )
    job_store.cancel_job(created.edu_job_id, owner_user_id="teacher-a")

    def fail_if_called(**kwargs):
        raise AssertionError("canceled queued job must not start ingestion")

    monkeypatch.setattr(video_service, "make_ingester", fail_if_called)
    video_service.run_video_ingestion_job(created.edu_job_id)

    assert job_store.get_job(created.edu_job_id).status == JobStatus.CANCELED
