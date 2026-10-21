from sqlalchemy import String, Integer, Float, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class PracticeSession(Base):
    __tablename__='practice_sessions'
    id: Mapped[str] = mapped_column(String(80),primary_key=True)
    owner: Mapped[str] = mapped_column(String(160),index=True)
    practice_id: Mapped[str] = mapped_column(String(200))
    artifact_revision: Mapped[str] = mapped_column(String(64))
    seq: Mapped[int] = mapped_column(Integer,default=0)
    state: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[float] = mapped_column(Float)

class PracticeEvent(Base):
    __tablename__='practice_events'
    __table_args__=(UniqueConstraint('session_id','seq',name='uq_practice_event_seq'),)
    session_id: Mapped[str] = mapped_column(String(80),ForeignKey('practice_sessions.id'),primary_key=True)
    event_id: Mapped[str] = mapped_column(String(80),primary_key=True)
    seq: Mapped[int] = mapped_column(Integer)
    batch_id: Mapped[str] = mapped_column(String(80),index=True)
    request: Mapped[dict] = mapped_column(JSON)
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float)

class PracticeJournalEntry(Base):
    __tablename__='practice_journal_entries'
    session_id: Mapped[str] = mapped_column(String(80),ForeignKey('practice_sessions.id'),primary_key=True)
    entry_id: Mapped[str] = mapped_column(String(80),primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float)
