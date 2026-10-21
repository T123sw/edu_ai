"""Authenticated generation API. Raw results and model settings stay private."""
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from starlette.concurrency import run_in_threadpool
from app.auth import get_current_user
from app.chat.tasks.task_store import get_task_store
from app.services.job_store import JobKind, JobStatus, create_job, get_job, reconcile_exam_enqueue_job
from app.services.platform_task_handlers import enqueue_platform_task
from app.exam_generation.repository import GenerationRepository, GenerationNotFound, GenerationConflict, identifier
from app.exam_generation.schemas import CreateGeneration
from app.exam_generation.sources import GenerationSources
from app.exam_generation.snapshots import SnapshotCodec
from app.exam_generation.uploads import ExamUploads, MAX_UPLOAD_BYTES
from app.exam_generation.titles import paper_title

router = APIRouter(prefix='/api/exam-generations', tags=['模拟考试生成'])


def repository(): return GenerationRepository()
def source_reader(): return GenerationSources()
def snapshot_codec(): return SnapshotCodec()
def upload_store(): return ExamUploads()


@router.post('/documents', status_code=201)
async def upload_document(file: UploadFile = File(...), user=Depends(get_current_user),
                          uploads=Depends(upload_store)):
    """Store original bytes only; the generation task performs MinerU parsing."""
    try:
        filename = file.filename or ''
        uploads.validate_filename(filename)
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, '资料不能超过 30 MB')
        return await run_in_threadpool(uploads.create, user['username'], filename, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    finally:
        await file.close()


def public_status(row, job):
    return {'generation_id': row['id'], 'job_id': job.edu_job_id if job else row['id'],
            'title': paper_title(row['request'], row.get('sources')),
            'status': job.status.value if job else 'pending', 'progress': job.progress if job else 0,
            'message': job.message if job else '正在排队', 'exam_ready': False, 'error_code': job.error_code if job else None}


@router.post('', status_code=202)
def create(payload: CreateGeneration, user=Depends(get_current_user), repo=Depends(repository),
           sources=Depends(source_reader), codec=Depends(snapshot_codec), tasks=Depends(get_task_store)):
    owner = user['username']
    request = payload.model_dump(mode='json')
    gid = identifier(owner, request['request_id'])
    try:
        try:
            row = repo.get(owner, gid, include_events=False)
            fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
            if row['fingerprint'] != fingerprint:
                raise GenerationConflict('此请求编号已用于其他生成要求')
        except GenerationNotFound:
            refs = sources.freeze(owner, request['sources'])
            row = repo.create(owner, request, sources=refs, encrypted_snapshot=codec.capture(owner))
        with repo.lock(owner, gid):
            job = get_job(gid)
            if job is None:
                job = create_job(edu_job_id=gid, kind=JobKind.GENERATE_EXAM, owner_user_id=owner,
                    scope_type='exam_generation', scope_id=gid,
                    input_summary={'source': 'exam-generation', 'title': '模拟试卷生成', 'generation_id': gid})
            durable = tasks.get_durable(gid)
            if job.status == JobStatus.FAILED and job.error_code == 'TASK_ENQUEUE_FAILED' and (durable is None or durable.status in {'pending', 'leased'}):
                job = reconcile_exam_enqueue_job(gid, owner_user_id=owner, running=durable is not None and durable.status == 'leased')
            if durable is None and job.status == JobStatus.QUEUED:
                job = enqueue_platform_task(job=job, workflow_type='exam_generate',
                    command={'generation_id': gid, 'deadline_seconds': 1800, 'execution_timeout_seconds': 1800}, task_store=tasks)
        return public_status(row, job)
    except GenerationConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except PermissionError:
        raise HTTPException(404, '资料不存在或无权访问') from None
    except ValueError:
        raise HTTPException(422, '请检查资料格式与模型配置') from None


@router.get('/{generation_id}')
def status(generation_id: str, user=Depends(get_current_user), repo=Depends(repository)):
    try:
        row = repo.get(user['username'], generation_id, include_events=False)
    except GenerationNotFound:
        raise HTTPException(404, '生成记录不存在或无权访问') from None
    job = get_job(row.get('job_id', generation_id))
    if job and job.owner_user_id != user['username']:
        raise HTTPException(404, '生成记录不存在或无权访问')
    return public_status(row, job)


@router.get('')
def list_generations(user=Depends(get_current_user), repo=Depends(repository)):
    from app.exam_practice.service import PracticeService
    rows=repo.list(user['username'])
    summaries=PracticeService(repo.engine).summaries(user['username'],[row['id'] for row in rows])
    return {'items': [{**public_status(row, get_job(row.get('job_id', row['id']))),
                       'requirement': row['request']['requirement'],'practice_summary':summaries.get(row['id'])}
                      for row in rows]}


def question_view(qa):
    # Answers, explanations, source templates and review traces stay private.
    return {key: qa[key] for key in ('question_id', 'question_type', 'question', 'options') if key in qa} | {
        'children': [question_view(child) for child in qa.get('children') or []]}


@router.get('/{generation_id}/paper')
def paper(generation_id: str, user=Depends(get_current_user), repo=Depends(repository)):
    from app.exam_generation.validation import complete_result
    try:
        row = repo.get(user['username'], generation_id, include_events=False)
    except GenerationNotFound:
        raise HTTPException(404, '生成记录不存在或无权访问') from None
    if not complete_result(row):
        raise HTTPException(409, '整份试卷尚未生成完成')
    summary = row['result']['metadata']['summary']
    return {'generation_id': generation_id, 'title': paper_title(row['request'], row.get('sources')), 'exam_ready': False,
            'questions': [question_view(item['qa_pair']) for item in summary['results']]}
