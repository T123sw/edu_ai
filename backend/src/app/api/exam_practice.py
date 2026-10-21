from typing import Literal
from fastapi import APIRouter, Depends, Query
from app.auth import get_current_user
from app.exam_practice.service import PracticeService
from app.exam_practice.contracts import Start,Draft,Submit,Finish,Ask
router=APIRouter(prefix='/api/exam-generations',tags=['试卷作答'])
def service():return PracticeService()

@router.get('/{paper_id}/practice')
def paper(paper_id:str,user=Depends(get_current_user),svc=Depends(service)):
    return svc.paper(user['username'],paper_id)

@router.get('/{paper_id}/practice-runs')
def runs(paper_id:str,user=Depends(get_current_user),svc=Depends(service)):
    return {'items':svc.runs(user['username'],paper_id)}

@router.post('/{paper_id}/practice-runs')
def start(paper_id:str,payload:Start,user=Depends(get_current_user),svc=Depends(service)):
    return svc.start(user['username'],paper_id,payload)

@router.get('/{paper_id}/practice-runs/{run_id}')
def get_run(paper_id:str,run_id:str,user=Depends(get_current_user),svc=Depends(service)):
    return svc.get_run(user['username'],paper_id,run_id)

@router.put('/{paper_id}/practice-runs/{run_id}/drafts/{qid}')
def draft(paper_id:str,run_id:str,qid:str,payload:Draft,user=Depends(get_current_user),svc=Depends(service)):
    return svc.draft(user['username'],paper_id,run_id,qid,payload)

@router.post('/{paper_id}/practice-runs/{run_id}/answers/{qid}')
def submit(paper_id:str,run_id:str,qid:str,payload:Submit,user=Depends(get_current_user),svc=Depends(service)):
    return svc.submit(user['username'],paper_id,run_id,qid,payload)

@router.post('/{paper_id}/practice-runs/{run_id}/finish')
def finish(paper_id:str,run_id:str,payload:Finish,user=Depends(get_current_user),svc=Depends(service)):
    return svc.finish(user['username'],paper_id,run_id,payload)

@router.post('/{paper_id}/practice-runs/{run_id}/answers/{qid}/{aid}/evaluate')
def evaluate(paper_id:str,run_id:str,qid:str,aid:str,user=Depends(get_current_user),svc=Depends(service)):
    return svc.retry_evaluation(user['username'],paper_id,run_id,qid,aid)

@router.get('/{paper_id}/agent-turns')
def turns(paper_id:str,before:float|None=None,limit:int=Query(default=30,ge=1,le=100),user=Depends(get_current_user),svc=Depends(service)):
    return {'items':svc.turns(user['username'],paper_id,before,limit)}

@router.post('/{paper_id}/agent-turns',status_code=202)
def ask(paper_id:str,payload:Ask,user=Depends(get_current_user),svc=Depends(service)):
    return svc.ask(user['username'],paper_id,payload)

@router.post('/{paper_id}/agent-turns/{tid}/{operation}')
def control(paper_id:str,tid:str,operation:Literal['retry','cancel'],user=Depends(get_current_user),svc=Depends(service)):
    return svc.control(user['username'],paper_id,tid,operation)

@router.delete('/{paper_id}')
def remove(paper_id:str,user=Depends(get_current_user),svc=Depends(service)):
    svc.delete(user['username'],paper_id)
    return {'deleted':True}
