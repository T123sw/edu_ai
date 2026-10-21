from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
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
        raise HTTPException(409, '任务状态已经更新，请刷新页面后再试。') from exc
    except BudgetExceeded as exc:
        from app.course_preparation.failure_explanation import explain
        _, reason, action = explain(str(exc))
        raise HTTPException(409, reason + action) from exc
    except ValueError as exc:
        message = {'ONLY_TERMINAL_FAILURE_CAN_RETRY': '这条任务当前不能重试。请刷新页面查看最新进度，只有失败或取消的任务才能重新执行。'}.get(
            str(exc), '本次操作未能完成，请刷新页面后再试；如果仍然失败，请联系维护人员查看这条任务。')
        raise HTTPException(422, message) from exc


class CancelRequest(BaseModel):
    expected_revision: int | None = Field(default=None, ge=1)
    expected_attempt_no: int | None = Field(default=None, ge=1)


class RetryRequest(BaseModel):
    node_id: str | None = Field(default=None, min_length=1, max_length=200)


@router.post('', status_code=202)
def submit(payload: PreparationRequest, actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: svc.submit(actor, payload))


@router.get('')
def list_preparations(actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: {'preparations': svc.list(actor)})


@router.get('/notifications')
def notifications(user=Depends(current_user), svc=Depends(service)):
    from app.course_preparation.notifications import NotificationService
    return execute(lambda: {'items': NotificationService(svc.repository.engine).list(user['username'])})


@router.post('/notifications/{event_id}/read')
def mark_notification(event_id: str, user=Depends(current_user), svc=Depends(service)):
    from app.course_preparation.notifications import NotificationService
    execute(lambda: NotificationService(svc.repository.engine).mark_read(user['username'], event_id))
    return {'saved': True}


@router.post('/uploads', status_code=201)
async def upload(file: UploadFile = File(...), actor=Depends(owner), svc=Depends(service)):
    from pathlib import Path
    from app.services.personal_knowledge_service import PersonalKnowledgeService
    from app.course_preparation.adapters.documents import PersonalDocumentReader, SUPPORTED_DOCUMENT_SUFFIXES
    from app.course_preparation.adapters.document_store import DocumentStore
    if Path(file.filename or '').suffix.lower() not in SUPPORTED_DOCUMENT_SUFFIXES:
        raise HTTPException(422, '支持 PDF、Word、PPT、Excel、图片（PNG/JPG/JPEG/JP2/WebP/GIF/BMP）、HTML、Markdown 和 TXT 文件')
    data = await file.read(30 * 1024 * 1024 + 1)
    await file.close()
    if not data or len(data) > 30 * 1024 * 1024:
        raise HTTPException(422, '文件不能为空，且不能超过 30 MB')
    def create():
        personal = PersonalKnowledgeService()
        from app.course_preparation.adapters.memory import PreparationMemory
        username = PreparationMemory(svc.repository).subject(actor)
        record = personal.create_document(owner_user_id=username, filename=Path(file.filename).name, file_data=data)
        return DocumentStore(svc.repository.engine, PersonalDocumentReader(personal)).register(actor, record['id'])
    return execute(create)


@router.get('/{preparation_id}')
def get(preparation_id: str, actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: svc.get(actor, preparation_id))


@router.post('/{preparation_id}/cancel')
def cancel(preparation_id: str, payload: CancelRequest, actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: svc.cancel(actor, preparation_id, payload.expected_revision,
        **({'expected_attempt_no': payload.expected_attempt_no} if payload.expected_attempt_no is not None else {})))


@router.post('/{preparation_id}/retry', status_code=202)
def retry(preparation_id: str, payload: RetryRequest | None = None, actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: svc.retry(actor, preparation_id, **({'node_id': payload.node_id} if payload and payload.node_id else {})))


@router.get('/{preparation_id}/events')
def events(preparation_id: str, after: int = Query(0, ge=0), actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: {'events': [e.model_dump(mode='json') for e in svc.events(actor, preparation_id, after)]})


@router.get('/{preparation_id}/intermediates')
def intermediates(preparation_id: str, actor=Depends(owner), svc=Depends(service)):
    return execute(lambda: svc.intermediates(actor, preparation_id))
