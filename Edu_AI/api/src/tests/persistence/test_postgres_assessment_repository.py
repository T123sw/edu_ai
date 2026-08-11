from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import create_engine

from app.assessment.models import (
    AssessmentItemRecord,
    AssessmentRecord,
    AssessmentVersionRecord,
)
from app.database import Base
from app.persistence.postgres_assessment_repository import PostgresAssessmentRepository


def test_assessment_store_postgres_mode_does_not_create_sqlite_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'postgres-mode.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ASSESSMENT_PERSISTENCE_MODE", "postgres")
    sqlite_path = tmp_path / "assessment.db"

    from app.assessment.store import AssessmentStore

    store = AssessmentStore(sqlite_path)
    assessment = AssessmentRecord(
        assessment_id="asmt-postgres",
        course_id="course-1",
        task_id="lt-postgres",
        created_by="teacher-1",
    )
    version = AssessmentVersionRecord(
        assessment_version_id="asv-postgres",
        assessment_id=assessment.assessment_id,
        version_number=1,
        status="draft",
        source_mode="manual",
        assessment_mode="closed_book",
        pass_threshold=60,
        mastery_threshold=80,
        max_attempts=3,
        score_policy="best_final_score",
        answer_reveal_policy="after_finish_or_exhausted",
        shuffle_questions=False,
        shuffle_options=False,
    )

    store.create_draft(assessment, version)

    assert store.get_assessment_for_task("course-1", "lt-postgres") is not None
    assert sqlite_path.exists() is False
    store.close()


def test_postgres_repository_freezes_published_version_with_sqlite_shim(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'postgres-shim.db').as_posix()}")
    Base.metadata.create_all(engine)
    repository = PostgresAssessmentRepository(engine)
    assessment = AssessmentRecord(
        assessment_id="asmt-1",
        course_id="course-1",
        task_id="lt-1",
        created_by="teacher-1",
    )
    version = AssessmentVersionRecord(
        assessment_version_id="asv-1",
        assessment_id="asmt-1",
        version_number=1,
        status="draft",
        source_mode="manual",
        assessment_mode="closed_book",
        pass_threshold=60,
        mastery_threshold=80,
        max_attempts=3,
        score_policy="best_final_score",
        answer_reveal_policy="after_finish_or_exhausted",
        shuffle_questions=False,
        shuffle_options=False,
    )
    item = replace(
        AssessmentItemRecord.new(
            assessment_version_id="asv-1",
            position=1,
            item_type="judge",
            prompt={"stem": "for 可用于循环。"},
            scoring_key={"correct_value": True},
            rubric={},
            max_score=10,
            grading_provider="deterministic",
            knowledge_point_ids=["loops"],
            source_refs=[{"material_type": "report", "material_id": "report-1"}],
            created_origin="teacher",
        ),
        assessment_item_id="asi-1",
    )

    repository.create_draft(assessment, version)
    updated = repository.update_draft(
        replace(version, source_mode="mixed", pass_threshold=70),
        [item],
        expected_revision=0,
    )
    assert updated.draft_revision == 1
    assert updated.source_mode == "mixed"
    assert updated.pass_threshold == 70
    with pytest.raises(ValueError, match="Assessment draft has changed"):
        repository.update_draft(version, [item], expected_revision=0)
    published = repository.publish_version("asv-1", published_by="teacher-1")

    assert published.status == "published"
    assert repository.get_assessment_for_task("course-1", "lt-1").current_version_id == "asv-1"
    assert repository.list_items("asv-1")[0].scoring_key == {"correct_value": True}
