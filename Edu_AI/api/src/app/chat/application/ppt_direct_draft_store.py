from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from core.config import Config


class PptDirectDraftStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or (Config.STORAGE_ROOT / "ppt_drafts"))
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @staticmethod
    def _owner_key(owner: str) -> str:
        normalized = str(owner or "").strip()
        if not normalized:
            raise ValueError("owner is required")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _safe_draft_id(draft_id: str) -> str:
        normalized = str(draft_id or "").strip()
        if not normalized or Path(normalized).name != normalized:
            raise ValueError("invalid draft_id")
        return normalized

    def _path(self, owner: str, draft_id: str) -> Path:
        owner_dir = self.root / self._owner_key(owner)
        owner_dir.mkdir(parents=True, exist_ok=True)
        return owner_dir / f"{self._safe_draft_id(draft_id)}.json"

    def save(self, *, owner: str, draft: dict[str, Any]) -> None:
        draft_id = self._safe_draft_id(str(draft.get("draft_id") or ""))
        payload = {**dict(draft), "owner_user_id": str(owner).strip()}
        if self._uses_postgres():
            self._repository().put(
                "ppt_drafts",
                f"{self._owner_key(owner)}:{draft_id}",
                payload,
                owner_user_id=owner,
            )
            return
        target = self._path(owner, draft_id)
        with self._lock:
            handle = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{draft_id}-",
                suffix=".tmp",
                delete=False,
            )
            temporary = Path(handle.name)
            try:
                with handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)

    def get(self, *, owner: str, draft_id: str) -> dict[str, Any]:
        if self._uses_postgres():
            payload = self._repository().get(
                "ppt_drafts",
                f"{self._owner_key(owner)}:{self._safe_draft_id(draft_id)}",
            )
            if payload is None:
                raise KeyError(draft_id)
            if str(payload.get("owner_user_id") or "") != str(owner or "").strip():
                raise PermissionError("ppt draft owner mismatch")
            return dict(payload)
        target = self._path(owner, draft_id)
        with self._lock:
            if not target.exists():
                raise KeyError(draft_id)
            payload = json.loads(target.read_text(encoding="utf-8"))
        if str(payload.get("owner_user_id") or "") != str(owner or "").strip():
            raise PermissionError("ppt draft owner mismatch")
        return dict(payload)

    @staticmethod
    def _uses_postgres() -> bool:
        return str(os.getenv("APP_STATE_PERSISTENCE_MODE", "json")).strip().lower() == "postgres"

    @staticmethod
    def _repository():
        from app.persistence.dependencies import get_postgres_app_state_repository
        return get_postgres_app_state_repository()


_default_store: PptDirectDraftStore | None = None
_default_store_lock = threading.Lock()


def get_default_ppt_direct_draft_store() -> PptDirectDraftStore:
    global _default_store
    if _default_store is None:
        with _default_store_lock:
            if _default_store is None:
                _default_store = PptDirectDraftStore()
    return _default_store

