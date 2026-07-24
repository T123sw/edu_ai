"""通用异步任务轮询端点（SPEC-05 §3）。

edu_ai 的长任务（目前只有 generate_classroom）统一走 `EduJob`；前端只轮询
这一个端点，不直连 sidecar（SPEC-05 §2.2：隐藏 sidecar、权限统一收口）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.job_store import get_job
from core.auth import auth_manager

security = HTTPBearer()
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    return auth_manager.get_current_user(token)


@router.get("/{edu_job_id}", summary="轮询 edu_ai 任务状态")
def get_job_status(edu_job_id: str, current_user: dict = Depends(get_current_user)):
    job = get_job(edu_job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    owner = current_user.get("username") if current_user else None
    if job.owner and owner and job.owner != owner:
        raise HTTPException(status_code=403, detail="无权查看该任务")

    return job
