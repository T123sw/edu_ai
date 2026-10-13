"""Opt-in check coaching and a durable, per-attempt feedback outbox."""
from sqlalchemy import ForeignKey, Integer, String, Float, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.models import JSON_PAYLOAD


class LearningTeachingActivity(Base):
    __tablename__ = 'learning_teaching_activities'
    check_id: Mapped[str] = mapped_column(ForeignKey('learning_checks.check_id'), primary_key=True)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)


class LearningTeachingFeedback(Base):
    __tablename__ = 'learning_teaching_feedback'
    __table_args__ = (Index('ix_learning_teaching_feedback_pending', 'status', 'created_at'),)
    attempt_id: Mapped[str] = mapped_column(ForeignKey('learning_check_attempts.attempt_id'), primary_key=True)
    check_id: Mapped[str] = mapped_column(ForeignKey('learning_checks.check_id'), nullable=False)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    request: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    turn_id: Mapped[str | None] = mapped_column(String(80))
    error: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[float] = mapped_column(Float, nullable=False)


TABLES = ('learning_teaching_activities', 'learning_teaching_feedback')
