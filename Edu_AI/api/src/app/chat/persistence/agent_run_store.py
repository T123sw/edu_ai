"""Durable, privacy-minimal snapshot store for Agent conversation workflow state."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


_DEFAULT_DB_PATH = os.getenv(
    "AGENT_RUNS_DB_PATH",
    str(Path(__file__).resolve().parents[4] / "data" / "agent_runs.db"),
)
_ALLOWED_STATE_KEYS = {
    "active_draft_outline", "pending_tasks", "current_plan", "plan_step_index",
    "plan_mode", "task_contract", "research_bundle_ref", "verification_report",
    "accumulated_images", "agent_run_status", "logical_task_id",
    "agent_memory",
}


class AgentRunStore:
    def __init__(self, db_path: str | Path = _DEFAULT_DB_PATH):
        self._path = str(db_path)
        self._lock = threading.RLock()
        self._postgres = (
            str(os.getenv("APP_STATE_PERSISTENCE_MODE", "json")).strip().lower()
            == "postgres"
        )
        if self._postgres:
            from app.persistence.dependencies import get_postgres_app_state_repository

            self._repository = get_postgres_app_state_repository()
            self._conn = None
            return
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False, timeout=5)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                conversation_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                course_id TEXT NOT NULL DEFAULT '',
                state_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def save(
        self,
        conversation_id: str,
        owner_user_id: str,
        course_id: str | None,
        state: dict[str, Any],
    ) -> None:
        conversation_id = str(conversation_id or "").strip()
        owner_user_id = str(owner_user_id or "").strip()
        if not conversation_id or not owner_user_id:
            return
        safe_state = {
            key: value for key, value in dict(state or {}).items()
            if key in _ALLOWED_STATE_KEYS
        }
        if self._postgres:
            self._repository.put(
                "agent_runs",
                conversation_id,
                {
                    "conversation_id": conversation_id,
                    "owner_user_id": owner_user_id,
                    "course_id": str(course_id or ""),
                    "state": safe_state,
                    "updated_at": time.time(),
                },
                owner_user_id=owner_user_id,
            )
            return
        payload = json.dumps(safe_state, ensure_ascii=False, separators=(",", ":"), default=str)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO agent_runs(conversation_id, owner_user_id, course_id, state_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    owner_user_id=excluded.owner_user_id,
                    course_id=excluded.course_id,
                    state_json=excluded.state_json,
                    updated_at=excluded.updated_at
                """,
                (conversation_id, owner_user_id, str(course_id or ""), payload, time.time()),
            )
            self._conn.commit()

    def load(
        self,
        conversation_id: str,
        *,
        owner_user_id: str,
        course_id: str | None = None,
    ) -> dict[str, Any]:
        conversation_id = str(conversation_id or "").strip()
        owner_user_id = str(owner_user_id or "").strip()
        if not conversation_id or not owner_user_id:
            return {}
        if self._postgres:
            payload = self._repository.get("agent_runs", conversation_id)
            if payload is None or payload.get("owner_user_id") != owner_user_id:
                return {}
            if course_id is not None and str(payload.get("course_id") or "") != str(course_id or ""):
                return {}
            state = payload.get("state") or {}
            return dict(state) if isinstance(state, dict) else {}
        with self._lock:
            if course_id is None:
                row = self._conn.execute(
                    "SELECT state_json FROM agent_runs WHERE conversation_id=? AND owner_user_id=?",
                    (conversation_id, owner_user_id),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT state_json FROM agent_runs "
                    "WHERE conversation_id=? AND owner_user_id=? AND course_id=?",
                    (conversation_id, owner_user_id, str(course_id or "")),
                ).fetchone()
        if not row:
            return {}
        try:
            state = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            return {}
        return state if isinstance(state, dict) else {}

    def close(self) -> None:
        if self._postgres:
            return
        with self._lock:
            self._conn.close()


_store: AgentRunStore | None = None
_store_lock = threading.Lock()


def get_agent_run_store() -> AgentRunStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = AgentRunStore()
    return _store
