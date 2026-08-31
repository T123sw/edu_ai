"""Authenticated API for the global EduJob ledger."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import get_current_user
from app.chat.tasks.task_store import get_task_store
from app.services.job_store import (
    EduJob,
    JobKind,
    JobStatus,
    cancel_job,
    get_job,
    list_job_page,
    retry_job,
    update_job,
)
from app.services.job_retry_service import (
    dispatch_retry_job,
    retry_durable_job,
)

from app.api import courses as courses_api

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
optional_security = HTTPBearer(auto_error=False)
PUBLIC_JOB_EXCLUDES = {"sidecar_job_id", "provider_job_ref", "owner"}
RETRY_ACCEPTED_STATUSES = {
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.SUCCEEDED,
}


def _public_job(job: EduJob) -> dict:
    return job.model_dump(mode="json", exclude=PUBLIC_JOB_EXCLUDES)


def _owner(current_user: dict) -> str:
    owner = str((current_user or {}).get("username") or "").strip()
    if not owner:
        raise HTTPException(status_code=401, detail="未认证")
    return owner


def _owned_job(edu_job_id: str, current_user: dict) -> EduJob:
    job = get_job(edu_job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.owner_user_id != _owner(current_user):
        raise HTTPException(status_code=403, detail="无权操作该任务")
    return job


def _accepted_retry(job: EduJob) -> dict:
    if job.status not in RETRY_ACCEPTED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                job.message
                or job.error_message
                or "重试任务未能进入执行队列"
            ),
        )
    return _public_job(job)


@router.get("", summary="列出当前用户的后台任务")
def list_user_jobs(
    status_filter: Optional[List[JobStatus]] = Query(None, alias="status"),
    kind_filter: Optional[List[JobKind]] = Query(None, alias="kind"),
    course_id: Optional[str] = None,
    active_only: bool = False,
    updated_after: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    try:
        page = list_job_page(
            owner_user_id=_owner(current_user),
            statuses=status_filter,
            kinds=kind_filter,
            course_id=course_id,
            active_only=active_only,
            updated_after=updated_after.isoformat() if updated_after else None,
            limit=limit,
            cursor=cursor,
        )
        return {
            "items": [_public_job(job) for job in page.items],
            "next_cursor": page.next_cursor,
            "server_time": page.server_time,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{edu_job_id}", summary="查询后台任务")
def get_job_status(
    edu_job_id: str, current_user: dict = Depends(get_current_user)
):
    return _public_job(_owned_job(edu_job_id, current_user))


@router.post(
    "/{edu_job_id}/cancel", summary="取消后台任务"
)
def cancel_user_job(
    edu_job_id: str, current_user: dict = Depends(get_current_user)
):
    job = _owned_job(edu_job_id, current_user)
    task_store = get_task_store()
    durable = task_store.get_durable(edu_job_id)
    if durable is not None and not task_store.request_cancel(
        edu_job_id,
        owner_user_id=job.owner_user_id,
    ):
        raise HTTPException(
            status_code=409,
            detail="后台任务已结束，不能取消",
        )
    try:
        canceled = cancel_job(
            edu_job_id,
            owner_user_id=_owner(current_user),
        )
        if durable is not None:
            canceled = (
                update_job(
                    edu_job_id,
                    error_code="GENERATION_CANCELLED",
                    error_message="Generation cancellation requested",
                )
                or canceled
            )
        return _public_job(canceled)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/{edu_job_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="从失败任务创建重试任务",
)
async def retry_user_job(
    edu_job_id: str,
    current_user: dict = Depends(get_current_user),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
):
    original = _owned_job(edu_job_id, current_user)
    owner = _owner(current_user)
    retried: EduJob | None = None
    try:
        durable_retried = retry_durable_job(
            original,
            owner_user_id=owner,
            task_store=get_task_store(),
        )
        if durable_retried is not None:
            return _accepted_retry(durable_retried)
        retried = retry_job(edu_job_id, owner_user_id=owner)
        dispatched = await dispatch_retry_job(
            retried,
            auth_token=credentials.credentials if credentials else "",
            current_user=current_user,
            course_storage_manager=courses_api._svc._get_manager(),
        )
        return _accepted_retry(dispatched)
    except HTTPException:
        raise
    except ValueError as exc:
        if retried is not None:
            update_job(
                retried.edu_job_id,
                status=JobStatus.FAILED,
                step="retry_dispatch_failed",
                progress=100,
                message=str(exc),
                error_code="RETRY_DISPATCH_FAILED",
                error_message=str(exc),
            )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        if retried is not None:
            update_job(
                retried.edu_job_id,
                status=JobStatus.FAILED,
                step="retry_dispatch_failed",
                progress=100,
                message="重试任务未能提交，请稍后再试",
                error_code="RETRY_DISPATCH_FAILED",
                error_message=str(exc),
            )
        raise HTTPException(
            status_code=503,
            detail="重试任务未能提交，请稍后再试",
        ) from exc
