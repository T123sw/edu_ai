"""Add unique human-friendly course join codes.

Revision ID: 20260811_0011
Revises: 20260810_0010
Create Date: 2026-08-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.services.course_code_service import deterministic_course_code


revision: str = "20260811_0011"
down_revision: Union[str, None] = "20260810_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("course_code", sa.String(length=8), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT course_id FROM courses ORDER BY course_id")).fetchall()
    used: set[str] = set()
    for (course_id,) in rows:
        salt = 0
        code = deterministic_course_code(str(course_id), salt=salt)
        while code in used:
            salt += 1
            code = deterministic_course_code(str(course_id), salt=salt)
        used.add(code)
        connection.execute(
            sa.text("UPDATE courses SET course_code = :code WHERE course_id = :course_id"),
            {"code": code, "course_id": course_id},
        )
    op.alter_column("courses", "course_code", nullable=False)
    op.create_index("ix_courses_course_code", "courses", ["course_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_courses_course_code", table_name="courses")
    op.drop_column("courses", "course_code")
