"""Persistent opt-in coaching and transactional attempt feedback."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261013_0037'
down_revision = '20260918_0036'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('learning_teaching_activities',
        sa.Column('check_id', sa.String(80), sa.ForeignKey('learning_checks.check_id'), primary_key=True),
        sa.Column('owner', sa.String(160), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False))
    op.create_table('learning_teaching_feedback',
        sa.Column('attempt_id', sa.String(80), sa.ForeignKey('learning_check_attempts.attempt_id'), primary_key=True),
        sa.Column('check_id', sa.String(80), sa.ForeignKey('learning_checks.check_id'), nullable=False),
        sa.Column('owner', sa.String(160), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('request', sa.JSON().with_variant(JSONB(), 'postgresql'), nullable=False),
        sa.Column('turn_id', sa.String(80)), sa.Column('error', sa.String(80)),
        sa.Column('created_at', sa.Float(), nullable=False))
    op.create_index('ix_learning_teaching_feedback_pending', 'learning_teaching_feedback', ['status', 'created_at'])


def downgrade():
    op.drop_table('learning_teaching_feedback')
    op.drop_table('learning_teaching_activities')
