"""Private generation state and public, versioned practice data."""
from sqlalchemy import Float, Integer, JSON, String, Text, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class PblExercise(Base):
    __tablename__ = 'pbl_exercises'
    __table_args__ = (UniqueConstraint('owner', 'request_id', name='uq_pbl_request'),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner: Mapped[str] = mapped_column(String(160), index=True)
    request_id: Mapped[str] = mapped_column(String(80))
    topic: Mapped[str] = mapped_column(Text)
    generation_state: Mapped[str] = mapped_column(String(32), default='queued')
    current_job_id: Mapped[str] = mapped_column(String(200))
    candidate_private: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    checkpoint: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    repair_count: Mapped[int] = mapped_column(Integer, default=0)
    artifact_public: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    artifact_version: Mapped[int] = mapped_column(Integer, default=0)
    template_version: Mapped[str | None] = mapped_column(String(80))
    validation_report: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)

class PblWorkspace(Base):
    __tablename__ = 'pbl_workspaces'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    exercise_id: Mapped[str] = mapped_column(String(80), ForeignKey('pbl_exercises.id'), primary_key=True)
    artifact_version: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    files: Mapped[dict] = mapped_column(JSON(none_as_null=True))
    active_task_id: Mapped[str] = mapped_column(String(80))
    custom_input_text: Mapped[str] = mapped_column(Text)
    last_mutation_id: Mapped[str | None] = mapped_column(String(80))
    last_mutation_payload: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    updated_at: Mapped[float] = mapped_column(Float)

class PblRun(Base):
    __tablename__ = 'pbl_runs'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    exercise_id: Mapped[str] = mapped_column(String(80), ForeignKey('pbl_exercises.id'), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[float] = mapped_column(Float)

class PblTutorTurn(Base):
    __tablename__ = 'pbl_tutor_turns'
    owner: Mapped[str] = mapped_column(String(160), primary_key=True)
    exercise_id: Mapped[str] = mapped_column(String(80), ForeignKey('pbl_exercises.id'), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    artifact_version: Mapped[int] = mapped_column(Integer)
    task_id: Mapped[str] = mapped_column(String(200))
    request: Mapped[dict] = mapped_column(JSON(none_as_null=True))
    response: Mapped[dict] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[float] = mapped_column(Float)
