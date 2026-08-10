"""Create core identity and course tables.

Revision ID: 20260810_0001
Revises:
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260810_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("username", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_disabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'teacher', 'student')",
            name=op.f("ck_users_valid_role"),
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "courses",
        sa.Column("course_id", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("icon", sa.String(length=120), server_default="menu_book", nullable=False),
        sa.Column("color", sa.String(length=32), server_default="#2563eb", nullable=False),
        sa.Column("cover_image_ref", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
            name=op.f("fk_courses_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("course_id", name=op.f("pk_courses")),
    )
    op.create_index(op.f("ix_courses_created_by"), "courses", ["created_by"], unique=False)
    op.create_table(
        "course_objectives",
        sa.Column("objective_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("course_id", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.CheckConstraint("position >= 0", name=op.f("ck_course_objectives_non_negative_position")),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.course_id"],
            name=op.f("fk_course_objectives_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("objective_id", name=op.f("pk_course_objectives")),
        sa.UniqueConstraint("course_id", "position", name="uq_course_objectives_course_position"),
    )
    op.create_index(
        op.f("ix_course_objectives_course_id"),
        "course_objectives",
        ["course_id"],
        unique=False,
    )
    op.create_table(
        "course_memberships",
        sa.Column("course_id", sa.String(length=200), nullable=False),
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("added_by", sa.String(length=160), nullable=True),
        sa.CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')",
            name=op.f("ck_course_memberships_valid_role"),
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.course_id"],
            name=op.f("fk_course_memberships_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_course_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("course_id", "user_id", name=op.f("pk_course_memberships")),
    )


def downgrade() -> None:
    op.drop_table("course_memberships")
    op.drop_index(op.f("ix_course_objectives_course_id"), table_name="course_objectives")
    op.drop_table("course_objectives")
    op.drop_index(op.f("ix_courses_created_by"), table_name="courses")
    op.drop_table("courses")
    op.drop_table("users")
