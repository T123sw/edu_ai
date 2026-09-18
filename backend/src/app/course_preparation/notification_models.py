from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.models import JSON_PAYLOAD

class PreparationCourseNotification(Base):
    __tablename__ = 'preparation_course_notifications'
    event_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, nullable=False)
    read_at: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
