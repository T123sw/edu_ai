from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
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


class JobRecord(Base):
    __tablename__ = "jobs"

    edu_job_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step: Mapped[str] = mapped_column(String(160), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    owner_user_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    course_id: Mapped[str | None] = mapped_column(String(200), index=True)
    scope_type: Mapped[str] = mapped_column(String(64), nullable=False, default="course")
    scope_id: Mapped[str | None] = mapped_column(String(240), index=True)
    retry_of_job_id: Mapped[str | None] = mapped_column(String(200), index=True)
    parent_job_id: Mapped[str | None] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )

    events: Mapped[list[JobEvent]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobEvent.version",
    )


class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (
        UniqueConstraint("edu_job_id", "version", name="uq_job_events_version"),
    )

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    edu_job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.edu_job_id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    step: Mapped[str] = mapped_column(String(160), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )

    job: Mapped[JobRecord] = relationship(back_populates="events")


class Material(Base):
    __tablename__ = "materials"

    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    material_type: Mapped[str] = mapped_column(String(80), primary_key=True)
    material_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="ready")
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="course")
    owner_user_id: Mapped[str | None] = mapped_column(String(160), index=True)
    scope_type: Mapped[str] = mapped_column(String(64), nullable=False, default="course")
    scope_id: Mapped[str | None] = mapped_column(String(240), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_job_id: Mapped[str | None] = mapped_column(String(200), index=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )


class MaterialVersion(Base):
    __tablename__ = "material_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["course_id", "material_type", "material_id"],
            ["materials.course_id", "materials.material_type", "materials.material_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "course_id", "material_type", "material_id", "version",
            name="uq_material_versions_version",
        ),
    )

    material_version_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    material_type: Mapped[str] = mapped_column(String(80), nullable=False)
    material_id: Mapped[str] = mapped_column(String(240), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )


class ArtifactFile(Base):
    __tablename__ = "artifact_files"
    __table_args__ = (
        ForeignKeyConstraint(
            ["course_id", "material_type", "material_id"],
            ["materials.course_id", "materials.material_type", "materials.material_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "course_id", "material_type", "material_id", "path",
            name="uq_artifact_files_path",
        ),
    )

    artifact_file_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    material_type: Mapped[str] = mapped_column(String(80), nullable=False)
    material_id: Mapped[str] = mapped_column(String(240), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(128))
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )


class MigrationQuarantine(Base):
    __tablename__ = "migration_quarantine"
    __table_args__ = (
        UniqueConstraint("domain", "source_path", name="uq_migration_quarantine_source"),
    )

    quarantine_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    quarantined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class KnowledgeLibrary(Base):
    __tablename__ = "knowledge_libraries"

    library_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    library_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    course_id: Mapped[str | None] = mapped_column(String(200), index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(160), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    library_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_libraries.library_id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id: Mapped[str] = mapped_column(String(260), primary_key=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    path: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    scope_type: Mapped[str] = mapped_column(String(64), nullable=False, default="course")
    scope_id: Mapped[str | None] = mapped_column(String(240), index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )


class KnowledgeGraphVersion(Base):
    __tablename__ = "knowledge_graph_versions"
    __table_args__ = (
        UniqueConstraint("library_id", "version", name="uq_knowledge_graph_versions_version"),
    )

    graph_version_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    library_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_libraries.library_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    source_build_id: Mapped[str | None] = mapped_column(String(200), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graph_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )


class KnowledgeBuild(Base):
    __tablename__ = "knowledge_builds"
    __table_args__ = (
        UniqueConstraint("library_id", "idempotency_key", name="uq_knowledge_builds_idempotency"),
    )

    build_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    library_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_libraries.library_id", ondelete="CASCADE"), nullable=False, index=True
    )
    triggered_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(80), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(300))
    plan_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)
    quality_score: Mapped[float | None] = mapped_column(Float)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeSourceCandidate(Base):
    __tablename__ = "knowledge_source_candidates"
    __table_args__ = (
        UniqueConstraint("build_id", "url", name="uq_knowledge_source_candidates_url"),
    )

    candidate_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    build_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_builds.build_id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[str | None] = mapped_column(String(200), index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(700), nullable=False)
    domain: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    language: Mapped[str | None] = mapped_column(String(50))
    authority_tier: Mapped[str | None] = mapped_column(String(80))
    license_info: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    review_reason: Mapped[str | None] = mapped_column(Text)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class KnowledgeQualityCheck(Base):
    __tablename__ = "knowledge_quality_checks"

    check_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    build_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_builds.build_id", ondelete="CASCADE"), nullable=False, index=True
    )
    check_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    score: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[float | None] = mapped_column(Float)
    details: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class RuntimeIndexEntry(Base):
    __tablename__ = "runtime_index_entries"

    index_name: Mapped[str] = mapped_column(String(80), primary_key=True)
    entry_key: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(160), index=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )


class AppStateRecord(Base):
    __tablename__ = "app_state_records"

    namespace: Mapped[str] = mapped_column(String(120), primary_key=True)
    record_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(160), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )


class LearningTaskModel(Base):
    __tablename__ = "learning_tasks"

    task_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    resource_refs: Mapped[list[Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=list)
    knowledge_point_ids: Mapped[list[Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[str | None] = mapped_column(String(160))


class LearningEventModel(Base):
    __tablename__ = "learning_events"

    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.task_id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    resource_ref: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LearningProgressModel(Base):
    __tablename__ = "learning_progress"

    task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.task_id", ondelete="CASCADE"), primary_key=True
    )
    student_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DurableTaskModel(Base):
    __tablename__ = "durable_tasks"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "workflow_type",
            "idempotency_key",
            name="uq_durable_tasks_idempotency",
        ),
    )

    task_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    workflow_type: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    handler_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    owner_user_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    course_id: Mapped[str | None] = mapped_column(String(200), index=True)
    scope_type: Mapped[str] = mapped_column(String(64), nullable=False, default="course")
    scope_id: Mapped[str | None] = mapped_column(String(240), index=True)
    command: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    config_snapshot_id: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(200))
    lease_expires_at: Mapped[float | None] = mapped_column(Float, index=True)
    heartbeat_at: Mapped[float | None] = mapped_column(Float)
    deadline_at: Mapped[float | None] = mapped_column(Float, index=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    progress: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    result_ref: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    error_code: Mapped[str | None] = mapped_column(String(120))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(80), nullable=False)
    started_at: Mapped[float | None] = mapped_column(Float)
    finished_at: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)
