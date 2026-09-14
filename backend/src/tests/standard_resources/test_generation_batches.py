from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from app.database import Base
from app.persistence.postgres_material_repository import PostgresMaterialRepository
from app.standard_resources.batch_service import StandardResourceBatchService
from app.standard_resources.repository import StandardResourceRepository, StandardResourceRuleError

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


def test_create_batch_separates_queue_and_execution_timeouts(repository) -> None:
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

    asyncio.run(
        service.create_batch(
            course_id="course-1",
            created_by="teacher",
            leaf_ids=["relationships-and-keys", "integrity-constraints"],
        )
    )

    assert [
        (
            call["item"]["standard_kind"],
            call["context"].get("deadline_seconds"),
            call["context"].get("execution_timeout_seconds"),
        )
        for call in submitted
    ] == [
        ("classroom", 86400, 3600),
        ("practice", 86400, 900),
        ("study_guide", 86400, 900),
        ("classroom", 86400, 3600),
        ("practice", 86400, 900),
        ("study_guide", 86400, 900),
    ]


def test_retry_failed_classroom_keeps_long_runtime_budget(repository) -> None:
    retry_budgets: list[tuple[int, int]] = []
    classroom_attempts = 0

    async def submit(item, context):
        nonlocal classroom_attempts
        if item["standard_kind"] == "classroom":
            classroom_attempts += 1
            if classroom_attempts == 1:
                raise RuntimeError("temporary classroom failure")
            retry_budgets.append(
                (
                    context["deadline_seconds"],
                    context["execution_timeout_seconds"],
                )
            )
        return SimpleNamespace(edu_job_id=f"job-{item['standard_kind']}-{classroom_attempts}")

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

    asyncio.run(
        service.retry_failed(
            course_id="course-1",
            batch_id=created["batch_id"],
            requested_by="teacher",
        )
    )

    assert retry_budgets == [(86400, 3600)]


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


def _seed_existing_resources(repository) -> PostgresMaterialRepository:
    materials = PostgresMaterialRepository(repository._engine)
    common = {
        "course_id": "course-1",
        "origin_type": "standard",
        "scope_type": "knowledge_point",
        "scope_id": "relationships-and-keys",
    }
    materials.upsert({
        **common,
        "material_type": "report",
        "material_id": "standard-relationships-and-keys-study_guide",
        "standard_kind": "study_guide",
        "title": "学习指南",
        "version": 2,
        "approved_version": 2,
        "current_review_status": "approved",
        "review_status": "approved",
        "content_hash": "guide-v2",
        "content": "已批准指南内容",
    })
    materials.upsert({
        **common,
        "material_type": "quiz",
        "material_id": "standard-relationships-and-keys-practice",
        "standard_kind": "practice",
        "title": "练习",
        "version": 3,
        "current_review_status": "rejected",
        "review_status": "rejected",
        "rejection_reason": "答案解析没有说明候选键与主键的区别",
        "content_hash": "practice-v3",
        "content": {"questions": []},
    })
    return materials


def test_preview_distinguishes_missing_rejected_and_existing_resources(repository) -> None:
    materials = _seed_existing_resources(repository)
    service = StandardResourceBatchService(
        repository=repository,
        graph_lookup=lambda _course_id: GRAPH,
        submitter=lambda _item, _context: None,
        job_lookup=lambda _job_id: None,
        material_list=materials.list,
        material_get=materials.get,
        version_lookup=materials.get_version,
    )

    fill = service.preview_batch(
        course_id="course-1",
        leaf_ids=["relationships-and-keys"],
        mode="fill_missing",
    )
    assert (fill["generate_items"], fill["kept_items"], fill["actionable_items"]) == (1, 2, 1)

    repair = service.preview_batch(
        course_id="course-1",
        leaf_ids=["relationships-and-keys"],
        mode="repair_rejected",
    )
    assert (repair["generate_items"], repair["repair_items"], repair["kept_items"]) == (1, 1, 1)
    repaired = next(item for item in repair["items"] if item["action"] == "repair")
    assert repaired["base_version"] == 3
    assert "候选键与主键" in repaired["generation_context"]["rejection_reason"]
    assert "questions" in repaired["generation_context"]["baseline_summary"]

    regenerate = service.preview_batch(
        course_id="course-1",
        leaf_ids=["relationships-and-keys"],
        standard_kinds=["study_guide"],
        mode="regenerate_all",
    )
    assert regenerate["regenerate_items"] == 1
    assert regenerate["actionable_items"] == 1

    with pytest.raises(StandardResourceRuleError) as error:
        asyncio.run(service.create_batch(
            course_id="course-1",
            created_by="teacher",
            leaf_ids=["relationships-and-keys"],
            standard_kinds=["study_guide"],
            mode="fill_missing",
            idempotency_key="empty-plan",
        ))
    assert error.value.code == "NO_ACTIONABLE_RESOURCES"

    materials.upsert({
        "course_id": "course-1",
        "material_type": "report",
        "material_id": "standard-relationships-and-keys-study_guide",
        "standard_kind": "study_guide",
        "origin_type": "standard",
        "title": "待审核学习指南",
        "version": 3,
        "approved_version": 2,
        "current_review_status": "pending",
        "review_status": "pending",
        "content_hash": "guide-v3",
        "content": "待审核候选",
    })
    blocked = service.preview_batch(
        course_id="course-1",
        leaf_ids=["relationships-and-keys"],
        standard_kinds=["study_guide"],
        mode="regenerate_all",
    )
    assert blocked["blocked_items"] == 1
    assert blocked["actionable_items"] == 0


