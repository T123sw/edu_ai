"""
用户画像存储模块：基于 JSON 文件的 profile 读写
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional

from core.config import Config


def _now_iso() -> str:
    return datetime.now().isoformat()


class UserProfileStorage:
    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = Path(storage_file or Config.USER_PROFILES_FILE)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if self._uses_postgres():
            for profile in self._repository().list("user_profiles"):
                user_id = str(profile.get("user_id") or "").strip()
                if user_id:
                    self._profiles[user_id] = profile
            return
        if not self.storage_file.exists():
            return
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            self._profiles = {}
            return

        profiles = raw
        if isinstance(raw, dict):
            profiles = raw.get("profiles", [])

        if not isinstance(profiles, list):
            profiles = []

        for profile in profiles:
            user_id = str(profile.get("user_id") or "").strip()
            if user_id:
                profile.setdefault("created_at", _now_iso())
                profile.setdefault("updated_at", profile["created_at"])
                self._profiles[user_id] = profile

    def _save_locked(self):
        if self._uses_postgres():
            for user_id, profile in self._profiles.items():
                self._repository().put(
                    "user_profiles", user_id, profile, owner_user_id=user_id
                )
            return
        payload = {
            "updated_at": _now_iso(),
            "profiles": list(self._profiles.values()),
        }
        with open(self.storage_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def get_profile(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            return dict(self._profiles.get(user_id, {}))

    def upsert_profile(self, user_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            now = _now_iso()
            profile = self._profiles.get(user_id)
            if not profile:
                profile = {
                    "user_id": user_id,
                    "created_at": now,
                    "updated_at": now,
                }
                self._profiles[user_id] = profile
            profile.update(patch or {})
            profile["updated_at"] = now
            self._save_locked()
            return dict(profile)

    @staticmethod
    def _uses_postgres() -> bool:
        import os
        return str(os.getenv("APP_STATE_PERSISTENCE_MODE", "json")).strip().lower() == "postgres"

    @staticmethod
    def _repository():
        from app.persistence.dependencies import get_postgres_app_state_repository
        return get_postgres_app_state_repository()


user_profile_storage = UserProfileStorage()
