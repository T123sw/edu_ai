"""P4 checks, derived summaries and invalidation metadata (preferences reuse memory tables)."""
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.models import JSON_PAYLOAD

class LearningCheck(Base):
    __tablename__ = 'learning_checks'
    __table_args__ = (UniqueConstraint('owner', 'request_id', name='uq_learning_check_request'),)
    check_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(240), nullable=False)
    request_id: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    source: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    objective_ids: Mapped[list] = mapped_column(JSON_PAYLOAD, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

class LearningCheckAttempt(Base):
    __tablename__ = 'learning_check_attempts'
    __table_args__ = (UniqueConstraint('owner', 'request_id', name='uq_learning_check_attempt_request'),)
    attempt_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    check_id: Mapped[str] = mapped_column(ForeignKey('learning_checks.check_id'), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

class LearningMemoryEpoch(Base):
    __tablename__ = 'learning_memory_epochs'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

class LearningMemorySuppression(Base):
    __tablename__ = 'learning_memory_suppressions'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    field: Mapped[str] = mapped_column(String(80), primary_key=True)
    epoch: Mapped[int] = mapped_column(Integer, nullable=False)

class LearningMemoryDependency(Base):
    __tablename__ = 'learning_memory_dependencies'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    target_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)

class LearningContextSummary(Base):
    __tablename__ = 'learning_context_summaries'
    session_id: Mapped[str] = mapped_column(ForeignKey('learning_topic_sessions.session_id'), primary_key=True)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(240), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    covered_until: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    facts_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)

class LearningEnrichmentReceipt(Base):
    __tablename__ = 'learning_enrichment_receipts'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)

class LearningObservation(Base):
    __tablename__ = 'learning_observations'
    turn_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(240), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='hypothesis')

class LearningMemoryOutbox(Base):
    __tablename__ = 'learning_memory_outbox'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)

TABLES = ('learning_checks', 'learning_check_attempts', 'learning_memory_epochs', 'learning_memory_suppressions',
          'learning_memory_dependencies', 'learning_context_summaries', 'learning_enrichment_receipts', 'learning_observations', 'learning_memory_outbox')
