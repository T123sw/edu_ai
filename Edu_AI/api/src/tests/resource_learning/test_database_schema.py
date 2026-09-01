from __future__ import annotations

from sqlalchemy import create_engine, inspect

from app.database.base import Base
from app.database import models as _database_models  # noqa: F401


def test_resource_learning_schema_has_versioned_progress_and_idempotent_events() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    names = set(inspector.get_table_names())
    assert {
        "resource_learning_manifests",
        "resource_learning_sessions",
        "resource_learning_events",
        "resource_learning_activity_events",
        "resource_learning_coverage",
        "resource_question_attempts",
        "resource_learning_progress",
        "task_resource_evidence_refs",
    } <= names

    progress_columns = {
        item["name"] for item in inspector.get_columns("resource_learning_progress")
    }
    assert "completion_basis" in progress_columns

    event_constraints = inspector.get_unique_constraints("resource_learning_events")
    assert any(
        set(item["column_names"]) == {"session_id", "sequence_number"}
        for item in event_constraints
    )

    attempt_constraints = inspector.get_unique_constraints("resource_question_attempts")
    assert any(
        set(item["column_names"])
        == {
            "student_id",
            "course_id",
            "resource_id",
            "resource_version",
            "question_id",
            "attempt_number",
        }
        for item in attempt_constraints
    )

    evidence_constraints = inspector.get_unique_constraints("task_resource_evidence_refs")
    assert any(
        set(item["column_names"])
        == {"task_id", "student_id", "resource_id", "resource_version"}
        for item in evidence_constraints
    )


def test_progress_uses_student_course_resource_and_version_as_primary_key() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    primary_key = inspect(engine).get_pk_constraint("resource_learning_progress")
    assert primary_key["constrained_columns"] == [
        "student_id",
        "course_id",
        "resource_id",
        "resource_version",
    ]
