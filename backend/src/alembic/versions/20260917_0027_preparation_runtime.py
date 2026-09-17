"""Preparation execution leases, shared budget and durable action receipts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '20260917_0027'
down_revision = '20260917_0026'
branch_labels = None
depends_on = None


def upgrade():
    payload = sa.JSON().with_variant(JSONB(), 'postgresql')
    op.create_table('preparation_executions',
        sa.Column('preparation_id', sa.String(200), primary_key=True),
        sa.Column('attempt_no', sa.Integer(), primary_key=True),
        sa.Column('lease_token', sa.String(64)), sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('worker_id', sa.String(200)), sa.Column('wake_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('input_digest', sa.String(64), nullable=False), sa.Column('checkpoint', payload, nullable=False),
        sa.Column('error_code', sa.String(100)), sa.Column('result_ref', payload),
        sa.Column('no_progress', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['preparation_id', 'attempt_no'],
            ['course_preparation_attempts.preparation_id', 'course_preparation_attempts.attempt_no'], ondelete='CASCADE'))
    op.create_index('ix_preparation_executions_wake_at', 'preparation_executions', ['wake_at'])
    op.create_table('preparation_budgets',
        sa.Column('preparation_id', sa.String(200), sa.ForeignKey('course_preparations.preparation_id'), primary_key=True),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=False),
        sa.Column('limits', payload, nullable=False), sa.Column('reserved', payload, nullable=False),
        sa.Column('consumed', payload, nullable=False))
    op.create_table('preparation_actions',
        sa.Column('action_id', sa.String(200), primary_key=True),
        sa.Column('preparation_id', sa.String(200), sa.ForeignKey('course_preparations.preparation_id'), nullable=False),
        sa.Column('action_key', sa.String(240), nullable=False), sa.Column('kind', sa.String(100), nullable=False),
        sa.Column('payload_digest', sa.String(64), nullable=False), sa.Column('payload', payload, nullable=False),
        sa.Column('reserved', payload, nullable=False), sa.Column('consumed', payload),
        sa.Column('status', sa.String(24), nullable=False), sa.Column('receipt', payload),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('preparation_id', 'action_key', name='uq_preparation_action_key'),
        sa.CheckConstraint("status IN ('pending', 'completed', 'failed')", name='preparation_action_status'))


def downgrade():
    op.drop_table('preparation_actions')
    op.drop_table('preparation_budgets')
    op.drop_table('preparation_executions')
