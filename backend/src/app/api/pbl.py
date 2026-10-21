"""Authenticated public whitelist for personal programming exercises."""
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth import get_current_user
from app.chat.tasks.task_store import get_task_store
from app.services.job_store import JobKind, JobStatus, create_job, get_job, update_job, reconcile_pbl_enqueue_job
from app.services.platform_task_handlers import enqueue_platform_task
from app.services.runtime_config_resolver import runtime_config_resolver
from app.pbl.project_schemas import parse_artifact, ProjectCheckRequest
from app.pbl.repository import PblRepository, NotFound, WorkspaceConflict
from app.pbl.generation_policy import generation_limits
from app.pbl.schemas import CreateExercise, WorkspacePatch, RunRecord, ExerciseArtifact
from app.pbl.tutor import TutorQuestion, TutorRepository, answer_question
from starlette.concurrency import run_in_threadpool

router=APIRouter(prefix='/api/pbl',tags=['编程练习'])

def repository(): return PblRepository()

def invoke(operation):
    try: return operation()
    except NotFound: raise HTTPException(404,'练习不存在或无权访问') from None
    except WorkspaceConflict as exc: raise HTTPException(409,str(exc)) from None
    except ValueError: raise HTTPException(422,'练习数据不符合契约') from None

def public_job(row):
    job=get_job(row.current_job_id)
    return job if job and job.owner_user_id==row.owner and job.kind==JobKind.GENERATE_PBL else None

def status(row):
    job=public_job(row)
    return job.status.value if job else row.generation_state

@router.post('',status_code=202)
def create(payload: CreateExercise,user=Depends(get_current_user),repo=Depends(repository)):
    owner=user['username']
    row=invoke(lambda:repo.create_or_get(owner,payload.request_id,payload.topic))
    with repo.creation_lock(owner,row.id) as row:
        job=public_job(row)
        if not job:
            job=create_job(kind=JobKind.GENERATE_PBL,edu_job_id=row.current_job_id,owner_user_id=owner,
                scope_type='pbl',scope_id=row.id,input_summary={'topic':row.topic,'title':row.topic,'exercise_id':row.id})
        # Exercise and queue may use separate stores. Reconcile a lost enqueue acknowledgement first.
        task_store=get_task_store()
        durable=task_store.get_durable(job.edu_job_id)
        if job.status==JobStatus.FAILED and job.error_code=='TASK_ENQUEUE_FAILED' and (durable is None or durable.status in {'pending','leased'}):
            job=reconcile_pbl_enqueue_job(job.edu_job_id,owner_user_id=owner,running=durable is not None and durable.status=='leased')
        if durable is None and not row.artifact_public and job.status==JobStatus.QUEUED:
            snapshot=runtime_config_resolver.capture_snapshot(owner)
            job=update_job(job.edu_job_id,status=JobStatus.QUEUED,step='queued',progress=0,
                message='编程练习已排队',error_code=None,error_message=None) or job
            job=enqueue_platform_task(job=job,workflow_type='pbl_generate',
                command=generation_limits({'exercise_id':row.id,'topic':row.topic}),runtime_config_snapshot=snapshot,task_store=task_store)
        return {'exerciseId':row.id,'jobId':job.edu_job_id,'status':job.status.value}

@router.get('')
def listing(cursor: str | None=None,limit: int=Query(50,ge=1,le=100),user=Depends(get_current_user),repo=Depends(repository)):
    rows=repo.list_owned(user['username'],cursor=cursor,limit=limit+1)
    return {'items':[{'exerciseId':r.id,'topic':r.topic,'status':status(r),'jobId':r.current_job_id} for r in rows[:limit]],
        'nextCursor':rows[limit-1].id if len(rows)>limit else None}

@router.get('/{identifier}')
def detail(identifier: str,user=Depends(get_current_user),repo=Depends(repository)):
    row=invoke(lambda:repo.get_owned(user['username'],identifier))
    job=public_job(row)
    return {'exerciseId':row.id,'job':job.model_dump(mode='json') if job else None,
        'artifact':parse_artifact(row.artifact_public).model_dump(mode='json') if row.artifact_public else None}

@router.get('/{identifier}/workspace')
def workspace(identifier: str,user=Depends(get_current_user),repo=Depends(repository)):
    return invoke(lambda:repo.get_or_create_workspace(user['username'],identifier))

@router.put('/{identifier}/workspace')
def save_workspace(identifier: str,payload: WorkspacePatch,user=Depends(get_current_user),repo=Depends(repository)):
    return invoke(lambda:repo.save_workspace(user['username'],identifier,payload))

@router.post('/{identifier}/runs')
def append_run(identifier: str,payload: RunRecord,user=Depends(get_current_user),repo=Depends(repository)):
    return invoke(lambda:repo.append_run(user['username'],identifier,payload))

@router.get('/{identifier}/runs')
def runs(identifier: str,cursor: str | None=None,limit: int=Query(50,ge=1,le=100),user=Depends(get_current_user),repo=Depends(repository)):
    items=invoke(lambda:repo.list_runs(user['username'],identifier,cursor=cursor,limit=limit+1))
    return {'items':items[:limit],'nextCursor':items[limit-1]['runId'] if len(items)>limit else None}


@router.post('/{identifier}/check')
def check_project_step(identifier: str,payload: ProjectCheckRequest,user=Depends(get_current_user),repo=Depends(repository)):
    from app.pbl.project_validation import check_project
    from app.pbl.validation import RuntimeUnavailable
    request,checks,existing=invoke(lambda:repo.project_check_input(user['username'],identifier,payload))
    if existing: return existing
    artifact=repo._ready(repo.get_owned(user['username'],identifier))
    runtime=artifact.runtime.model_dump() if artifact.runtime else None
    try: result=check_project(request.files,checks,**({'runtime':runtime} if runtime else {}))
    except RuntimeUnavailable: raise HTTPException(503,'浏览器检查环境暂不可用，请稍后重试') from None
    return invoke(lambda:repo.save_project_check(user['username'],identifier,request,result))


@router.get('/{identifier}/tutor')
def tutor_history(identifier: str, artifactVersion: int = Query(ge=1), taskId: str = Query(min_length=1, max_length=200),
                  cursor: str | None = None, user=Depends(get_current_user), repo=Depends(repository)):
    return invoke(lambda: TutorRepository(repo).history(user['username'], identifier, artifactVersion, taskId, cursor=cursor))


@router.post('/{identifier}/tutor')
async def tutor_ask(identifier: str, payload: TutorQuestion, user=Depends(get_current_user), repo=Depends(repository)):
    tutor = TutorRepository(repo)
    owner = user['username']
    existing, context = await run_in_threadpool(invoke, lambda: tutor.prepare(owner, identifier, payload))
    if existing is not None:
        return existing
    try:
        answer = await answer_question(owner, context)
    except Exception:
        raise HTTPException(502, '编程辅导暂时不可用，请稍后重试；代码和检查记录已保留') from None
    return await run_in_threadpool(invoke, lambda: tutor.save(owner, identifier, payload, context, answer))
