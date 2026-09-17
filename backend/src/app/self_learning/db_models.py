"""Learning session indexes; original messages use the existing conversation tables."""
from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models import JSON_PAYLOAD


class LearningTopicSession(Base):
    __tablename__ = 'learning_topic_sessions'
    __table_args__ = (
        UniqueConstraint('owner', 'course_id', 'topic_id', name='uq_learning_topic_owner'),
        CheckConstraint('next_position >= 0', name='learning_position_nonnegative'),
    )
    session_id: Mapped[str] = mapped_column(ForeignKey('conversations.conversation_id', ondelete='CASCADE'), primary_key=True)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(240), nullable=False)
    next_position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    import_metadata: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)


class LearningAgentTurn(Base):
    __tablename__ = 'learning_agent_turns'
    __table_args__ = (
        CheckConstraint("status IN ('running', 'succeeded', 'failed')", name='learning_turn_status'),
    )
    session_id: Mapped[str] = mapped_column(ForeignKey('learning_topic_sessions.session_id', ondelete='CASCADE'), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    lease_until: Mapped[float] = mapped_column(Float, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(240), nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(String(80))


class LearningFactRevision(Base):
    __tablename__ = 'self_learning_fact_revisions'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LearningEventRecord(Base):
    __tablename__ = 'self_learning_events'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(240), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    receipt: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)


class LearningResourceState(Base):
    __tablename__ = 'self_learning_resource_states'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    resource_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    resource_ref: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    state: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LearningReadingStream(Base):
    __tablename__ = 'self_learning_reading_streams'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    resource_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    stream_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    locator: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)


class LearningTopicState(Base):
    __tablename__ = 'self_learning_topic_states'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    topic_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    value: Mapped[str] = mapped_column(String(24), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LearningProgressOutbox(Base):
    __tablename__ = 'learning_progress_outbox'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)


class LearningAnswerRun(Base):
    __tablename__ = 'learning_answer_runs'
    __table_args__ = (UniqueConstraint('session_id', 'request_id', name='uq_learning_answer_request'),)
    turn_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('learning_topic_sessions.session_id', ondelete='CASCADE'), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(240), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False, default='')
    lease_until: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    deadline: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checkpoint: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON_PAYLOAD)
    error_code: Mapped[str | None] = mapped_column(String(80))


class LearningAgentToolCall(Base):
    __tablename__ = 'learning_agent_tool_calls'
    turn_id: Mapped[str] = mapped_column(ForeignKey('learning_answer_runs.turn_id', ondelete='CASCADE'), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)


class LearningAgentOutbox(Base):
    __tablename__ = 'learning_agent_outbox'
    event_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    turn_id: Mapped[str] = mapped_column(ForeignKey('learning_answer_runs.turn_id', ondelete='CASCADE'), nullable=False)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)

# Register P4 tables on the same application metadata for migration/test tooling.
from . import enrichment_models as _enrichment_models

from app.course_preparation import production_models  # noqa: F401
