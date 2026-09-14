"""Bind standard-resource regeneration batches to exact versions.

Revision ID: 20260910_0021
Revises: 20260901_0020
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_0021"
down_revision: Union[str, None] = "20260901_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("standard_resource_batches", sa.Column("idempotency_key", sa.String(200), nullable=True))
    op.add_column("standard_resource_batches", sa.Column("graph_version", sa.String(128), nullable=True))
    op.add_column("standard_resource_batches", sa.Column("generation_mode", sa.String(32), nullable=True))
    op.execute("UPDATE standard_resource_batches SET idempotency_key = batch_id, graph_version = 'legacy', generation_mode = 'regenerate_all'")
    op.alter_column("standard_resource_batches", "idempotency_key", nullable=False)
    op.alter_column("standard_resource_batches", "graph_version", nullable=False)
    op.alter_column("standard_resource_batches", "generation_mode", nullable=False)
    op.create_unique_constraint("uq_standard_resource_batches_idempotency", "standard_resource_batches", ["course_id", "idempotency_key"])

    op.add_column("standard_resource_batch_items", sa.Column("action", sa.String(32), nullable=False, server_default="generate"))
    op.add_column("standard_resource_batch_items", sa.Column("base_version", sa.Integer(), nullable=True))
    op.add_column("standard_resource_batch_items", sa.Column("material_version", sa.Integer(), nullable=True))
    op.add_column("standard_resource_batch_items", sa.Column("content_hash", sa.String(128), nullable=True))
    op.add_column("standard_resource_batch_items", sa.Column("active_slot_key", sa.String(700), nullable=True))
    op.add_column("standard_resource_batch_items", sa.Column("generation_context", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.create_unique_constraint("uq_standard_resource_batch_items_active_slot", "standard_resource_batch_items", ["active_slot_key"])


def downgrade() -> None:
    op.drop_constraint("uq_standard_resource_batch_items_active_slot", "standard_resource_batch_items", type_="unique")
    for column in ("generation_context", "active_slot_key", "content_hash", "material_version", "base_version", "action"):
        op.drop_column("standard_resource_batch_items", column)
    op.drop_constraint("uq_standard_resource_batches_idempotency", "standard_resource_batches", type_="unique")
    for column in ("generation_mode", "graph_version", "idempotency_key"):
        op.drop_column("standard_resource_batches", column)
