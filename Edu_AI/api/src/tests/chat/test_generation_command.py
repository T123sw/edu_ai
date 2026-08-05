from __future__ import annotations

import time

import pytest

from app.services.generation_command import (
    GenerationCommand,
    GenerationCommandService,
)
from app.services.job_store import JobKind, JobStatus, get_job


def _wait_for_terminal(job_id: str):
    for _ in range(100):
        job = get_job(job_id)
        if job and job.status not in {
            JobStatus.QUEUED,
            JobStatus.RUNNING,
            JobStatus.CANCEL_REQUESTED,
        }:
            return job
        time.sleep(0.01)
    raise AssertionError("generation command did not finish")


def test_generation_command_requires_owner_course_sources_and_idempotency_key():
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
    with pytest.raises(ValueError):
        GenerationCommand(
            resource_type="flashcard",
            owner_user_id="teacher",
            course_id="course-1",
            selected_doc_ids=[],
            idempotency_key="request-1",
        )


def test_generation_command_is_owner_scoped_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.job_store.Config.STORAGE_ROOT", tmp_path)
    service = GenerationCommandService()
    calls = []

    def handler(command, job_id, config_snapshot_id):
        calls.append((command.owner_user_id, job_id, config_snapshot_id))
        return {
            "saved": True,
            "result_ref": {
                "resource_type": "course_material",
                "course_id": command.course_id,
                "material_type": command.resource_type,
                "material_id": "deck-1",
            },
        }

    command = GenerationCommand(
        resource_type="flashcard",
        owner_user_id="teacher-a",
        course_id="course-1",
        selected_doc_ids=["doc-1"],
        config={"count": 8},
        idempotency_key="request-1",
    )
    first = service.submit(command, handler)
    second = service.submit(command, handler)
    assert second.edu_job_id == first.edu_job_id
    finished = _wait_for_terminal(first.edu_job_id)
    assert finished.status == JobStatus.SUCCEEDED
    assert finished.kind == JobKind.GENERATE_FLASHCARD
    assert finished.result_ref["material_id"] == "deck-1"
    assert len(calls) == 1


def test_generation_command_marks_save_failure_partially_succeeded(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.job_store.Config.STORAGE_ROOT", tmp_path)
    service = GenerationCommandService()
    command = GenerationCommand(
        resource_type="ppt",
        owner_user_id="teacher-a",
        course_id="course-1",
        selected_doc_ids=["doc-1"],
        idempotency_key="request-partial",
    )
    job = service.submit(
        command,
        lambda *_: {
            "saved": False,
            "error": "manifest write failed",
            "result_ref": {"resource_type": "generated_artifact"},
        },
    )
    finished = _wait_for_terminal(job.edu_job_id)
    assert finished.status == JobStatus.PARTIALLY_SUCCEEDED
    assert finished.retryable is True
    assert finished.error_code == "RESOURCE_SAVE_FAILED"

