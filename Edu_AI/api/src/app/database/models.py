from __future__ import annotations

from datetime import datetime, timezone
import secrets
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
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


def default_course_code() -> str:
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


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
    course_code: Mapped[str] = mapped_column(
        String(8), nullable=False, unique=True, index=True, default=default_course_code
    )
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
    __table_args__ = (
        CheckConstraint(
            "origin_type IN ('personal', 'standard', 'legacy_shared')",
            name="materials_valid_origin_type",
        ),
        CheckConstraint(
            "standard_kind IS NULL OR standard_kind IN ('classroom', 'study_guide', 'practice')",
            name="materials_valid_standard_kind",
        ),
        CheckConstraint(
            "current_review_status IN ('not_required', 'pending', 'approved', 'rejected')",
            name="materials_valid_review_status",
        ),
    )

    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    material_type: Mapped[str] = mapped_column(String(80), primary_key=True)
    material_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="ready")
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="course")
    origin_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="personal", index=True
    )
    standard_kind: Mapped[str | None] = mapped_column(String(32), index=True)
    generation_batch_id: Mapped[str | None] = mapped_column(String(200), index=True)
    current_review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_required", index=True
    )
    approved_version: Mapped[int | None] = mapped_column(Integer)
    approved_by: Mapped[str | None] = mapped_column(String(160))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
        CheckConstraint(
            "origin_type IN ('personal', 'standard', 'legacy_shared')",
            name="material_versions_valid_origin_type",
        ),
        CheckConstraint(
            "standard_kind IS NULL OR standard_kind IN ('classroom', 'study_guide', 'practice')",
            name="material_versions_valid_standard_kind",
        ),
        CheckConstraint(
            "review_status IN ('not_required', 'pending', 'approved', 'rejected')",
            name="material_versions_valid_review_status",
        ),
    )

    material_version_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    material_type: Mapped[str] = mapped_column(String(80), nullable=False)
    material_id: Mapped[str] = mapped_column(String(240), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="personal", index=True
    )
    standard_kind: Mapped[str | None] = mapped_column(String(32), index=True)
    generation_batch_id: Mapped[str | None] = mapped_column(String(200), index=True)
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_required", index=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(160))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
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
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    graph_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    confirmed_graph_revision: Mapped[int | None] = mapped_column(Integer)
    confirmed_by: Mapped[str | None] = mapped_column(String(160), index=True)
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
    __table_args__ = (
        CheckConstraint(
            "task_type IN ('reading', 'assessed')",
            name="learning_tasks_valid_task_type",
        ),
    )

    task_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, default="assessed")
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    resource_refs: Mapped[list[Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=list)
    knowledge_point_ids: Mapped[list[Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[str | None] = mapped_column(String(160))


class StandardResourceBatch(Base):
    __tablename__ = "standard_resource_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'partial', 'completed', 'failed')",
            name="standard_resource_batches_valid_status",
        ),
    )

    batch_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    running_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StandardResourceBatchItem(Base):
    __tablename__ = "standard_resource_batch_items"
    __table_args__ = (
        UniqueConstraint(
            "batch_id", "leaf_id", "standard_kind",
            name="uq_standard_resource_batch_items_slot",
        ),
        CheckConstraint(
            "standard_kind IN ('classroom', 'study_guide', 'practice')",
            name="standard_resource_batch_items_valid_kind",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="standard_resource_batch_items_valid_status",
        ),
    )

    batch_item_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("standard_resource_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leaf_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    leaf_title: Mapped[str] = mapped_column(String(500), nullable=False)
    standard_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    material_type: Mapped[str] = mapped_column(String(80), nullable=False)
    material_id: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    job_id: Mapped[str | None] = mapped_column(String(200), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LearningTaskResourceSnapshot(Base):
    __tablename__ = "learning_task_resource_snapshots"
    __table_args__ = (
        UniqueConstraint("task_id", "position", name="uq_learning_task_snapshots_position"),
    )

    snapshot_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.task_id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    source_material_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_material_id: Mapped[str] = mapped_column(String(240), nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_type: Mapped[str] = mapped_column(String(32), nullable=False)
    standard_kind: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=dict
    )
    file_refs: Mapped[list[Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
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
    completion_basis: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssessmentModel(Base):
    __tablename__ = "assessments"

    assessment_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.task_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(String(200), index=True)


class AssessmentVersionModel(Base):
    __tablename__ = "assessment_versions"
    __table_args__ = (
        UniqueConstraint("assessment_id", "version_number", name="uq_assessment_versions_number"),
    )

    assessment_version_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(
        ForeignKey("assessments.assessment_id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    assessment_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    pass_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    mastery_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    score_policy: Mapped[str] = mapped_column(String(40), nullable=False)
    answer_reveal_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, nullable=False)
    shuffle_options: Mapped[bool] = mapped_column(Boolean, nullable=False)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssessmentItemModel(Base):
    __tablename__ = "assessment_items"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id", "position", name="uq_assessment_items_position"
        ),
    )

    assessment_item_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    assessment_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_versions.assessment_version_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)
    scoring_key: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)
    rubric: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    grading_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    knowledge_point_ids: Mapped[list[Any]] = mapped_column(JSON_PAYLOAD, nullable=False)
    source_refs: Mapped[list[Any]] = mapped_column(JSON_PAYLOAD, nullable=False)
    source_exposure_state: Mapped[str] = mapped_column(String(32), nullable=False)
    created_origin: Mapped[str] = mapped_column(String(32), nullable=False)


class AssessmentAssignmentModel(Base):
    __tablename__ = "assessment_assignments"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "student_id", "cycle_number", name="uq_assessment_assignment_cycle"
        ),
    )

    assessment_assignment_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    assessment_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_versions.assessment_version_id"), nullable=False, index=True
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_attempt_id: Mapped[str | None] = mapped_column(String(200))
    best_final_score: Mapped[float | None] = mapped_column(Float)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    answers_revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssessmentAttemptModel(Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint(
            "assessment_assignment_id", "attempt_number", name="uq_assessment_attempt_number"
        ),
    )

    attempt_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    assessment_assignment_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_assignments.assessment_assignment_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_version_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_score: Mapped[float | None] = mapped_column(Float)
    final_score: Mapped[float | None] = mapped_column(Float)
    result: Mapped[str | None] = mapped_column(String(32))
    submission_idempotency_key: Mapped[str | None] = mapped_column(String(300))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_by: Mapped[str | None] = mapped_column(String(160))
    invalidation_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssessmentAnswerModel(Base):
    __tablename__ = "assessment_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "assessment_item_id", name="uq_assessment_answer_item"),
    )

    answer_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.attempt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_item_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_items.assessment_item_id"), nullable=False, index=True
    )
    answer: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)
    artifact_refs: Mapped[list[Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=list)
    auto_score: Mapped[float | None] = mapped_column(Float)
    ai_suggestion: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    final_score: Mapped[float | None] = mapped_column(Float)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssessmentReviewModel(Base):
    __tablename__ = "assessment_reviews"

    review_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.attempt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("assessment_items.assessment_item_id"), index=True
    )
    reviewer_id: Mapped[str] = mapped_column(String(160), nullable=False)
    previous_score: Mapped[float | None] = mapped_column(Float)
    new_score: Mapped[float | None] = mapped_column(Float)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    comment_private: Mapped[str] = mapped_column(Text, nullable=False, default="")
    comment_student_visible: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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


