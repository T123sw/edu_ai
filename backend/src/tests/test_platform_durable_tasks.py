import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.chat.tasks.task_store import TaskStore
from app.services import classroom_service
from app.services import classroom_video_export
from app.services import knowledge_document_service
from app.services import video_service
from app.services.job_store import JobKind, create_job
from app.services.platform_task_handlers import (
    PlatformTaskHandlers,
    enqueue_platform_task,
    register_platform_task_handlers,
)
from app.services.durable_task_handlers import (
    DurableExecutionContext,
    DurableTaskHandlerRegistry,
)
from app.services.durable_task_executor import DurableTaskExecutor
from app.services.job_completion_service import JobCompletionService
from app.services.job_store import JobStatus, get_job
from core.course_storage import CourseStorageManager
from core import Config


def test_platform_commands_are_persisted_without_live_dependencies(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    job = create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        edu_job_id="job-platform-1",
        owner_user_id="teacher-a",
        course_id="course-1",
    )

    enqueue_platform_task(
        job=job,
        workflow_type="classroom_generate",
        command={
            "course_id": "course-1",
            "requirement": "Explain recursion",
            "enable_tts": True,
        },
        task_store=store,
    )

    durable = store.get_durable(job.edu_job_id)
    assert durable is not None
    assert durable.status == "pending"
    assert durable.command == {
        "course_id": "course-1",
        "requirement": "Explain recursion",
        "enable_tts": True,
    }
    store.close()


def test_platform_registry_exposes_all_four_workflows():
    registry = DurableTaskHandlerRegistry()

    register_platform_task_handlers(registry)

    for workflow in (
        "classroom_generate",
        "classroom_video_export",
        "rag_document_index",
        "video_ingest",
    ):
        assert registry.resolve(workflow, 1) is not None


def test_classroom_submission_does_not_build_research_in_request(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "storage")
    captured = {}

    def capture(**kwargs):
        captured.update(kwargs)
        return kwargs["job"]

    monkeypatch.setattr(
        "app.services.platform_task_handlers.enqueue_platform_task",
        capture,
    )
    monkeypatch.setattr(
        classroom_service,
        "_build_research_context",
        lambda **_: (_ for _ in ()).throw(
            AssertionError("research must run in the worker")
        ),
    )

    job = asyncio.run(
        classroom_service.submit_classroom_generation_job(
            course_id="course-1",
            requirement="Explain recursion",
            owner="teacher-a",
            course_storage_manager=SimpleNamespace(),
            enable_web_search=True,
            enable_tts=True,
        )
    )

    assert job.status.value == "queued"
    assert captured["workflow_type"] == "classroom_generate"
    assert captured["command"]["requirement"] == "Explain recursion"
    assert "client" not in captured["command"]
    assert "course_storage_manager" not in captured["command"]


def test_rag_submission_persists_document_identity_not_rag_client(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "storage")
    captured = {}
    records = [
        {
            "id": "doc-1",
            "filename": "lesson.pdf",
            "scope_type": "course",
        }
    ]

    class Manager:
        def get_knowledge_base_index(self, course_id):
            return list(records)

        def save_knowledge_base_index(self, course_id, value):
            records[:] = value
            return True

    def capture(**kwargs):
        captured.update(kwargs)
        return kwargs["job"]

    monkeypatch.setattr(
        "app.services.platform_task_handlers.enqueue_platform_task",
        capture,
    )

    job = knowledge_document_service.submit_index_job(
        manager=Manager(),
        rag_system=object(),
        course_id="course-1",
        document_id="doc-1",
        owner_user_id="teacher-a",
        force_reindex=False,
    )

    assert job.status.value == "queued"
    assert captured["workflow_type"] == "rag_document_index"
    assert captured["command"]["document_id"] == "doc-1"
    assert "rag_system" not in captured["command"]
    assert "manager" not in captured["command"]


