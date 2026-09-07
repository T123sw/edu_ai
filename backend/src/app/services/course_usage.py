"""Per-user course visits, separate from course content modification times."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.config import Config

_lock = threading.RLock()


def _namespace(user_id: str) -> str:
    return "course_usage:" + hashlib.sha256(user_id.encode()).hexdigest()


def _directory(user_id: str) -> Path:
    return Path(Config.STORAGE_ROOT) / "course_usage" / _namespace(user_id).split(":")[1]


def _uses_postgres() -> bool:
    return os.getenv("APP_STATE_PERSISTENCE_MODE", "json").strip().lower() == "postgres"


def _repository():
    from app.persistence.dependencies import get_postgres_app_state_repository
    return get_postgres_app_state_repository()


def list_course_usage(user_id: str) -> dict[str, str]:
    if _uses_postgres():
        records = _repository().list(_namespace(user_id))
    else:
        with _lock:
            records = [json.loads(path.read_text(encoding="utf-8")) for path in _directory(user_id).glob("*.json")]
    return {item["course_id"]: item["last_used_at"] for item in records}


def record_course_usage(user_id: str, course_id: str) -> str:
    with _lock:
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {"course_id": course_id, "last_used_at": timestamp}
        if _uses_postgres():
            _repository().put(_namespace(user_id), course_id, payload, owner_user_id=user_id)
        else:
            directory = _directory(user_id)
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / (hashlib.sha256(course_id.encode()).hexdigest() + ".json")
            temporary = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
            try:
                temporary.write_text(json.dumps(payload), encoding="utf-8")
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return timestamp
