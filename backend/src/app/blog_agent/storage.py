from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .models import BlogTaskState


def _tasks_dir() -> Path:
    # 统一放在现有 storage 目录下，和其它缓存/任务保持一致
    return Path(__file__).resolve().parents[2] / "storage" / "blog_tasks"


def ensure_tasks_dir() -> Path:
    d = _tasks_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _task_file(thread_id: str) -> Path:
    return ensure_tasks_dir() / f"{thread_id}.json"


def now_iso() -> str:
    return datetime.now().isoformat()


def create_task_state(
    thread_id: str,
    course_id: str,
    topic: str,
    generation_config: Optional[Dict[str, Any]] = None,
) -> BlogTaskState:
    state = BlogTaskState(
        thread_id=thread_id,
        course_id=course_id,
        topic=topic,
        generation_config=dict(generation_config or {}),
        created_at=now_iso(),
        updated_at=now_iso(),
        status="planning",
    )
    save_task_state(state)
    return state


def load_task_state(thread_id: str) -> Optional[BlogTaskState]:
    if _uses_postgres():
        data = _repository().get("blog_tasks", thread_id)
        return BlogTaskState(**data) if data is not None else None
    path = _task_file(thread_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return BlogTaskState(**data)


def save_task_state(state: BlogTaskState) -> None:
    state.updated_at = now_iso()
    if _uses_postgres():
        _repository().put("blog_tasks", state.thread_id, state.model_dump())
        return
    path = _task_file(state.thread_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.model_dump(), f, ensure_ascii=False, indent=2)


def patch_task_state(thread_id: str, patch: Dict[str, Any]) -> BlogTaskState:
    state = load_task_state(thread_id)
    if state is None:
        raise KeyError(thread_id)

    data = state.model_dump()
    data.update(patch)
    new_state = BlogTaskState(**data)
    save_task_state(new_state)
    return new_state


def _uses_postgres() -> bool:
    import os
    return str(os.getenv("APP_STATE_PERSISTENCE_MODE", "json")).strip().lower() == "postgres"


def _repository():
    from app.persistence.dependencies import get_postgres_app_state_repository
    return get_postgres_app_state_repository()

