"""Delivery notices remain separate from tutoring notifications."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260918_0036'
down_revision='20260917_0035'
branch_labels=None
depends_on=None

def upgrade():
    payload=sa.JSON().with_variant(postgresql.JSONB(),'postgresql')
    op.create_table('preparation_course_notifications',sa.Column('event_id',sa.String(160),primary_key=True),sa.Column('owner',sa.String(160),nullable=False),
        sa.Column('course_id',sa.String(200),nullable=False),sa.Column('payload',payload,nullable=False),sa.Column('read_at',sa.Float()),sa.Column('created_at',sa.Float(),nullable=False))

def downgrade():
    op.drop_table('preparation_course_notifications')
