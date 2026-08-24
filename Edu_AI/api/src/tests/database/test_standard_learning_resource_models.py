from __future__ import annotations

from sqlalchemy import create_engine, inspect

from app.database import Base


def test_standard_resource_tables_and_columns_are_part_of_metadata() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    material_columns = {item["name"] for item in inspector.get_columns("materials")}
    assert {
        "origin_type",
        "standard_kind",
        "generation_batch_id",
        "current_review_status",
        "approved_version",
        "approved_by",
        "approved_at",
    } <= material_columns

    version_columns = {item["name"] for item in inspector.get_columns("material_versions")}
    assert {
        "origin_type",
        "standard_kind",
        "generation_batch_id",
        "review_status",
        "reviewed_by",
        "reviewed_at",
        "rejection_reason",
    } <= version_columns

    task_columns = {item["name"] for item in inspector.get_columns("learning_tasks")}
    assert "task_type" in task_columns

    assert {
        "standard_resource_batches",
        "standard_resource_batch_items",
        "learning_task_resource_snapshots",
    } <= set(inspector.get_table_names())


def test_standard_resource_relational_constraints_are_present() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    batch_item_unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("standard_resource_batch_items")
    }
    assert ("batch_id", "leaf_id", "standard_kind") in batch_item_unique_columns

    snapshot_unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("learning_task_resource_snapshots")
    }
    assert ("task_id", "position") in snapshot_unique_columns
