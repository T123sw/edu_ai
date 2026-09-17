"""User disposition of sourced tutoring hypotheses; never a mastery label."""
import time
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database.models import ConversationMessage
from .db_models import LearningTopicSession


class ObservationService:
    def __init__(self,learning):self.learning=learning;self.repository=learning.session_repository

    def list(self,owner,course,topic):
        self.learning.sessions._chapter(owner,course,topic)
        found=self.repository.find(owner,course,topic)
        if found is None:return []
        with Session(self.repository.engine) as db:
            session=db.get(LearningTopicSession,found['session_id'])
            statuses=session.import_metadata.get('observation_statuses',{})
            rows=db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id==session.session_id)
                .order_by(ConversationMessage.position.desc()).limit(200)).all()
            return [{'message_id':m.message_id,**m.raw_payload['answer_result']['observation'],
                **statuses.get(m.message_id,{'status':'hypothesis','revision':0})} for m in rows
                if (m.raw_payload or {}).get('answer_result',{}).get('observation')][:20]

    def update(self,owner,course,topic,message_id,status,expected_revision):
        if status not in ('resolved','retracted'):raise HTTPException(422,'无效观察状态')
        self.learning.sessions._chapter(owner,course,topic)
        found=self.repository.find(owner,course,topic)
        if found is None:raise HTTPException(404,'教学观察不存在')
        with self.repository._write(found['session_id']) as db:
            session=db.scalar(select(LearningTopicSession).where(LearningTopicSession.session_id==found['session_id']).with_for_update())
            source=db.get(ConversationMessage,message_id)
            if source is None or source.conversation_id!=session.session_id or not (source.raw_payload or {}).get('answer_result',{}).get('observation'):
                raise HTTPException(404,'教学观察不存在')
            statuses=dict(session.import_metadata.get('observation_statuses',{}));old=statuses.get(message_id,{'status':'hypothesis','revision':0})
            if old['status']==status:return old
            if old['revision']!=expected_revision:raise HTTPException(409,'教学观察已更新，请刷新')
            value={'status':status,'revision':old['revision']+1,'updated_at':time.time()}
            statuses[message_id]=value
            self.repository._append(db,session,'observation-status:'+uuid4().hex,'user',
                '我确认此前这项教学观察'+('已解决' if status=='resolved' else '不适用，撤回')+'：'+source.raw_payload['answer_result']['observation']['text'],
                'user_content',{'observation_source':message_id,'status':status})
            session.import_metadata={**session.import_metadata,'observation_statuses':statuses,
                'summary_job':{**session.import_metadata.get('summary_job',{}),'pending':True,'revision':session.next_position}}
            return value
