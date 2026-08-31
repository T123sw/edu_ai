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
    current_user: dict = Depends(get_current_user),
):
    service = _service()
    invalidated = service.repository.invalidate(
        memory_id=memory_id,
        subject_user_id=_subject(current_user),
        reason=reason,
    )
    if not invalidated:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"memory_id": memory_id, "status": "invalidated"}
