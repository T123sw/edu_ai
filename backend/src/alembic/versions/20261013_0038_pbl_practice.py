"""Versioned personal programming exercises and immutable browser reports."""
from alembic import op
import sqlalchemy as sa

revision='20261013_0038'
down_revision='20261013_0037'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('pbl_exercises',
        sa.Column('id',sa.String(80),primary_key=True),sa.Column('owner',sa.String(160),nullable=False),
        sa.Column('request_id',sa.String(80),nullable=False),sa.Column('topic',sa.Text(),nullable=False),
        sa.Column('generation_state',sa.String(32),nullable=False),sa.Column('current_job_id',sa.String(200),nullable=False),
        sa.Column('candidate_private',sa.JSON()),sa.Column('checkpoint',sa.JSON()),
        sa.Column('repair_count',sa.Integer(),nullable=False),sa.Column('artifact_public',sa.JSON()),
        sa.Column('artifact_version',sa.Integer(),nullable=False),sa.Column('template_version',sa.String(80)),
        sa.Column('validation_report',sa.JSON()),sa.Column('created_at',sa.Float(),nullable=False),
        sa.Column('updated_at',sa.Float(),nullable=False),sa.UniqueConstraint('owner','request_id',name='uq_pbl_request'))
    op.create_index('ix_pbl_exercises_owner','pbl_exercises',['owner'])
    op.create_table('pbl_workspaces',
        sa.Column('owner',sa.String(160),primary_key=True),
        sa.Column('exercise_id',sa.String(80),sa.ForeignKey('pbl_exercises.id'),primary_key=True),
        sa.Column('artifact_version',sa.Integer(),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('files',sa.JSON(),nullable=False),sa.Column('active_task_id',sa.String(80),nullable=False),
        sa.Column('custom_input_text',sa.Text(),nullable=False),sa.Column('last_mutation_id',sa.String(80)),
        sa.Column('last_mutation_payload',sa.JSON()),sa.Column('updated_at',sa.Float(),nullable=False))
    op.create_table('pbl_runs',sa.Column('owner',sa.String(160),primary_key=True),
        sa.Column('exercise_id',sa.String(80),sa.ForeignKey('pbl_exercises.id'),primary_key=True),
        sa.Column('run_id',sa.String(80),primary_key=True),sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.Float(),nullable=False))

def downgrade():
    op.drop_table('pbl_runs')
    op.drop_table('pbl_workspaces')
    op.drop_index('ix_pbl_exercises_owner',table_name='pbl_exercises')
    op.drop_table('pbl_exercises')