def test_create_batch_is_idempotent_and_does_not_resubmit(repository) -> None:
    submissions = 0

    async def submit(_item, _context):
        nonlocal submissions
        submissions += 1
        return SimpleNamespace(edu_job_id=f"job-{submissions}")

    service = StandardResourceBatchService(
        repository=repository,
        graph_lookup=lambda _course_id: GRAPH,
        submitter=submit,
        job_lookup=lambda _job_id: None,
    )
    request = dict(
        course_id="course-1",
        created_by="teacher",
        leaf_ids=["relationships-and-keys"],
        idempotency_key="browser-confirm-1",
    )
    first = asyncio.run(service.create_batch(**request))
    second = asyncio.run(service.create_batch(**request))

    assert second["batch_id"] == first["batch_id"]
    assert submissions == 3


def test_create_rejects_stale_graph_preview(repository) -> None:
    service = StandardResourceBatchService(
        repository=repository,
        graph_lookup=lambda _course_id: GRAPH,
        submitter=lambda _item, _context: None,
        job_lookup=lambda _job_id: None,
    )
    preview = service.preview_batch(
        course_id="course-1", leaf_ids=["relationships-and-keys"]
    )
    changed_graph = {**GRAPH, "version": "newer-graph"}
    service.graph_lookup = lambda _course_id: changed_graph

    with pytest.raises(StandardResourceRuleError) as error:
        asyncio.run(service.create_batch(
            course_id="course-1",
            created_by="teacher",
            leaf_ids=["relationships-and-keys"],
            idempotency_key="stale-preview",
            expected_graph_version=preview["graph_version"],
        ))
    assert error.value.code == "GRAPH_VERSION_CHANGED"


def test_succeeded_jobs_bind_exact_material_version_and_hash(repository) -> None:
    submitted: list[dict] = []

    async def submit(item, context):
        job_id = f"job-{item['standard_kind']}"
        submitted.append({"item": item, "context": context, "job_id": job_id})
        return SimpleNamespace(edu_job_id=job_id)

    def lookup(job_id):
        return SimpleNamespace(
            status="succeeded",
            result_ref={"version": 4, "content_hash": f"hash-{job_id}"},
        )

    def material_get(_course_id, material_type, material_id):
        call = next(item for item in submitted if item["item"]["material_id"] == material_id)
        return {
            "material_type": material_type,
            "material_id": material_id,
            "version": 4,
            "content_hash": f"hash-{call['job_id']}",
            "generation_batch_id": call["context"]["generation_batch_id"],
            "source_job_id": call["job_id"],
        }

    service = StandardResourceBatchService(
        repository=repository,
        graph_lookup=lambda _course_id: GRAPH,
        submitter=submit,
        job_lookup=lookup,
        material_get=material_get,
    )
    result = asyncio.run(service.create_batch(
        course_id="course-1",
        created_by="teacher",
        leaf_ids=["relationships-and-keys"],
        idempotency_key="bind-result",
    ))

    assert result["status"] == "completed"
    assert {item["material_version"] for item in result["items"]} == {4}
    assert {item["content_hash"] for item in result["items"]} == {
        "hash-job-classroom", "hash-job-study_guide", "hash-job-practice"
    }
