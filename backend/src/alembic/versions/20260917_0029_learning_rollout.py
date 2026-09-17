"""Audited legacy learning import and scoped rollout."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='20260917_0029'
down_revision='20260917_0028'
branch_labels=None
depends_on=None

def upgrade():
    j=sa.JSON().with_variant(JSONB(),'postgresql')
    op.create_table('learning_migration_ledger',
        sa.Column('owner',sa.String(160),primary_key=True),sa.Column('course_id',sa.String(200),primary_key=True),
        sa.Column('source_hash',sa.String(64),nullable=False),sa.Column('source',j,nullable=False),
        sa.Column('result',j,nullable=False),sa.Column('updated_at',sa.Float(),nullable=False))
    op.create_table('learning_rollout_scopes',
        sa.Column('owner',sa.String(160),primary_key=True),sa.Column('course_id',sa.String(200),primary_key=True),
        sa.Column('phase',sa.Integer(),nullable=False),sa.Column('source_hash',sa.String(64),nullable=False),sa.Column('activated_at',sa.Float(),nullable=False))

def downgrade():
    op.drop_table('learning_rollout_scopes')
    op.drop_table('learning_migration_ledger')
