"""Authenticated intent → research → learning-path stage API."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.course_preparation import research_dependencies as infrastructure
from app.course_preparation.contracts import IdempotencyConflict, PreparationNotFound
from app.course_preparation.research_contracts import ResearchRequest

router = APIRouter(prefix='/api/course-preparations/research-runs', tags=['course-preparation'])
bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    # Lazy import keeps domain/API dependency tests independent of legacy app bootstrap.
    if credentials is None:
        raise HTTPException(401, '请先登录')
    from app.auth import get_current_user
    return get_current_user(credentials)


def repository():
    if not infrastructure.enabled():
        raise HTTPException(503, '课程研究流程尚未启用')
    try:
        return infrastructure.repository()
    except RuntimeError as exc:
        raise HTTPException(503, '课程研究服务尚未配置或迁移') from exc


def config_snapshot():
    return infrastructure.snapshot


def execute(action):
    try:
        return action()
    except PreparationNotFound as exc:
        raise HTTPException(404, '任务不存在或不可访问') from exc
    except IdempotencyConflict as exc:
        raise HTTPException(409, '同一 request_id 不能提交不同需求') from exc


@router.post('', status_code=202)
def create(payload: ResearchRequest, user=Depends(current_user), repo=Depends(repository), capture=Depends(config_snapshot)):
    return execute(lambda: repo.submit(user['username'], payload, config_snapshot=capture(user['username'])))


@router.get('/{run_id}')
def get(run_id: str, user=Depends(current_user), repo=Depends(repository)):
    return execute(lambda: repo.get(user['username'], run_id))


@router.post('/{run_id}/cancel')
def cancel(run_id: str, user=Depends(current_user), repo=Depends(repository)):
    return execute(lambda: repo.get(user['username'], run_id, cancel=True))
