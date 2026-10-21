from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import threading
import time
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, delete
from app.database.session import database_session
from app.database.models import AppStateRecord, DurableTaskModel
from app.exam_generation.repository import NAMESPACE
from app.exam_generation.titles import paper_title
from .paper import build, validate_answer, objective

RUN='exam_practice_run_v1'
TURN='exam_practice_turn_v1'
PAPER='exam_practice_paper_v1'
_local_lock=threading.RLock()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def public_turn(value):
    return {k:v for k,v in value.items() if k not in {'context','fingerprint','history'}}

class PracticeService:
    def __init__(self, engine=None):self.engine=engine

    @contextmanager
    def locked(self, owner, paper_id, *, sources=False, ready=True):
        # The generation row is the common fence for runs, drafts and chat.
        with _local_lock, database_session(engine=self.engine) as db:
            row=db.execute(select(AppStateRecord.record_key,AppStateRecord.payload['request'],
                AppStateRecord.payload['sources']).where(AppStateRecord.namespace==NAMESPACE,
                AppStateRecord.record_key==paper_id,AppStateRecord.owner_user_id==owner).with_for_update()).first()
            if not row:raise HTTPException(404,'试卷不存在或无权访问')
            if not ready:
                yield db,None,{},{}
                return
            snapshot=db.get(AppStateRecord,(PAPER,paper_id))
            if snapshot is None:
                record=deepcopy(db.get(AppStateRecord,(NAMESPACE,paper_id)).payload)
                record['id']=paper_id
                paper,questions=build(record)
                self.put(db,PAPER,owner,paper_id,{'paper_id':paper_id,'paper':paper,'questions':questions})
            else:
                paper,questions=deepcopy(snapshot.payload['paper']),deepcopy(snapshot.payload['questions'])
                record={'id':paper_id}
            # Old practice snapshots may still contain the generic generation prompt.
            # Display metadata can change without changing the frozen questions/version.
            paper['title']=paper_title(row[1],row[2])
            if sources and 'parsed_sources' not in record:
                record['parsed_sources']=db.scalar(select(AppStateRecord.payload['parsed_sources']).where(
                    AppStateRecord.namespace==NAMESPACE,AppStateRecord.record_key==paper_id,AppStateRecord.owner_user_id==owner)) or []
            yield db,paper,questions,record

    def record(self, db, namespace, owner, key, paper_id):
        row=db.get(AppStateRecord,(namespace,key))
        if not row or row.owner_user_id!=owner or row.payload.get('paper_id')!=paper_id:
            raise HTTPException(404,'记录不存在或无权访问')
        return row

    def put(self, db, namespace, owner, key, value):
        row=db.get(AppStateRecord,(namespace,key))
        if row:row.payload=deepcopy(value)
        else:db.add(AppStateRecord(namespace=namespace,record_key=key,owner_user_id=owner,payload=deepcopy(value)))

    def rows(self, db, namespace, owner, paper_id):
        return list(db.scalars(select(AppStateRecord).where(AppStateRecord.namespace==namespace,
            AppStateRecord.owner_user_id==owner,AppStateRecord.payload['paper_id'].as_string()==paper_id).order_by(AppStateRecord.created_at)))

    def queue(self, db, owner, paper_id, command):
        tid='examwork_'+uuid4().hex
        now=time.time()
        db.add(DurableTaskModel(task_id=tid,workflow_type='exam_practice',handler_version=1,
            owner_user_id=owner,scope_type='exam_generation',scope_id=paper_id,
            command={**command,'paper_id':paper_id,'execution_timeout_seconds':120},idempotency_key=tid,
            status='pending',attempt_count=0,max_attempts=3,available_at=now,cancel_requested=False,
            created_at=datetime.now(timezone.utc).isoformat(),updated_at=now))
        return tid

    def paper(self,owner,paper_id):
        with self.locked(owner,paper_id) as (_,paper,__,___):return paper

    def runs(self,owner,paper_id):
        with self.locked(owner,paper_id) as (db,_,__,___):
            return [self.summary(r.payload) for r in reversed(self.rows(db,RUN,owner,paper_id))]

    def summaries(self,owner,paper_ids):
        result={}
        with database_session(engine=self.engine) as db:
            rows=db.scalars(select(AppStateRecord).where(AppStateRecord.namespace==RUN,
                AppStateRecord.owner_user_id==owner,AppStateRecord.payload['paper_id'].as_string().in_(paper_ids)).order_by(AppStateRecord.created_at))
            for row in rows:result[row.payload['paper_id']]=self.summary(row.payload)
        return result

    @staticmethod
    def summary(run):
        latest=[v[-1] for v in run['answers'].values() if v]
        return {**{k:run[k] for k in ['id','paper_id','version','status','created_at','finished_at']},
            'submitted':len(latest),'total':run['total'],'correct':sum(a['correct'] is True and a['evaluator']=='deterministic' for a in latest),
            'objective':sum(a['evaluator']=='deterministic' for a in latest),'pending':sum(a['status']=='pending_evaluation' for a in latest)}

    def start(self,owner,paper_id,request):
        body=request.model_dump(mode='json');key='examrun_'+digest([owner,paper_id,body['request_id']])[:32]
        with self.locked(owner,paper_id) as (db,paper,questions,_):
            old=db.get(AppStateRecord,(RUN,key))
            if old:
                if old.payload['start_fingerprint']!=digest(body):raise HTTPException(409,'请求编号已用于其他操作')
                return deepcopy(old.payload)
            active=next((r for r in reversed(self.rows(db,RUN,owner,paper_id)) if r.payload['status']=='active'),None)
            if active:
                if request.new:raise HTTPException(409,'请先完成当前练习，再开始新一轮')
                return self.view(db,deepcopy(active.payload))
            run={'id':key,'paper_id':paper_id,'version':paper['version'],'status':'active','created_at':time.time(),
                 'finished_at':None,'total':len(questions),'drafts':{},'answers':{},'receipts':{},'start_fingerprint':digest(body)}
            self.put(db,RUN,owner,key,run);return run

    def view(self,db,run):
        # A lost/expired worker must never leave a permanent "evaluating" display.
        for attempts in run['answers'].values():
            for a in attempts:
                if a['status']=='pending_evaluation':
                    task=db.get(DurableTaskModel,a['task_id'])
                    if not task or task.status in {'failed','canceled'}:
                        a.update(status='evaluation_failed',feedback='答案已保存，评价暂不可用，可重试。')
        return run

    def get_run(self,owner,paper_id,run_id):
        with self.locked(owner,paper_id) as (db,_,__,___):
            row=self.record(db,RUN,owner,run_id,paper_id)
            return self.view(db,deepcopy(row.payload))

    def mutable_run(self,db,owner,paper,run_id):
        row=self.record(db,RUN,owner,run_id,paper['generation_id']);run=deepcopy(row.payload)
        if run['version']!=paper['version']:raise HTTPException(409,'试卷版本已变化')
        if run['status']!='active':raise HTTPException(409,'本轮已结束，可开始新一轮练习')
        return row,run

    def draft(self,owner,paper_id,run_id,qid,request):
        with self.locked(owner,paper_id) as (db,paper,questions,_):
            row,run=self.mutable_run(db,owner,paper,run_id)
            if qid not in questions:raise HTTPException(404,'题目不存在')
            answer=request.answer.model_dump();validate_answer(questions[qid],answer,allow_empty=True)
            previous=run['drafts'].get(qid,{'revision':0})
            if previous['revision']!=request.expected_revision:
                if previous.get('answer')==answer:return previous
                raise HTTPException(409,'另一处已更新此题草稿，请选择保留本地或使用已保存的版本')
            value={'answer':answer,'revision':previous['revision']+1,'updated_at':time.time()}
            run['drafts'][qid]=value;row.payload=run;return value

    def add_answer(self,db,owner,run,q,answer,request_id):
        fingerprint=digest([q['question_id'],answer]);old=run['receipts'].get(request_id)
        if old:
            if old['fingerprint']!=fingerprint:raise HTTPException(409,'提交编号已用于其他答案')
            return next(a for a in run['answers'][q['question_id']] if a['id']==old['id'])
        validate_answer(q,answer)
        correct=objective(q,answer);aid='examanswer_'+uuid4().hex
        attempt={'id':aid,'question_id':q['question_id'],'answer':answer,'created_at':time.time(),
            'status':'graded' if correct is not None else 'pending_evaluation','correct':correct,
            'evaluator':'deterministic' if correct is not None else 'model','feedback':q['explanation'] if correct is not None else '',
            'reference_answer':q['correct_answer'] if correct is not None else ''}
        if correct is None:
            attempt['task_id']=self.queue(db,owner,run['paper_id'],{'operation':'evaluate','run_id':run['id'],'question_id':q['question_id'],'attempt_id':aid})
        run['answers'].setdefault(q['question_id'],[]).append(attempt)
        run['receipts'][request_id]={'fingerprint':fingerprint,'id':aid}
        # Keep a revision tombstone, so a late autosave cannot resurrect the submitted draft.
        prior=run['drafts'].get(q['question_id'],{'revision':0})
        run['drafts'][q['question_id']]={'answer':answer,'revision':prior['revision']+1,'updated_at':time.time(),'submitted':True}
        return attempt

    def submit(self,owner,paper_id,run_id,qid,request):
        with self.locked(owner,paper_id) as (db,paper,questions,_):
            row=self.record(db,RUN,owner,run_id,paper_id);run=deepcopy(row.payload)
            if qid not in questions:raise HTTPException(404,'题目不存在')
            rid=str(request.request_id)
            if rid not in run['receipts']:self.mutable_run(db,owner,paper,run_id)
            result=self.add_answer(db,owner,run,questions[qid],request.answer.model_dump(),rid)
            row.payload=run;return result

    def finish(self,owner,paper_id,run_id,request):
        with self.locked(owner,paper_id) as (db,paper,questions,_):
            row=self.record(db,RUN,owner,run_id,paper_id);run=deepcopy(row.payload)
            fingerprint=digest(request.model_dump(mode='json'))
            if run['status']=='finished':
                if run.get('finish_fingerprint')!=fingerprint:raise HTTPException(409,'本轮已经结束，请刷新查看记录')
                return self.view(db,run)
            self.mutable_run(db,owner,paper,run_id)
            for qid,answer in request.answers.items():
                if qid not in questions:raise HTTPException(404,'题目不存在')
                self.add_answer(db,owner,run,questions[qid],answer.model_dump(),str(request.request_id)+':'+qid)
            run.update(status='finished',finished_at=time.time(),finish_fingerprint=fingerprint);row.payload=run
            return run

    def retry_evaluation(self,owner,paper_id,run_id,qid,aid):
        with self.locked(owner,paper_id) as (db,_,questions,__):
            row=self.record(db,RUN,owner,run_id,paper_id);run=self.view(db,deepcopy(row.payload))
            attempt=next((a for a in run['answers'].get(qid,[]) if a['id']==aid),None)
            if not attempt:raise HTTPException(404,'作答不存在')
            if attempt['status']=='evaluation_failed':
                attempt.update(status='pending_evaluation',feedback='',task_id=self.queue(db,owner,paper_id,
                    {'operation':'evaluate','run_id':run_id,'question_id':qid,'attempt_id':aid}))
                row.payload=run
            return attempt

    def turns(self,owner,paper_id,before=None,limit=30):
        with self.locked(owner,paper_id) as (db,_,__,___):
            values=[deepcopy(r.payload) for r in self.rows(db,TURN,owner,paper_id)]
            if before:values=[v for v in values if v['created_at']<before]
            values=values[-limit:]
            for value in values:
                if value['status']=='pending':
                    task=db.get(DurableTaskModel,value['task_id'])
                    if not task or task.status in {'failed','canceled'}:value.update(status='failed',error='回答暂未完成，请重试')
            return [public_turn(v) for v in values]

    def ask(self,owner,paper_id,request):
        body=request.model_dump(mode='json');tid='examchat_'+digest([owner,paper_id,body['request_id']])[:32]
        with self.locked(owner,paper_id) as (db,paper,questions,record):
            old=db.get(AppStateRecord,(TURN,tid))
            if old:
                if old.payload['fingerprint']!=digest(body):raise HTTPException(409,'请求编号已用于其他问题')
                return public_turn(deepcopy(old.payload))
            run=self.record(db,RUN,owner,request.run_id,paper_id).payload
            if run['version']!=paper['version']:raise HTTPException(409,'试卷版本已变化')
            if request.attempt_id and request.draft:raise HTTPException(422,'请选择草稿或已提交答案')
            q=questions.get(request.question_id) if request.question_id else None
            if request.question_id and not q:raise HTTPException(404,'题目不存在')
            practice=None
            if request.attempt_id:
                practice=next((a for a in run['answers'].get(request.question_id,[]) if a['id']==request.attempt_id),None)
                if not practice:raise HTTPException(404,'作答不属于当前题目和轮次')
                practice={'kind':'submitted',**deepcopy(practice)}
            elif request.draft:
                if not q:raise HTTPException(422,'引用草稿需要选择题目')
                value=request.draft.model_dump();validate_answer(q,value,allow_empty=True)
                practice={'kind':'unsubmitted_draft','answer':value}
            context={'paper_title':paper['title'],'question':q,'practice':practice,'run_id':run['id'],'run_status':run['status'],
                'outline':[{'id':i,'number':v['number'],'type':v['question_type'],'stem':v['question'][:160]} for i,v in questions.items()]}
            value={'id':tid,'paper_id':paper_id,'version':paper['version'],'run_id':run['id'],'question_id':request.question_id,
                'question_number':q['number'] if q else None,'question':request.question.strip(),'answer':'','status':'pending',
                'created_at':time.time(),'context':context,'fingerprint':digest(body),'citations':[],'error':''}
            value['task_id']=self.queue(db,owner,paper_id,{'operation':'chat','turn_id':tid})
            self.put(db,TURN,owner,tid,value);return public_turn(value)

    def control(self,owner,paper_id,tid,operation):
        with self.locked(owner,paper_id) as (db,_,__,___):
            row=self.record(db,TURN,owner,tid,paper_id);value=deepcopy(row.payload)
            task=db.get(DurableTaskModel,value['task_id'])
            if operation=='cancel' and value['status']=='pending':
                value.update(status='canceled',error='已停止回答')
                if task:task.cancel_requested=True
            elif operation=='retry' and (value['status'] in {'failed','canceled'} or task is None or task.status in {'failed','canceled'}):
                value.update(status='pending',error='',task_id=self.queue(db,owner,paper_id,{'operation':'chat','turn_id':tid}))
            row.payload=value;return public_turn(value)

    def delete(self,owner,paper_id):
        with self.locked(owner,paper_id,ready=False) as (db,_,__,___):
            for ns in [RUN,TURN,PAPER]:
                for row in self.rows(db,ns,owner,paper_id):db.delete(row)
            for task in db.scalars(select(DurableTaskModel).where(DurableTaskModel.owner_user_id==owner,DurableTaskModel.scope_id==paper_id)):
                task.cancel_requested=True
            for ns in [NAMESPACE,NAMESPACE+'_cursor',NAMESPACE+'_events']:
                removal=delete(AppStateRecord).where(AppStateRecord.owner_user_id==owner,AppStateRecord.namespace==ns)
                removal=removal.where(AppStateRecord.record_key.startswith(paper_id+':',autoescape=True) if ns.endswith('_events') else AppStateRecord.record_key==paper_id)
                db.execute(removal)
