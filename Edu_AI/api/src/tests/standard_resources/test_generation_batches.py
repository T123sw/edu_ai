from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from app.database import Base
from app.standard_resources.batch_service import StandardResourceBatchService
from app.standard_resources.repository import StandardResourceRepository

from .test_models import GRAPH


@pytest.fixture
def repository(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'batch.db').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        yield StandardResourceRepository(engine)
    finally:
        engine.dispose()


def test_create_batch_submits_each_slot_with_stable_standard_metadata(repository) -> None:
    submitted: list[dict] = []

    async def submit(item, context):
        submitted.append({"item": item, "context": context})
        return SimpleNamespace(edu_job_id=f"job-{len(submitted)}")

    service = StandardResourceBatchService(
        repository=repository,
        graph_lookup=lambda _course_id: GRAPH,
        submitter=submit,
        job_lookup=lambda _job_id: None,
    )

    result = asyncio.run(
        service.create_batch(
            course_id="course-1",
            created_by="teacher",
            leaf_ids=["relationships-and-keys"],
        )
    )

    assert result["total_items"] == 3
    assert result["running_items"] == 3
    assert {call["context"]["origin_type"] for call in submitted} == {"standard"}
    assert {call["context"]["scope_type"] for call in submitted} == {"knowledge_point"}
    assert {call["item"]["material_id"] for call in submitted} == {
        "standard-relationships-and-keys-classroom",
        "standard-relationships-and-keys-study_guide",
        "standard-relationships-and-keys-practice",
    }


def test_retry_submits_only_failed_items(repository) -> None:
    call_count = 0

    async def submit(item, _context):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("provider unavailable")
        return SimpleNamespace(edu_job_id=f"job-{call_count}")

    service = StandardResourceBatchService(
        repository=repository,
        graph_lookup=lambda _course_id: GRAPH,
        submitter=submit,
        job_lookup=lambda _job_id: None,
    )
    created = asyncio.run(
        service.create_batch(
            course_id="course-1",
            created_by="teacher",
            leaf_ids=["relationships-and-keys"],
        )
    )
    assert created["failed_items"] == 1

    asyncio.run(
        service.retry_failed(
            course_id="course-1",
            batch_id=created["batch_id"],
            requested_by="teacher",
        )
    )

    assert call_count == 4
