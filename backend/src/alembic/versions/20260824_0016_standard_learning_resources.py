"""Add standard learning resources, review batches, and task snapshots.

Revision ID: 20260824_0016
Revises: 20260812_0015
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_0016"
down_revision: Union[str, None] = "20260812_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def _create_index_if_missing(table: str, name: str, columns: list[str]) -> None:
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns)


def upgrade() -> None:
    _add_column_if_missing(
        "materials",
        sa.Column("origin_type", sa.String(32), nullable=False, server_default="personal"),
    )
    _add_column_if_missing("materials", sa.Column("standard_kind", sa.String(32)))
    _add_column_if_missing("materials", sa.Column("generation_batch_id", sa.String(200)))
    _add_column_if_missing(
        "materials",
        sa.Column(
            "current_review_status",
            sa.String(32),
            nullable=False,
            server_default="not_required",
        ),
    )
    _add_column_if_missing("materials", sa.Column("approved_version", sa.Integer()))
    _add_column_if_missing("materials", sa.Column("approved_by", sa.String(160)))
    _add_column_if_missing(
        "materials", sa.Column("approved_at", sa.DateTime(timezone=True))
    )

    _add_column_if_missing(
        "material_versions",
        sa.Column("origin_type", sa.String(32), nullable=False, server_default="personal"),
    )
    _add_column_if_missing("material_versions", sa.Column("standard_kind", sa.String(32)))
    _add_column_if_missing(
        "material_versions", sa.Column("generation_batch_id", sa.String(200))
    )
    _add_column_if_missing(
        "material_versions",
        sa.Column(
            "review_status",
            sa.String(32),
            nullable=False,
            server_default="not_required",
        ),
    )
    _add_column_if_missing("material_versions", sa.Column("reviewed_by", sa.String(160)))
    _add_column_if_missing(
        "material_versions", sa.Column("reviewed_at", sa.DateTime(timezone=True))
    )
    _add_column_if_missing("material_versions", sa.Column("rejection_reason", sa.Text()))
    _add_column_if_missing(
        "learning_tasks",
        sa.Column("task_type", sa.String(32), nullable=False, server_default="assessed"),
    )

    op.execute(
        sa.text(
            "UPDATE materials SET origin_type = CASE "
            "WHEN visibility = 'course' THEN 'legacy_shared' ELSE 'personal' END "
            "WHERE origin_type = 'personal'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE material_versions AS mv SET origin_type = m.origin_type "
            "FROM materials AS m WHERE mv.course_id = m.course_id "
            "AND mv.material_type = m.material_type AND mv.material_id = m.material_id"
        )
    )

    for table, name, columns in (
        ("materials", "ix_materials_origin_type", ["origin_type"]),
        ("materials", "ix_materials_standard_kind", ["standard_kind"]),
        ("materials", "ix_materials_generation_batch_id", ["generation_batch_id"]),
        ("materials", "ix_materials_current_review_status", ["current_review_status"]),
        ("material_versions", "ix_material_versions_origin_type", ["origin_type"]),
        ("material_versions", "ix_material_versions_standard_kind", ["standard_kind"]),
        (
            "material_versions",
            "ix_material_versions_generation_batch_id",
            ["generation_batch_id"],
        ),
        ("material_versions", "ix_material_versions_review_status", ["review_status"]),
    ):
        _create_index_if_missing(table, name, columns)

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("standard_resource_batches"):
        op.create_table(
            "standard_resource_batches",
            sa.Column("batch_id", sa.String(200), primary_key=True),
            sa.Column("course_id", sa.String(200), nullable=False),
            sa.Column("created_by", sa.String(160), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
            sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("queued_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("running_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("succeeded_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
            sa.CheckConstraint(
                "status IN ('queued', 'running', 'partial', 'completed', 'failed')",
                name="standard_resource_batches_valid_status",
            ),
        )
        for name, columns in (
            ("ix_standard_resource_batches_course_id", ["course_id"]),
            ("ix_standard_resource_batches_created_by", ["created_by"]),
            ("ix_standard_resource_batches_status", ["status"]),
        ):
            op.create_index(name, "standard_resource_batches", columns)

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("standard_resource_batch_items"):
        op.create_table(
            "standard_resource_batch_items",
            sa.Column("batch_item_id", sa.String(240), primary_key=True),
            sa.Column(
                "batch_id",
                sa.String(200),
                sa.ForeignKey("standard_resource_batches.batch_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("leaf_id", sa.String(240), nullable=False),
            sa.Column("leaf_title", sa.String(500), nullable=False),
            sa.Column("standard_kind", sa.String(32), nullable=False),
            sa.Column("material_type", sa.String(80), nullable=False),
            sa.Column("material_id", sa.String(240), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
            sa.Column("job_id", sa.String(200)),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error", sa.JSON()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint(
                "batch_id", "leaf_id", "standard_kind",
                name="uq_standard_resource_batch_items_slot",
            ),
            sa.CheckConstraint(
                "standard_kind IN ('classroom', 'study_guide', 'practice')",
                name="standard_resource_batch_items_valid_kind",
            ),
            sa.CheckConstraint(
                "status IN ('queued', 'running', 'succeeded', 'failed')",
                name="standard_resource_batch_items_valid_status",
            ),
        )
        for name, columns in (
            ("ix_standard_resource_batch_items_batch_id", ["batch_id"]),
            ("ix_standard_resource_batch_items_leaf_id", ["leaf_id"]),
            ("ix_standard_resource_batch_items_status", ["status"]),
            ("ix_standard_resource_batch_items_job_id", ["job_id"]),
        ):
            op.create_index(name, "standard_resource_batch_items", columns)

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("learning_task_resource_snapshots"):
        op.create_table(
            "learning_task_resource_snapshots",
            sa.Column("snapshot_id", sa.String(240), primary_key=True),
            sa.Column(
                "task_id",
                sa.String(200),
                sa.ForeignKey("learning_tasks.task_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("source_material_type", sa.String(80), nullable=False),
            sa.Column("source_material_id", sa.String(240), nullable=False),
            sa.Column("source_version", sa.Integer(), nullable=False),
            sa.Column("origin_type", sa.String(32), nullable=False),
            sa.Column("standard_kind", sa.String(32)),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("content_payload", sa.JSON(), nullable=False),
            sa.Column("file_refs", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "task_id", "position", name="uq_learning_task_snapshots_position"
            ),
        )
        op.create_index(
            "ix_learning_task_resource_snapshots_task_id",
            "learning_task_resource_snapshots",
            ["task_id"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("learning_task_resource_snapshots"):
        op.drop_table("learning_task_resource_snapshots")
    if inspector.has_table("standard_resource_batch_items"):
        op.drop_table("standard_resource_batch_items")
    if inspector.has_table("standard_resource_batches"):
        op.drop_table("standard_resource_batches")

    for table, columns in (
        ("learning_tasks", ["task_type"]),
        (
            "material_versions",
            [
                "rejection_reason", "reviewed_at", "reviewed_by", "review_status",
                "generation_batch_id", "standard_kind", "origin_type",
            ],
        ),
        (
            "materials",
            [
                "approved_at", "approved_by", "approved_version",
                "current_review_status", "generation_batch_id",
                "standard_kind", "origin_type",
            ],
        ),
    ):
        existing = {
            item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)
        }
        for column in columns:
            if column in existing:
                op.drop_column(table, column)
