"""Idempotent preparation notifications do not append dialogue or move reading state."""
import time
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import PreparationDeliveryEvent, User, CourseMembership
from .notification_models import PreparationCourseNotification as LearningNotification
from app.self_learning.postgres_repository import SessionRepository
from app.self_learning.prepared_courses import PreparedCourses


class NotificationService:
    def __init__(self, engine):
        self.engine=engine
        self.repository=SessionRepository(engine)

    def consume(self, limit=100):
        count=0
        with self.repository._write('preparation-notifications') as db:
            events=db.scalars(select(PreparationDeliveryEvent).where(PreparationDeliveryEvent.delivered.is_(False))
                .order_by(PreparationDeliveryEvent.created_at).limit(limit).with_for_update(skip_locked=True)).all()
            for event in events:
                user=db.get(User,event.owner_user_id)
                if user is None: continue
                if db.get(LearningNotification,event.event_id) is None:
                    db.add(LearningNotification(event_id=event.event_id,owner=user.username,course_id=event.course_id,
                        payload=event.payload,created_at=time.time()))
                    count+=1
                event.delivered=True
        return count

    def list(self,owner,course_id=None):
        self.consume()
        prepared=PreparedCourses(self.engine)
        with Session(self.engine) as db:
            query=select(LearningNotification).where(LearningNotification.owner==owner)
            if course_id: query=query.where(LearningNotification.course_id==course_id)
            items=[]
            for row in db.scalars(query.order_by(LearningNotification.created_at.desc()).limit(100)):
                if prepared.lookup(owner,row.course_id):
                    items.append({'event_id':row.event_id,'course_id':row.course_id,'result_ref':row.payload['result_ref'],
                        'read':row.read_at is not None,'created_at':row.created_at})
            return items

    def mark_read(self,owner,event_id):
        with self.repository._write('notification:'+event_id) as db:
            row=db.get(LearningNotification,event_id)
            if row is None or row.owner!=owner: raise PermissionError('NOTIFICATION_UNAVAILABLE')
            if PreparedCourses(self.engine).lookup(owner,row.course_id) is None: raise PermissionError('COURSE_UNAVAILABLE')
            row.read_at=row.read_at or time.time()
