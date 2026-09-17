from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.chat.memory.dependencies import get_agent_memory_service


router = APIRouter(prefix="/api/agent-memory", tags=["agent-memory"])


class ProfileFactUpdateRequest(BaseModel):
    value: str = Field(min_length=1, max_length=2_000)
    course_id: str | None = None


def _subject(current_user: dict) -> str:
    return str(
        current_user.get("username") or current_user.get("user_id") or ""
    ).strip()


def _service():
    service = get_agent_memory_service()
    if not getattr(service, "available", True):
        raise HTTPException(status_code=503, detail=service.unavailable_reason)
    return service


@router.get("/profile")
def get_my_memory_profile(
    course_id: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    service = _service()
    return {
        "profile_facts": [
            item.model_dump(mode="json")
            for item in service.repository.list_profile_facts(
                subject_user_id=_subject(current_user), course_id=course_id
            )
        ]
    }


@router.get("/items")
def search_my_memories(
    q: str = "",
    course_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    service = _service()
    return {
        "items": [
            item.model_dump(mode="json")
            for item in service.repository.search(
                subject_user_id=_subject(current_user),
                course_id=course_id,
                query=q,
                limit=limit,
            )
        ]
    }


@router.put("/profile/{profile_axis}")
def update_my_profile_fact(
    profile_axis: str,
    payload: ProfileFactUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    service = _service()
    memory = service.confirm_profile_fact(
        actor={"user_id": _subject(current_user), "role": current_user.get("role")},
        profile_axis=profile_axis,
        value=payload.value,
        course_id=payload.course_id,
    )
    return {"memory": memory.model_dump(mode="json")}


@router.delete("/items/{memory_id}")
def invalidate_my_memory(
    memory_id: str,
    reason: str = Query(default="user_requested", min_length=3, max_length=200),
    expected_revision: str | None = Query(default=None, min_length=64, max_length=64),
    current_user: dict = Depends(get_current_user),
):
    service = _service()
    from app.chat.memory.lifecycle import MemoryChanged
    try:
        invalidated = service.repository.invalidate(
            memory_id=memory_id, subject_user_id=_subject(current_user), reason=reason,
            **({'expected_revision': expected_revision} if expected_revision else {}))
    except MemoryChanged as exc:
        raise HTTPException(409, '偏好已变化，请刷新后重试') from exc
    if not invalidated:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"memory_id": memory_id, "status": "invalidated"}


class PreferenceEdit(BaseModel):
    value: str = Field(min_length=1, max_length=2000)
    expected_revision: str = Field(min_length=64, max_length=64)


@router.get('/preferences')
def effective_preferences(course_id: str | None = None, current_user: dict = Depends(get_current_user)):
    from app.self_learning.memory_adapter import MemoryAdapter
    return MemoryAdapter(_service().repository._engine).read(_subject(current_user), course_id)


@router.put('/items/{memory_id}')
def edit_preference(memory_id: str, payload: PreferenceEdit, current_user: dict = Depends(get_current_user)):
    from app.self_learning.memory_adapter import MemoryAdapter
    from app.chat.memory.lifecycle import MemoryChanged
    try:
        memory = MemoryAdapter(_service().repository._engine).update_preference(
            _subject(current_user), memory_id, payload.value, payload.expected_revision)
        return {'memory': memory.model_dump(mode='json')}
    except MemoryChanged as exc:
        raise HTTPException(409, '偏好已变化，请刷新后重试') from exc
    except PermissionError as exc:
        raise HTTPException(404, '偏好不存在或无权访问') from exc
