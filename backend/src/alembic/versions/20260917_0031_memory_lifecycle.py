"""Shared memory watermarks, suppressions, dependencies and change outbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = '20260917_0031'
down_revision = '20260917_0030'
branch_labels = None
depends_on = None

def upgrade():
    payload = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')
    op.create_table('agent_memory_epochs', sa.Column('subject_user_id',sa.String(160),primary_key=True),sa.Column('epoch',sa.Integer(),nullable=False))
    op.create_table('agent_memory_suppressions', sa.Column('subject_user_id',sa.String(160),primary_key=True),sa.Column('source_digest',sa.String(64),primary_key=True),sa.Column('source_id',sa.Text(),nullable=False),sa.Column('epoch',sa.Integer(),nullable=False))
    op.create_table('agent_memory_dependencies', sa.Column('subject_user_id',sa.String(160),primary_key=True),sa.Column('consumer_ref',sa.String(300),primary_key=True),sa.Column('epoch',sa.Integer(),nullable=False),sa.Column('source_refs',payload,nullable=False),sa.Column('valid',sa.Boolean(),nullable=False))
    op.create_table('agent_memory_changes', sa.Column('subject_user_id',sa.String(160),primary_key=True),sa.Column('epoch',sa.Integer(),primary_key=True),sa.Column('affected_memory_ids',payload,nullable=False),sa.Column('delivered',sa.Boolean(),nullable=False),sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    for name in ('agent_memory_changes','agent_memory_dependencies','agent_memory_suppressions','agent_memory_epochs'): op.drop_table(name)
