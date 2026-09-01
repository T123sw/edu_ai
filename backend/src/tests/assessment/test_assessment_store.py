from __future__ import annotations

from dataclasses import replace

import pytest

from app.assessment.models import (
    AssessmentItemRecord,
    AssessmentRecord,
    AssessmentVersionRecord,
)
from app.assessment.store import AssessmentStore, AssessmentStoreError


def _draft_records() -> tuple[AssessmentRecord, AssessmentVersionRecord]:
    assessment = AssessmentRecord(
        assessment_id="asmt-1",
        course_id="course-1",
        task_id="lt-1",
        created_by="teacher-1",
        created_at="2026-08-12T00:00:00+00:00",
    )
    version = AssessmentVersionRecord(
        assessment_version_id="asv-1",
        assessment_id=assessment.assessment_id,
        version_number=1,
        status="draft",
        source_mode="imported",
        assessment_mode="closed_book",
        pass_threshold=60,
        mastery_threshold=80,
        max_attempts=3,
        score_policy="best_final_score",
        answer_reveal_policy="after_finish_or_exhausted",
        shuffle_questions=False,
        shuffle_options=False,
        created_at="2026-08-12T00:00:00+00:00",
    )
    return assessment, version


def _item(*, answer: str = "a") -> AssessmentItemRecord:
    return replace(
        AssessmentItemRecord.new(
            assessment_version_id="asv-1",
            position=1,
            item_type="single_choice",
            prompt={
                "stem": "Python 循环关键字是？",
                "options": [
                    {"id": "a", "text": "for"},
                    {"id": "b", "text": "when"},
                ],
            },
            scoring_key={"correct_option_id": answer},
            rubric={},
            max_score=10,
            grading_provider="deterministic",
            knowledge_point_ids=["loops"],
            source_refs=[{"material_type": "quiz", "material_id": "quiz-1"}],
            created_origin="imported",
        ),
        assessment_item_id="asi-1",
    )


def test_published_version_is_idempotent_immutable_and_durable(tmp_path):
    path = tmp_path / "assessment.db"
    store = AssessmentStore(path)
    assessment, version = _draft_records()
    store.create_draft(assessment, version)
    updated = store.replace_draft_items(
        version.assessment_version_id,
        [_item()],
        expected_revision=0,
    )

    first = store.publish_version(
        version.assessment_version_id,
        published_by="teacher-1",
    )
    second = store.publish_version(
        version.assessment_version_id,
        published_by="teacher-1",
    )

    assert updated.draft_revision == 1
    assert first.status == "published"
    assert first.content_hash
    assert second.content_hash == first.content_hash
    assert store.get_assessment_for_task("course-1", "lt-1").current_version_id == "asv-1"
    with pytest.raises(AssessmentStoreError) as error:
        store.replace_draft_items("asv-1", [_item(answer="b")], expected_revision=1)
    assert error.value.code == "VERSION_IMMUTABLE"

    store.close()
    reopened = AssessmentStore(path)
    restored = reopened.get_version("asv-1")
    assert restored is not None
    assert restored.content_hash == first.content_hash
    assert reopened.list_items("asv-1")[0].scoring_key == {"correct_option_id": "a"}


def test_replacing_draft_items_rejects_stale_revision(tmp_path):
    store = AssessmentStore(tmp_path / "assessment.db")
    assessment, version = _draft_records()
    store.create_draft(assessment, version)
    store.replace_draft_items("asv-1", [_item()], expected_revision=0)

    with pytest.raises(AssessmentStoreError) as error:
        store.replace_draft_items("asv-1", [_item(answer="b")], expected_revision=0)

    assert error.value.code == "DRAFT_REVISION_CONFLICT"
    assert store.list_items("asv-1")[0].scoring_key == {"correct_option_id": "a"}


def test_one_assessment_per_task_is_enforced(tmp_path):
    store = AssessmentStore(tmp_path / "assessment.db")
    assessment, version = _draft_records()
    store.create_draft(assessment, version)

    with pytest.raises(AssessmentStoreError) as error:
        store.create_draft(
            replace(assessment, assessment_id="asmt-2"),
            replace(version, assessment_id="asmt-2", assessment_version_id="asv-2"),
        )

    assert error.value.code == "TASK_ASSESSMENT_EXISTS"
