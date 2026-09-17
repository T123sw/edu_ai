"""Audited legacy import and persistent rollout scopes."""
from sqlalchemy import String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.models import JSON_PAYLOAD

class LearningMigrationLedger(Base):
    __tablename__='learning_migration_ledger'
    owner: Mapped[str]=mapped_column(String(160),primary_key=True)
    course_id: Mapped[str]=mapped_column(String(200),primary_key=True)
    source_hash: Mapped[str]=mapped_column(String(64),nullable=False)
    source: Mapped[dict]=mapped_column(JSON_PAYLOAD,nullable=False)
    result: Mapped[dict]=mapped_column(JSON_PAYLOAD,nullable=False)
    updated_at: Mapped[float]=mapped_column(Float,nullable=False)

class LearningRolloutScope(Base):
    __tablename__='learning_rollout_scopes'
    owner: Mapped[str]=mapped_column(String(160),primary_key=True)
    course_id: Mapped[str]=mapped_column(String(200),primary_key=True)
    phase: Mapped[int]=mapped_column(Integer,nullable=False)
    source_hash: Mapped[str]=mapped_column(String(64),nullable=False)
    activated_at: Mapped[float]=mapped_column(Float,nullable=False)

TABLES=('learning_migration_ledger','learning_rollout_scopes')
