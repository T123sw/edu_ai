"""Private generation drafts; no course publication before delivery transaction."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260917_0030'
down_revision='20260917_0029'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('preparation_artifacts',
        sa.Column('artifact_id',sa.String(160),primary_key=True),
        sa.Column('preparation_id',sa.String(200),sa.ForeignKey('course_preparations.preparation_id'),nullable=False),
        sa.Column('action_id',sa.String(160),sa.ForeignKey('preparation_actions.action_id'),nullable=False,unique=True),
        sa.Column('owner_user_id',sa.String(160),sa.ForeignKey('users.user_id'),nullable=False),
        sa.Column('resource_id',sa.String(200),nullable=False),sa.Column('resource_version',sa.Integer(),nullable=False),
        sa.Column('resource_type',sa.String(40),nullable=False),sa.Column('spec',sa.JSON().with_variant(postgresql.JSONB(),'postgresql'),nullable=False),
        sa.Column('spec_digest',sa.String(64),nullable=False),sa.Column('status',sa.String(30),nullable=False),
        sa.Column('lease_token',sa.String(160)),sa.Column('lease_until',sa.DateTime(timezone=True)),
        sa.Column('content',sa.JSON().with_variant(postgresql.JSONB(),'postgresql')),sa.Column('content_digest',sa.String(64)),
        sa.Column('error_code',sa.String(80)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_preparation_artifacts_preparation_id','preparation_artifacts',['preparation_id'])

def downgrade(): op.drop_table('preparation_artifacts')
