"""Add data integrity constraints for standard learning resources.

Revision ID: 20260824_0017
Revises: 20260824_0016
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_0017"
down_revision: Union[str, None] = "20260824_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CHECKS = (
    (
        "materials",
        "materials_valid_origin_type",
        "origin_type IN ('personal', 'standard', 'legacy_shared')",
    ),
    (
        "materials",
        "materials_valid_standard_kind",
        "standard_kind IS NULL OR standard_kind IN ('classroom', 'study_guide', 'practice')",
    ),
    (
        "materials",
        "materials_valid_review_status",
        "current_review_status IN ('not_required', 'pending', 'approved', 'rejected')",
    ),
    (
        "material_versions",
        "material_versions_valid_origin_type",
        "origin_type IN ('personal', 'standard', 'legacy_shared')",
    ),
    (
        "material_versions",
        "material_versions_valid_standard_kind",
        "standard_kind IS NULL OR standard_kind IN ('classroom', 'study_guide', 'practice')",
    ),
    (
        "material_versions",
        "material_versions_valid_review_status",
        "review_status IN ('not_required', 'pending', 'approved', 'rejected')",
    ),
    (
        "learning_tasks",
        "learning_tasks_valid_task_type",
        "task_type IN ('reading', 'assessed')",
    ),
)


def _physical_name(table: str, name: str) -> str:
    """Return the name produced by the metadata naming convention."""
    return f"ck_{table}_{name}"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, name, condition in CHECKS:
        existing = {
            item["name"]
            for item in sa.inspect(op.get_bind()).get_check_constraints(table)
        }
        if name not in existing and _physical_name(table, name) not in existing:
            op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, name, _condition in reversed(CHECKS):
        existing = {
            item["name"]
            for item in sa.inspect(op.get_bind()).get_check_constraints(table)
        }
        physical_name = _physical_name(table, name)
        if physical_name in existing:
            op.drop_constraint(physical_name, table, type_="check")
        elif name in existing:
            op.drop_constraint(name, table, type_="check")
