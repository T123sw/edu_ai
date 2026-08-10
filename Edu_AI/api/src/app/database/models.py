from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


JSON_PAYLOAD = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'teacher', 'student')",
            name="valid_role",
        ),
    )

    user_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    username: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )

    memberships: Mapped[list[CourseMembership]] = relationship(
        back_populates="user",
        foreign_keys="CourseMembership.user_id",
    )


class Course(Base):
    __tablename__ = "courses"

    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    icon: Mapped[str] = mapped_column(String(120), nullable=False, default="menu_book")
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="#2563eb")
    cover_image_ref: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )

    objectives: Mapped[list[CourseObjective]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseObjective.position",
    )
    memberships: Mapped[list[CourseMembership]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseMembership.user_id",
    )


class CourseObjective(Base):
    __tablename__ = "course_objectives"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "position",
            name="uq_course_objectives_course_position",
        ),
        CheckConstraint("position >= 0", name="non_negative_position"),
    )

    objective_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)

    course: Mapped[Course] = relationship(back_populates="objectives")


class CourseMembership(Base):
    __tablename__ = "course_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')",
            name="valid_role",
        ),
    )

    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.course_id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    # Audit actors can be users or stable system identifiers such as
    # "development-auto-enroll" from the existing JSON store.
    added_by: Mapped[str | None] = mapped_column(String(160))

    course: Mapped[Course] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(
        back_populates="memberships",
        foreign_keys=[user_id],
    )


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    owner: Mapped[str | None] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    course_id: Mapped[str | None] = mapped_column(String(200), index=True)
    scope_type: Mapped[str] = mapped_column(String(64), nullable=False, default="course")
    scope_id: Mapped[str | None] = mapped_column(String(240), index=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )

    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.position",
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "position", name="uq_conversation_messages_position"
        ),
        CheckConstraint("position >= 0", name="non_negative_position"),
    )

    message_id: Mapped[str] = mapped_column(String(260), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    message_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
