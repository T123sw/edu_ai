"""Persist step-scoped PBL tutoring and its code snapshot."""
from alembic import op
import sqlalchemy as sa

revision = '20261014_0039'
down_revision = '20261013_0038'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pbl_tutor_turns',
        sa.Column('owner', sa.String(160), primary_key=True),
        sa.Column('exercise_id', sa.String(80), sa.ForeignKey('pbl_exercises.id'), primary_key=True),
        sa.Column('request_id', sa.String(80), primary_key=True),
        sa.Column('artifact_version', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.String(200), nullable=False),
        sa.Column('request', sa.JSON(), nullable=False),
        sa.Column('response', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False))


def downgrade():
    op.drop_table('pbl_tutor_turns')
