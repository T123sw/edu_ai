from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.database import Base
from app.persistence.postgres_material_repository import PostgresMaterialRepository
from app.standard_resources.models import extract_leaf_nodes
from app.standard_resources.repository import (
    StandardResourceRepository,
    StandardResourceRuleError,
)

from .test_models import GRAPH


@pytest.fixture
def repositories(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'standard.db').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        yield StandardResourceRepository(engine), PostgresMaterialRepository(engine)
    finally:
        engine.dispose()


def test_batch_contains_three_items_for_each_selected_leaf(repositories) -> None:
    repository, _materials = repositories
    leaves = extract_leaf_nodes(GRAPH)[:2]

    batch = repository.create_batch(
        course_id="course-1",
        created_by="teacher",
        leaves=leaves,
    )

    assert batch["total_items"] == 6
    assert len(batch["items"]) == 6
    assert {
        (item["leaf_id"], item["standard_kind"]) for item in batch["items"]
    } == {
        (leaf.leaf_id, kind)
        for leaf in leaves
        for kind in ("classroom", "study_guide", "practice")
    }


def test_approving_pending_version_keeps_explicit_approved_pointer(repositories) -> None:
    repository, materials = repositories
    material_id = "standard-relationships-and-keys-study_guide"
    materials.upsert(
        {
            "course_id": "course-1",
            "material_type": "report",
            "material_id": material_id,
            "title": "关系与键学习指南",
            "origin_type": "standard",
            "standard_kind": "study_guide",
            "generation_batch_id": "batch-1",
            "current_review_status": "pending",
            "scope_type": "knowledge_point",
            "scope_id": "relationships-and-keys",
            "version": 1,
            "content": "version one",
        }
    )

    approved = repository.review_material(
        course_id="course-1",
        material_id=material_id,
        reviewer_id="teacher",
        decision="approved",
    )

    assert approved["approved_version"] == 1
    assert approved["current_review_status"] == "approved"
    version = materials.get_version("course-1", "report", material_id, 1)
    assert version["review_status"] == "approved"
    with pytest.raises(StandardResourceRuleError) as error:
        repository.review_material(
            course_id="course-1",
            material_id=material_id,
            reviewer_id="teacher",
            decision="approved",
        )
    assert error.value.code == "VERSION_NOT_PENDING"


def test_rejecting_new_version_does_not_remove_old_approved_pointer(repositories) -> None:
    repository, materials = repositories
    material_id = "standard-leaf-practice"
    base = {
        "course_id": "course-1",
        "material_type": "quiz",
        "material_id": material_id,
        "title": "练习",
        "origin_type": "standard",
        "standard_kind": "practice",
        "generation_batch_id": "batch-1",
        "scope_type": "knowledge_point",
        "scope_id": "leaf",
    }
    materials.upsert(
        {
            **base,
            "version": 1,
            "current_review_status": "pending",
            "content": "one",
        }
    )
    repository.review_material(
        course_id="course-1",
        material_id=material_id,
        reviewer_id="teacher",
        decision="approved",
    )
    materials.upsert(
        {
            **base,
            "version": 2,
            "current_review_status": "pending",
            "approved_version": 1,
            "content": "two",
        }
    )

    rejected = repository.review_material(
        course_id="course-1",
        material_id=material_id,
        reviewer_id="teacher",
        decision="rejected",
        reason="内容不准确",
    )

    assert rejected["approved_version"] == 1
    assert rejected["current_review_status"] == "rejected"