def test_personal_rag_handler_uses_owner_scoped_storage_factory(monkeypatch):
    personal_manager = object()
    captured = {}
    job = create_job(
        kind=JobKind.RAG_IMPORT,
        edu_job_id="job-personal-rag-handler",
        owner_user_id="student-a",
        course_id="personal:student-a",
    )

    def run_index_job(**kwargs):
        captured.update(kwargs)
        from app.services.job_store import update_job

        update_job(
            job.edu_job_id,
            status=JobStatus.SUCCEEDED,
            result_ref={"document_id": "doc-1"},
        )

    monkeypatch.setattr(knowledge_document_service, "run_index_job", run_index_job)
    handler = PlatformTaskHandlers(
        personal_storage_factory=lambda owner: (
            personal_manager if owner == "student-a" else None
        )
    )
    context = DurableExecutionContext(
        task_id=job.edu_job_id,
        owner_user_id="student-a",
        course_id="personal:student-a",
        config_snapshot_id=None,
        progress=lambda *_args: None,
        is_cancel_requested=lambda: False,
    )

    result = handler.rag_document_index(
        {
            "storage_scope": "personal",
            "course_id": "personal:student-a",
            "document_id": "doc-1",
            "pending_version": "idx-1",
        },
        context,
    )

    assert result["saved"] is True
    assert captured["manager"] is personal_manager
    assert captured["owner_user_id"] == "student-a"


def test_video_ingestion_command_uses_a_user_relative_path(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "storage")
    monkeypatch.setattr(Config, "VIDEOS_ROOT", tmp_path / "videos")
    captured = {}
    video = Config.VIDEOS_ROOT / "teacher-a" / "course-1" / "clip.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")

    def capture(**kwargs):
        captured.update(kwargs)
        return kwargs["job"]

    monkeypatch.setattr(
        "app.services.platform_task_handlers.enqueue_platform_task",
        capture,
    )

    job = video_service.create_video_ingestion_job(
        video_path=video,
        course_id="course-1",
        owner="teacher-a",
        original_filename="clip.mp4",
        window_seconds=30,
        stride_seconds=20,
        config_snapshot={"embedding": "revision-1"},
    )

    assert job.status.value == "queued"
    assert captured["workflow_type"] == "video_ingest"
    assert captured["command"]["video_rel_path"] == "course-1/clip.mp4"
    assert not Path(captured["command"]["video_rel_path"]).is_absolute()


def test_video_export_submission_never_persists_bearer_token(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "storage")
    captured = {}

    def capture(**kwargs):
        captured.update(kwargs)
        return kwargs["job"]

    monkeypatch.setattr(
        "app.services.platform_task_handlers.enqueue_platform_task",
        capture,
    )

    job = asyncio.run(
        classroom_video_export.submit_classroom_video_export_job(
            course_id="course-1",
            classroom_id="classroom-1",
            auth_token="must-not-persist",
            current_user={"username": "teacher-a", "role": "teacher"},
            owner="teacher-a",
            course_storage_manager=SimpleNamespace(),
        )
    )

    assert job.status.value == "queued"
    assert captured["workflow_type"] == "classroom_video_export"
    serialized = str(captured["command"])
    assert "must-not-persist" not in serialized
    assert "auth_token" not in captured["command"]


def test_worker_executes_a_persisted_video_ingestion_after_request_end(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "storage")
    monkeypatch.setattr(Config, "VIDEOS_ROOT", tmp_path / "videos")
    monkeypatch.setattr(Config, "VIDEO_CHUNKS_ROOT", tmp_path / "chunks")
    store = TaskStore(str(tmp_path / "tasks.db"))
    monkeypatch.setattr(
        "app.services.platform_task_handlers.get_task_store",
        lambda: store,
    )
    video = Config.VIDEOS_ROOT / "teacher-a" / "course-1" / "clip.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")

    class Ingester:
        def ingest(self, *, video_path, course_id):
            assert Path(video_path) == video.resolve()
            assert course_id == "course-1"
            return {"chunks": 2}

    monkeypatch.setattr(
        video_service,
        "make_ingester",
        lambda **_: Ingester(),
    )
    job = video_service.create_video_ingestion_job(
        video_path=video,
        course_id="course-1",
        owner="teacher-a",
        original_filename="clip.mp4",
        window_seconds=30,
        stride_seconds=20,
    )
    registry = DurableTaskHandlerRegistry()
    register_platform_task_handlers(registry)
    manager = CourseStorageManager(str(tmp_path / "courses"))
    executor = DurableTaskExecutor(
        task_store=store,
        handler_registry=registry,
        completion_service=JobCompletionService(
            task_store=store,
            course_storage_manager=manager,
        ),
        lease_seconds=2,
        heartbeat_interval=0.1,
        poll_interval=0.01,
    )

    assert executor.run_once() is True

    durable = store.get_durable(job.edu_job_id)
    public = get_job(job.edu_job_id)
    assert durable is not None
    assert durable.status == "succeeded"
    assert public is not None
    assert public.status == JobStatus.SUCCEEDED
    assert public.result_ref["chunks"] == 2
    store.close()
