"""At-least-once preparation event consumption, separate from conversation messages."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database import CoursePreparationEventRecord as Event, CoursePreparationRecord as Preparation
from app.course_preparation.production_models import ProductionRun, PreparationNotification as Notice

class NotificationService:
    def __init__(self, adapter):
        self.adapter, self.service = adapter, adapter.service

    def consume(self, event_id):
        # Event content and identity are reloaded from the committed producer outbox.
        with self.service.write() as db:
            if db.get(Notice,event_id):
                return False
            event=db.get(Event,event_id)
            if event is None or event.event_type not in {'succeeded','failed','canceled'}:
                return False
            run=db.get(ProductionRun,event.preparation_id)
            record=db.get(Preparation,event.preparation_id)
            if run is None or event.attempt_no != record.current_attempt_no or event.revision != record.revision:
                return False
            db.add(Notice(event_id=event_id,preparation_id=event.preparation_id,owner=run.owner,course_id=run.course_id,
                attempt_no=event.attempt_no,revision=event.revision,payload={'type':event.event_type,
                    'origin_ref':record.request_payload.get('origin'),'topic_id':run.topic_id,'result':event.payload}))
            return True

    def drain(self):
        with Session(self.service.engine) as db:
            ids=list(db.scalars(select(Event.event_id).join(ProductionRun,ProductionRun.preparation_id==Event.preparation_id)
                .outerjoin(Notice,Notice.event_id==Event.event_id).where(Notice.event_id.is_(None),Event.event_type.in_(['succeeded','failed','canceled']))))
        return sum(self.consume(value) for value in ids)

    def list(self, owner, course):
        self.adapter.learning.require(course,owner)
        with Session(self.service.engine) as db:
            rows=db.scalars(select(Notice).join(Preparation,Preparation.preparation_id==Notice.preparation_id).where(
                Notice.owner==owner,Notice.course_id==course,Notice.attempt_no==Preparation.current_attempt_no,
                Notice.revision==Preparation.revision).order_by(Notice.revision,Notice.event_id)).all()
            result=[]
            for row in rows:
                payload=dict(row.payload)
                refs=payload.get('result',{}).get('resource_refs',[])
                try:
                    for ref in refs:
                        self.adapter.learning.material(course,ref['material_type'],ref['material_id'],owner)
                except HTTPException:
                    payload={'type':'unavailable','topic_id':payload['topic_id'],'result':{'error_code':'RESULT_UNAVAILABLE'}}
                result.append({'notification_id':row.event_id,'preparation_id':row.preparation_id,'read':bool(row.read_at),**payload})
            return {'items':result}

    def mark_read(self, owner, notification_id):
        with self.service.write() as db:
            row=db.get(Notice,notification_id)
            if row is None or row.owner != owner:
                raise HTTPException(404)
            self.adapter.learning.require(row.course_id,owner)
            row.read_at=self.service.clock()
        return {'saved':True}
