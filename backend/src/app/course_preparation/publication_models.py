"""Published course versions are independent of each learner's private pointer."""
from sqlalchemy import String,Integer,Float,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from app.database.models import Base,JSON_PAYLOAD

class PublishedPreparationManifest(Base):
    __tablename__='published_preparation_manifests'
    course_id:Mapped[str]=mapped_column(ForeignKey('courses.course_id',ondelete='CASCADE'),primary_key=True)
    version:Mapped[int]=mapped_column(Integer,primary_key=True)
    source_owner_user_id:Mapped[str]=mapped_column(ForeignKey('users.user_id'),nullable=False)
    source_digest:Mapped[str]=mapped_column(String(64),nullable=False)
    payload:Mapped[dict]=mapped_column(JSON_PAYLOAD,nullable=False)
    content_digest:Mapped[str]=mapped_column(String(64),nullable=False)
    created_at:Mapped[float]=mapped_column(Float,nullable=False)

    @property
    def owner_user_id(self):return self.source_owner_user_id

class PublishedPreparationPointer(Base):
    __tablename__='published_preparation_pointers'
    course_id:Mapped[str]=mapped_column(ForeignKey('courses.course_id',ondelete='CASCADE'),primary_key=True)
    version:Mapped[int]=mapped_column(Integer,nullable=False)
