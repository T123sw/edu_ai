"""Atomic file-backed persistence for per-student classroom Q&A sessions."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from core.course_storage import CourseStorageManager


_PATH_LOCKS: dict[str, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


class ClassroomQaBusyError(RuntimeError):
    code = "CLASSROOM_QA_BUSY"


class ClassroomQaSessionStore:
    def __init__(
        self,
        storage: CourseStorageManager,
        *,
        clock: Callable[[], float] = time.time,
        stale_after_seconds: float = 120.0,
    ) -> None:
        self.storage = storage
        self.clock = clock
        self.stale_after_seconds = stale_after_seconds

    def session_dir(
        self,
        *,
        course_id: str,
        classroom_id: str,
        owner_user_id: str,
    ) -> Path:
        return self.storage.get_classroom_qa_dir(
            course_id,
            classroom_id,
            owner_user_id,
        )

    def load_or_empty(
        self,
        *,
        course_id: str,
        classroom_id: str,
        owner_user_id: str,
    ) -> dict[str, Any]:
        session_dir = self.session_dir(
            course_id=course_id,
            classroom_id=classroom_id,
            owner_user_id=owner_user_id,
        )
        session_path = session_dir / "session.json"
        with self._lock_for(session_path):
            stored = self._read(session_path)
            if stored is None:
                return self._empty_session(
                    course_id=course_id,
                    classroom_id=classroom_id,
                    owner_user_id=owner_user_id,
                )
            stored["turns"] = list(stored.get("turns") or [])[-100:]
            return stored

    def get_or_create(
        self,
        *,
        course_id: str,
        classroom_id: str,
        owner_user_id: str,
    ) -> dict[str, Any]:
        session_dir = self.session_dir(
            course_id=course_id,
            classroom_id=classroom_id,
            owner_user_id=owner_user_id,
        )
        session_path = session_dir / "session.json"
        with self._lock_for(session_path):
            stored = self._read(session_path)
            if stored is not None:
                stored["turns"] = list(stored.get("turns") or [])[-100:]
                return stored
            session = self._empty_session(
                course_id=course_id,
                classroom_id=classroom_id,
                owner_user_id=owner_user_id,
            )
            session_dir.mkdir(parents=True, exist_ok=True)
            self._atomic_write(session_path, session)
            return session

    @staticmethod
    def find_turn(
        session: dict[str, Any],
        client_turn_id: str,
    ) -> dict[str, Any] | None:
        normalized = str(client_turn_id)
        return next(
            (
                turn
                for turn in session.get("turns") or []
                if str(turn.get("client_turn_id")) == normalized
            ),
            None,
        )

    def begin_turn(
        self,
        *,
        session: dict[str, Any],
        client_turn_id: str,
        question: str,
        checkpoint: dict[str, Any],
    ) -> dict[str, Any]:
        session_path, claim_path = self._paths_for_session(session)
        with self._lock_for(session_path):
            current = self._read(session_path) or dict(session)
            existing = self.find_turn(current, client_turn_id)
            if existing is not None:
                self._replace_mapping(session, current)
                return existing

            self._reclaim_stale_claim(claim_path, current)
            if current.get("active_turn") is not None or claim_path.exists():
                raise ClassroomQaBusyError("A classroom Q&A turn is already processing")

            claim_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(
                    claim_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
            except FileExistsError as exc:
                raise ClassroomQaBusyError(
                    "A classroom Q&A turn is already processing"
                ) from exc

            active = {
                "client_turn_id": str(client_turn_id),
                "question": question,
                "checkpoint": dict(checkpoint),
                "started_at": self._iso_now(),
                "started_at_epoch": self.clock(),
            }
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(str(client_turn_id))
                    stream.flush()
                    os.fsync(stream.fileno())
                current["active_turn"] = active
                current.pop("last_failure", None)
                self._atomic_write(session_path, current)
            except Exception:
                claim_path.unlink(missing_ok=True)
                raise

            self._replace_mapping(session, current)
            return active

    def complete_turn(
        self,
        *,
        session: dict[str, Any],
        client_turn_id: str,
        turn: dict[str, Any],
    ) -> dict[str, Any]:
        session_path, claim_path = self._paths_for_session(session)
        with self._lock_for(session_path):
            current = self._read(session_path) or dict(session)
            active = current.get("active_turn") or {}
            if str(active.get("client_turn_id")) != str(client_turn_id):
                existing = self.find_turn(current, client_turn_id)
                if existing is not None:
                    self._replace_mapping(session, current)
                    return existing
                raise ClassroomQaBusyError("The active classroom Q&A turn changed")

            turns = list(current.get("turns") or [])
            turns.append(dict(turn))
            current["turns"] = turns[-100:]
            current["active_turn"] = None
            current.pop("last_failure", None)
            self._atomic_write(session_path, current)
            claim_path.unlink(missing_ok=True)
            self._replace_mapping(session, current)
            return dict(turn)

    def fail_turn(
        self,
        *,
        session: dict[str, Any],
        client_turn_id: str,
        error_code: str,
        retryable: bool,
    ) -> dict[str, Any]:
        session_path, claim_path = self._paths_for_session(session)
        with self._lock_for(session_path):
            current = self._read(session_path) or dict(session)
            failure = {
                "client_turn_id": str(client_turn_id),
                "error_code": error_code,
                "retryable": bool(retryable),
                "failed_at": self._iso_now(),
            }
            current["active_turn"] = None
            current["last_failure"] = failure
            self._atomic_write(session_path, current)
            claim_path.unlink(missing_ok=True)
            self._replace_mapping(session, current)
            return failure

    def _paths_for_session(self, session: dict[str, Any]) -> tuple[Path, Path]:
        session_dir = self.session_dir(
            course_id=str(session["course_id"]),
            classroom_id=str(session["classroom_id"]),
            owner_user_id=str(session["owner_user_id"]),
        )
        return session_dir / "session.json", session_dir / "active-turn.lock"

    def _empty_session(
        self,
        *,
        course_id: str,
        classroom_id: str,
        owner_user_id: str,
    ) -> dict[str, Any]:
        digest = hashlib.sha256(
            f"{course_id}\0{classroom_id}\0{owner_user_id}".encode("utf-8")
        ).hexdigest()[:24]
        return {
            "session_id": f"cqa_{digest}",
            "course_id": course_id,
            "classroom_id": classroom_id,
            "owner_user_id": owner_user_id,
            "status": "ready",
            "turns": [],
            "active_turn": None,
        }

    def _reclaim_stale_claim(
        self,
        claim_path: Path,
        session: dict[str, Any],
    ) -> None:
        active = session.get("active_turn") or {}
        started_at = float(active.get("started_at_epoch") or 0)
        claim_age = None
        if claim_path.exists():
            claim_age = self.clock() - claim_path.stat().st_mtime
        stale = (
            bool(active)
            and started_at > 0
            and self.clock() - started_at > self.stale_after_seconds
        ) or (claim_age is not None and claim_age > self.stale_after_seconds)
        if stale:
            claim_path.unlink(missing_ok=True)
            session["active_turn"] = None

    @staticmethod
    def _replace_mapping(target: dict[str, Any], source: dict[str, Any]) -> None:
        target.clear()
        target.update(source)

    @staticmethod
    def _read(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _lock_for(path: Path) -> threading.RLock:
        key = str(path.resolve())
        with _PATH_LOCKS_GUARD:
            return _PATH_LOCKS.setdefault(key, threading.RLock())
