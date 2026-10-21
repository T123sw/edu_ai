from __future__ import annotations
import hashlib
import json
import time
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.database.session import database_session
from .db_models import PracticeSession, PracticeEvent, PracticeJournalEntry
from .bundle import replay
from .contracts import EventBatch
from .verify import verify

class SessionConflict(ValueError): pass
class SessionNotFound(LookupError): pass

class GuidedRepository:
    def __init__(self,engine=None):self.engine=engine
    def transaction(self):return database_session(engine=self.engine)
    @staticmethod
    def payload(row):return {'session_id':row.id,'revision':row.artifact_revision,'saved_seq':row.seq,'state':row.state}
    @staticmethod
    def owned(db,owner,practice,identifier,locking=False):
        query=select(PracticeSession).where(PracticeSession.id==identifier,PracticeSession.owner==owner,PracticeSession.practice_id==practice)
        row=db.scalar(query.with_for_update() if locking else query)
        if row is None:raise SessionNotFound('实验会话不存在或无权访问')
        return row
    def get(self,owner,practice,identifier):
        with self.transaction() as db:return self.payload(self.owned(db,owner,practice,identifier))
    def open(self,owner,practice,manifest):
        identifier='ps_'+hashlib.sha256(f'{owner}:{practice}:{manifest["revision"]}'.encode()).hexdigest()[:40]
        try:
            with self.transaction() as db:
                row=db.get(PracticeSession,identifier)
                if row is None:
                    row=PracticeSession(id=identifier,owner=owner,practice_id=practice,artifact_revision=manifest['revision'],seq=0,state=replay(manifest),updated_at=time.time());db.add(row);db.flush()
        except IntegrityError:pass
        return self.get(owner,practice,identifier)
    def append(self,owner,practice,identifier,manifest,batch):
        batch=EventBatch.model_validate(batch);payload=batch.model_dump(exclude_none=True)
        if len(json.dumps(payload))>150000:raise ValueError('操作批次过大')
        commands=payload['commands'];ids=[c['id'] for c in commands]
        if len(set(ids))!=len(ids):raise ValueError('操作编号重复')
        with self.transaction() as db:
            row=self.owned(db,owner,practice,identifier,True)
            receipt=db.scalar(select(PracticeEvent).where(PracticeEvent.session_id==identifier,PracticeEvent.batch_id==batch.batch_id).order_by(PracticeEvent.seq.desc()).limit(1))
            if receipt:
                if receipt.request!=payload:raise SessionConflict('相同批次编号不能提交不同内容')
                return receipt.response
            if row.artifact_revision!=manifest['revision'] or batch.revision!=row.artifact_revision:raise SessionConflict('实验版本已改变')
            if row.seq!=batch.expected_seq:raise SessionConflict('实验已在其他页面更新；本地操作已保留，请重新读取或另存本地记录')
            if db.scalar(select(PracticeEvent.event_id).where(PracticeEvent.session_id==identifier,PracticeEvent.event_id.in_(ids)).limit(1)):raise SessionConflict('操作已经保存，不能重复执行')
            state=replay(manifest,row.state,commands);verify(manifest,state)
            changed=db.execute(update(PracticeSession).where(PracticeSession.id==identifier,PracticeSession.seq==batch.expected_seq).values(seq=state['seq'],state=state,updated_at=time.time()),execution_options={'synchronize_session':False})
            if not changed.rowcount:raise SessionConflict('会话保存冲突，本地操作已保留')
            response={'session_id':identifier,'revision':manifest['revision'],'saved_seq':state['seq'],'state':state}
            # Store one durable receipt per command. Only the last carries the batch response.
            for i,c in enumerate(commands):db.add(PracticeEvent(session_id=identifier,event_id=c['id'],seq=batch.expected_seq+i+1,batch_id=batch.batch_id,request=payload if i==len(commands)-1 else {'command':c},response=response if i==len(commands)-1 else {},created_at=time.time()))
            db.flush();return response

    def add_journal(self,owner,practice,identifier,kind,payload):
        from uuid import uuid4
        with self.transaction() as db:
            self.owned(db,owner,practice,identifier)
            db.add(PracticeJournalEntry(session_id=identifier,entry_id=uuid4().hex,kind=kind,payload=payload,created_at=time.time()))
        return self.journal(owner,practice)

    def journal(self,owner,practice):
        with self.transaction() as db:
            rows=db.scalars(select(PracticeJournalEntry).join(PracticeSession,PracticeSession.id==PracticeJournalEntry.session_id).where(PracticeSession.owner==owner,PracticeSession.practice_id==practice).order_by(PracticeJournalEntry.created_at,PracticeJournalEntry.entry_id)).all()
            return {'observations':[row.payload for row in rows if row.kind=='observation'],'messages':[message for row in rows if row.kind=='turn' for message in row.payload['messages']]}
