"""Durable learning answer snapshots, checkpoints and tool audit."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '20260917_0026'
down_revision = '20260917_0025'
branch_labels = None
depends_on = None


def upgrade():
    j = sa.JSON().with_variant(JSONB(), 'postgresql')
    op.create_table('learning_answer_runs',
        sa.Column('turn_id', sa.String(80), primary_key=True),
        sa.Column('session_id', sa.String(200), sa.ForeignKey('learning_topic_sessions.session_id', ondelete='CASCADE'), nullable=False),
        *[sa.Column(n, sa.String(size), nullable=False) for n, size in [('request_id',36), ('owner',160), ('course_id',200), ('topic_id',240), ('payload_hash',64), ('status',24), ('stage',40), ('token',64)]],
        sa.Column('request', j, nullable=False), sa.Column('checkpoint', j, nullable=False), sa.Column('result', j),
        sa.Column('error_code', sa.String(80)), sa.Column('attempt', sa.Integer(), nullable=False),
        *[sa.Column(n, sa.Float(), nullable=False) for n in ['lease_until', 'deadline', 'created_at']],
        sa.UniqueConstraint('session_id', 'request_id', name='uq_learning_answer_request'))
    op.create_table('learning_agent_tool_calls',
        sa.Column('turn_id', sa.String(80), sa.ForeignKey('learning_answer_runs.turn_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('operation_id', sa.String(80), primary_key=True), sa.Column('payload', j, nullable=False))

    op.create_table('learning_agent_outbox', sa.Column('event_id', sa.String(80), primary_key=True),
        sa.Column('turn_id', sa.String(80), sa.ForeignKey('learning_answer_runs.turn_id', ondelete='CASCADE'), nullable=False),
        sa.Column('owner', sa.String(160), nullable=False), sa.Column('payload', j, nullable=False))

def downgrade():
    op.drop_table('learning_agent_outbox')
    op.drop_table('learning_agent_tool_calls')
    op.drop_table('learning_answer_runs')
