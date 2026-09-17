from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from app.api.course_research import current_user
from app.course_preparation.contracts import IdempotencyConflict, PreparationNotFound
from app.course_preparation.lifecycle_repository import BudgetExceeded, RevisionConflict
from app.course_preparation.schemas import PreparationRequest

router = APIRouter(prefix='/api/course-preparations', tags=['course-preparation'])


def service(request: Request):
    value = getattr(request.app.state, 'preparation_service', None)
    if value is None:
        raise HTTPException(503, '完整课程准备服务尚未启用')
    return value


def owner(user=Depends(current_user)):
    # Existing authentication returns username; resolve the immutable database identity.
    from app.course_preparation.dependencies import owner_id
    return execute(lambda: owner_id(user['username']))


def execute(action):
    try:
        return action()
    except PreparationNotFound as exc:
        raise HTTPException(404, '任务不存在或不可访问') from exc
    except PermissionError as exc:
        raise HTTPException(403, '当前资料或任务权限不可用') from exc
    except (IdempotencyConflict, RevisionConflict) as exc:
        raise HTTPException(409, '请求标识或状态版本冲突') from exc
    except BudgetExceeded as exc:
        raise HTTPException(409, '任务预算或总时限已耗尽') from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


class CancelRequest(BaseModel):
    expected_revision: int | None = Field(default=None, ge=1)


@router.post('', status_code=202)
def submit(payload: PreparationRequest, actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: svc.submit(actor, payload))


@router.get('/{preparation_id}')
def get(preparation_id: str, actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: svc.get(actor, preparation_id))


@router.post('/{preparation_id}/cancel')
def cancel(preparation_id: str, payload: CancelRequest, actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: svc.cancel(actor, preparation_id, payload.expected_revision))


@router.post('/{preparation_id}/retry', status_code=202)
def retry(preparation_id: str, actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: svc.retry(actor, preparation_id))


@router.get('/{preparation_id}/events')
def events(preparation_id: str, after: int = Query(0, ge=0), actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: {'events': [e.model_dump(mode='json') for e in svc.events(actor, preparation_id, after)]})
