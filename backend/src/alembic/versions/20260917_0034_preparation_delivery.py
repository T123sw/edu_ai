"""Immutable personal manifests, active pointers and delivery outbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260917_0034'
down_revision='20260917_0033'
branch_labels=None
depends_on=None

def upgrade():
    payload=sa.JSON().with_variant(postgresql.JSONB(),'postgresql')
    op.create_table('prepared_manifest_versions',
        sa.Column('owner_user_id',sa.String(160),sa.ForeignKey('users.user_id'),primary_key=True),
        sa.Column('course_id',sa.String(200),primary_key=True),sa.Column('version',sa.Integer(),primary_key=True),
        sa.Column('manifest_id',sa.String(200),nullable=False),
        sa.Column('preparation_id',sa.String(200),sa.ForeignKey('course_preparations.preparation_id'),nullable=False),
        sa.Column('payload',payload,nullable=False),sa.Column('content_digest',sa.String(64),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('prepared_course_pointers',sa.Column('owner_user_id',sa.String(160),sa.ForeignKey('users.user_id'),primary_key=True),
        sa.Column('course_id',sa.String(200),primary_key=True),sa.Column('version',sa.Integer(),nullable=False))
    op.create_table('preparation_delivery_events',sa.Column('event_id',sa.String(160),primary_key=True),
        sa.Column('preparation_id',sa.String(200),sa.ForeignKey('course_preparations.preparation_id'),nullable=False,unique=True),
        sa.Column('owner_user_id',sa.String(160),sa.ForeignKey('users.user_id'),nullable=False),sa.Column('course_id',sa.String(200),nullable=False),
        sa.Column('manifest_version',sa.Integer(),nullable=False),sa.Column('payload',payload,nullable=False),sa.Column('delivered',sa.Boolean(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    for name in ('preparation_delivery_events','prepared_course_pointers','prepared_manifest_versions'): op.drop_table(name)
