from __future__ import annotations

import json

import pytest

from app.chat.tasks.task_store import TaskStore
from app.services.generation_command import (
    GenerationCommand,
    GenerationCommandService,
)
from app.services.job_store import JobKind, JobStatus, get_job


def test_generation_command_requires_owner_course_and_idempotency_key():
    with pytest.raises(ValueError):
        GenerationCommand(
            resource_type="flashcard",
            owner_user_id="",
            course_id="course-1",
            selected_doc_ids=["doc-1"],
            idempotency_key="request-1",
        )
    with pytest.raises(ValueError):
        GenerationCommand(
            resource_type="flashcard",
            owner_user_id="teacher",
            course_id="",
            selected_doc_ids=["doc-1"],
            idempotency_key="request-1",
        )


def test_generation_command_preserves_explicit_source_intent_and_deadline():
    command = GenerationCommand(
        resource_type="flashcard",
        owner_user_id="teacher",
        course_id="course-1",
        source_mode="none",
        selected_doc_ids=[],
        deadline_seconds=45,
        idempotency_key="request-1",
    )

    assert command.source_mode == "none"
    assert command.deadline_seconds == 45


def test_generation_command_infers_source_mode_for_legacy_payloads():
    selected = GenerationCommand.model_validate(
        {
            "resource_type": "quiz",
            "owner_user_id": "teacher",
            "course_id": "course-1",
            "selected_doc_ids": ["doc-1"],
            "idempotency_key": "selected",
        }
    )
    automatic = GenerationCommand.model_validate(
        {
            "resource_type": "quiz",
            "owner_user_id": "teacher",
            "course_id": "course-1",
            "selected_doc_ids": [],
            "idempotency_key": "automatic",
        }
    )

    assert selected.source_mode == "selected_documents"
    assert automatic.source_mode == "course_auto"


def test_generation_submit_persists_recoverable_owner_scoped_command(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.job_store.Config.STORAGE_ROOT",
        tmp_path / "jobs",
    )
    store = TaskStore(str(tmp_path / "tasks.db"))
    service = GenerationCommandService(
        task_store=store,
        snapshot_provider=lambda owner: {"llm": "user:revision-1"},
    )
    command = GenerationCommand(
        resource_type="flashcard",
        owner_user_id="teacher-a",
        course_id="course-1",
        selected_doc_ids=["doc-1"],
        config={"count": 8, "max_tokens": 1024},
        idempotency_key="request-1",
    )

    first = service.submit(command)
    second = service.submit(command)

    assert second.edu_job_id == first.edu_job_id
    assert first.kind == JobKind.GENERATE_FLASHCARD
    assert first.status == JobStatus.QUEUED
    task = store.get_durable(first.edu_job_id)
    assert task is not None
    assert task.status == "pending"
    assert task.workflow_type == "flashcard_direct"
    assert task.command["resource_type"] == "flashcard"
    assert task.command["runtime_config_snapshot"] == {
        "llm": "user:revision-1"
    }
    assert task.command["material_id"].startswith("flashcard-")
    assert task.command["config"]["max_tokens"] == 1024
    serialized = json.dumps(task.command).lower()
    assert "api_key" not in serialized
    assert "authorization" not in serialized
    store.close()


def test_generation_enqueue_failure_marks_public_job_failed(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.job_store.Config.STORAGE_ROOT",
        tmp_path / "jobs",
    )

    class FailingTaskStore:
        def enqueue(self, **kwargs):
            raise OSError("database is read only")

    service = GenerationCommandService(
        task_store=FailingTaskStore(),
        snapshot_provider=lambda owner: {},
    )
    command = GenerationCommand(
        resource_type="ppt",
        owner_user_id="teacher-a",
        course_id="course-1",
        selected_doc_ids=["doc-1"],
        idempotency_key="request-failed",
    )

    job = service.submit(command)
    failed = get_job(job.edu_job_id)

    assert failed is not None
    assert failed.status == JobStatus.FAILED
    assert failed.error_code == "TASK_ENQUEUE_FAILED"
    assert failed.error_message == "database is read only"
