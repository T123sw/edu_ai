"""Durable personal resource production and immutable delivery manifests."""
from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.models import JSON_PAYLOAD

class ProductionRun(Base):
    __tablename__ = 'course_production_runs'
    preparation_id: Mapped[str] = mapped_column(ForeignKey('course_preparations.preparation_id'), primary_key=True)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(240), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(200), nullable=False)
    token: Mapped[str] = mapped_column(String(40), nullable=False, default='')
    lease_until: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    deadline: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    state: Mapped[str] = mapped_column(String(24), nullable=False, default='accepted')
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    result: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False, default=dict)

class PersonalManifestHead(Base):
    __tablename__ = 'course_personal_manifest_heads'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

class PersonalManifestVersion(Base):
    __tablename__ = 'course_personal_manifest_versions'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)

class PreparationNotification(Base):
    __tablename__ = 'learning_preparation_notifications'
    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    preparation_id: Mapped[str] = mapped_column(String(200), nullable=False)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    read_at: Mapped[float] = mapped_column(Float, nullable=False, default=0)

TABLES = ('course_production_runs','course_personal_manifest_heads','course_personal_manifest_versions','learning_preparation_notifications')
