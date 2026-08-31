from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.database import Base
from app.persistence.postgres_material_repository import PostgresMaterialRepository
from app.resource_learning.repository import ResourceLearningRepository
from app.standard_resources.repository import StandardResourceRepository, StandardResourceRuleError
from app.standard_resources.review_service import StandardResourceReviewService


@pytest.fixture
def review_fixture(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'review.db').as_posix()}")
    Base.metadata.create_all(engine)
    materials = PostgresMaterialRepository(engine)
    learning = ResourceLearningRepository(engine)
    service = StandardResourceReviewService(
        repository=StandardResourceRepository(engine),
        material_repository=materials,
    )
    try:
        yield service, materials, learning
    finally:
        engine.dispose()


def _seed_classroom(materials: PostgresMaterialRepository, *, valid: bool = True) -> None:
    scenes = []
    if valid:
        scenes = [
            {
                "id": "slide-1",
                "type": "slide",
                "content": {"type": "slide"},
                "actions": [{"id": "speech-1", "type": "speech", "text": "知识点讲解"}],
            },
            {
                "id": "quiz-1",
                "type": "quiz",
                "content": {
                    "type": "quiz",
                    "questions": [
                        {"id": "q1", "type": "single", "answer": ["B"]},
                    ],
                },
            },
        ]
    materials.upsert(
        {
            "course_id": "course-1",
            "material_type": "classroom",
            "material_id": "classroom-1",
            "title": "标准 AI 课堂",
            "origin_type": "standard",
            "standard_kind": "classroom",
            "generation_batch_id": "batch-1",
            "current_review_status": "pending",
            "review_status": "pending",
            "version": 2,
            "scenes": scenes,
        }
    )


def test_approving_classroom_freezes_manifest_before_student_visibility(review_fixture) -> None:
    service, materials, learning = review_fixture
    _seed_classroom(materials)

    result = service.review(
        course_id="course-1",
        material_id="classroom-1",
        reviewer_id="teacher-1",
        decision="approved",
        reason="",
    )

    manifest = learning.get_manifest("course-1", "classroom-1", 2)
    assert result["approved_version"] == 2
    assert manifest is not None
    assert manifest.mode == "completable"


def test_manifest_failure_leaves_classroom_pending(review_fixture) -> None:
    service, materials, learning = review_fixture
    _seed_classroom(materials, valid=False)

    with pytest.raises(StandardResourceRuleError) as error:
        service.review(
            course_id="course-1",
            material_id="classroom-1",
            reviewer_id="teacher-1",
            decision="approved",
            reason="",
        )

    assert error.value.code == "LEARNING_MANIFEST_INVALID"
    material = materials.get("course-1", "classroom", "classroom-1")
    assert material["current_review_status"] == "pending"
    assert learning.get_manifest("course-1", "classroom-1", 2) is None


def test_non_classroom_review_keeps_existing_behavior(review_fixture) -> None:
    service, materials, learning = review_fixture
    materials.upsert(
        {
            "course_id": "course-1",
            "material_type": "report",
            "material_id": "guide-1",
            "title": "学习指南",
            "origin_type": "standard",
            "standard_kind": "study_guide",
            "current_review_status": "pending",
            "review_status": "pending",
            "version": 1,
            "content": "guide",
        }
    )

    result = service.review(
        course_id="course-1",
        material_id="guide-1",
        reviewer_id="teacher-1",
        decision="approved",
        reason="",
    )

    assert result["approved_version"] == 1
    assert learning.get_manifest("course-1", "guide-1", 1) is None