class ConversationEpisode(Base):
    __tablename__ = "conversation_episodes"
    __table_args__ = (
        Index("ix_conversation_episodes_owner_course", "owner_user_id", "course_id"),
    )

    episode_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    owner_user_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    course_id: Mapped[str | None] = mapped_column(String(200), index=True)
    message_start_position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_end_position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    salient_points: Mapped[list[Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=list)
    extractor: Mapped[str] = mapped_column(String(120), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    visibility: Mapped[str] = mapped_column(String(64), nullable=False, default="private")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class AgentMemoryItem(Base):
    __tablename__ = "agent_memory_items"
    __table_args__ = (
        Index(
            "ix_agent_memory_items_recall_scope",
            "subject_user_id",
            "course_id",
            "status",
            "visibility",
        ),
        UniqueConstraint("fingerprint", name="uq_agent_memory_items_fingerprint"),
    )

    memory_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_user_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    owner_user_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    course_id: Mapped[str | None] = mapped_column(String(200), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(200), index=True)
    task_id: Mapped[str | None] = mapped_column(String(200), index=True)
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fact_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    visibility: Mapped[str] = mapped_column(String(64), nullable=False, default="private")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(240), nullable=False)
    source_span: Mapped[str] = mapped_column(Text, nullable=False)
    profile_axis: Mapped[str | None] = mapped_column(String(80), index=True)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[Any] | None] = mapped_column(JSON_PAYLOAD)
    embedding_model: Mapped[str | None] = mapped_column(String(200))
    extractor: Mapped[str] = mapped_column(String(120), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(120), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class UserProfileFact(Base):
    __tablename__ = "user_profile_facts"
    __table_args__ = (
        Index("ix_user_profile_facts_scope", "subject_user_id", "course_id", "status"),
    )

    profile_fact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_user_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    course_id: Mapped[str | None] = mapped_column(String(200), index=True)
    course_scope_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    profile_axis: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_memory_ids: Mapped[list[Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    visibility: Mapped[str] = mapped_column(String(64), nullable=False, default="private")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class AgentMemoryAuditEvent(Base):
    __tablename__ = "agent_memory_audit_events"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_user_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(200), index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    decision: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ResourceLearningManifestModel(Base):
    __tablename__ = "resource_learning_manifests"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "resource_id",
            "resource_version",
            name="uq_resource_learning_manifest_version",
        ),
    )

    manifest_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    resource_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ResourceLearningSessionModel(Base):
    __tablename__ = "resource_learning_sessions"
    __table_args__ = (
        Index(
            "ix_resource_learning_sessions_active_scope",
            "student_id",
            "course_id",
            "resource_id",
            "resource_version",
            "status",
        ),
    )

    session_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    resource_version: Mapped[int] = mapped_column(Integer, nullable=False)
    student_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalid_reason: Mapped[str | None] = mapped_column(Text)


class ResourceLearningEventModel(Base):
    __tablename__ = "resource_learning_events"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "sequence_number",
            name="uq_resource_learning_events_session_sequence",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("resource_learning_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    scene_id: Mapped[str] = mapped_column(String(240), nullable=False)
    timeline_from_ms: Mapped[int | None] = mapped_column(Integer)
    timeline_to_ms: Mapped[int | None] = mapped_column(Integer)
    action_id: Mapped[str | None] = mapped_column(String(240))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)


class ResourceLearningCoverageModel(Base):
    __tablename__ = "resource_learning_coverage"

    student_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    resource_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    scene_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    covered_ranges_json: Mapped[list[Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=list
    )
    covered_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ResourceQuestionAttemptModel(Base):
    __tablename__ = "resource_question_attempts"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "course_id",
            "resource_id",
            "resource_version",
            "question_id",
            "attempt_number",
            name="uq_resource_question_attempt_number",
        ),
        UniqueConstraint(
            "student_id",
            "course_id",
            "resource_id",
            "resource_version",
            "idempotency_key",
            "question_id",
            name="uq_resource_question_attempt_idempotency",
        ),
    )

    question_attempt_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    resource_version: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[str] = mapped_column(String(240), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    answer_payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    knowledge_point_ids: Mapped[list[Any]] = mapped_column(
        JSON_PAYLOAD, nullable=False, default=list
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResourceLearningProgressModel(Base):
    __tablename__ = "resource_learning_progress"

    student_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    resource_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    explanation_covered_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    explanation_total_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    explanation_coverage_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    required_question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answered_question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question_completion_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    correct_count_first: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count_latest: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    demo_view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    demo_interaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class TaskResourceEvidenceRefModel(Base):
    __tablename__ = "task_resource_evidence_refs"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "student_id",
            "resource_id",
            "resource_version",
            name="uq_task_resource_evidence_version",
        ),
    )

    evidence_ref_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(240), nullable=False)
    resource_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resource_progress_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    resource_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    condition_status: Mapped[str] = mapped_column(String(32), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
