from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import (
    CourseMembershipRepository,
    CourseRepository,
    UserRepository,
)
from .modes import PersistenceMode, PersistenceSettings


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShadowWriteResult:
    attempted: bool
    succeeded: bool
    error_type: str | None = None


@dataclass(frozen=True)
class ShadowFailureEvent:
    event_id: str
    occurred_at: str
    domain: str
    operation: str
    entity_key: str
    error_type: str


class JsonlShadowFailureJournal:
    def __init__(self, path: Path | str):
        self._path = Path(path)
        self._lock = threading.RLock()

    def record(
        self,
        *,
        domain: str,
        operation: str,
        entity_key: str,
        error_type: str,
    ) -> None:
        event = ShadowFailureEvent(
            event_id=uuid.uuid4().hex,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            domain=domain,
            operation=operation,
            entity_key=entity_key,
            error_type=error_type,
        )
        serialized = json.dumps(asdict(event), ensure_ascii=False, sort_keys=True)
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())


class CoreShadowPersistence:
    def __init__(
        self,
        *,
        settings: PersistenceSettings,
        user_repository: UserRepository,
        course_repository: CourseRepository,
        course_membership_repository: CourseMembershipRepository,
        failure_journal: JsonlShadowFailureJournal,
    ) -> None:
        self._settings = settings
        self._users = user_repository
        self._courses = course_repository
        self._memberships = course_membership_repository
        self._failure_journal = failure_journal

    def _execute(
        self,
        *,
        mode: PersistenceMode,
        domain: str,
        operation: str,
        entity_key: str,
        action: Callable[[], Any],
    ) -> ShadowWriteResult:
        if mode is PersistenceMode.JSON:
            return ShadowWriteResult(attempted=False, succeeded=True)
        try:
            action()
            return ShadowWriteResult(attempted=True, succeeded=True)
        except Exception as exc:
            error_type = type(exc).__name__
            try:
                self._failure_journal.record(
                    domain=domain,
                    operation=operation,
                    entity_key=entity_key,
                    error_type=error_type,
                )
            except OSError:
                log.exception(
                    "could not persist shadow failure metadata for %s/%s",
                    domain,
                    entity_key,
                )
            return ShadowWriteResult(
                attempted=True,
                succeeded=False,
                error_type=error_type,
            )

    def upsert_user(self, user: Mapping[str, Any]) -> ShadowWriteResult:
        user_id = str(user.get("user_id") or user.get("username") or "").strip()
        return self._execute(
            mode=self._settings.user,
            domain="user",
            operation="upsert",
            entity_key=user_id,
            action=lambda: self._users.upsert(user),
        )

    def delete_user(self, user_id: str) -> ShadowWriteResult:
        normalized_id = str(user_id or "").strip()
        return self._execute(
            mode=self._settings.user,
            domain="user",
            operation="delete",
            entity_key=normalized_id,
            action=lambda: self._users.delete(normalized_id),
        )

    def upsert_course(self, course: Mapping[str, Any]) -> ShadowWriteResult:
        course_id = str(course.get("course_id") or course.get("id") or "").strip()
        return self._execute(
            mode=self._settings.course,
            domain="course",
            operation="upsert",
            entity_key=course_id,
            action=lambda: self._courses.upsert(course),
        )

    def delete_course(self, course_id: str) -> ShadowWriteResult:
        normalized_id = str(course_id or "").strip()
        return self._execute(
            mode=self._settings.course,
            domain="course",
            operation="delete",
            entity_key=normalized_id,
            action=lambda: self._courses.delete(normalized_id),
        )

    def upsert_membership(
        self, membership: Mapping[str, Any]
    ) -> ShadowWriteResult:
        course_id = str(membership.get("course_id") or "").strip()
        user_id = str(membership.get("user_id") or "").strip()
        entity_key = f"{course_id}/{user_id}"
        return self._execute(
            mode=self._settings.course_membership,
            domain="course_membership",
            operation="upsert",
            entity_key=entity_key,
            action=lambda: self._memberships.upsert(membership),
        )

    def delete_membership(
        self, course_id: str, user_id: str
    ) -> ShadowWriteResult:
        normalized_course_id = str(course_id or "").strip()
        normalized_user_id = str(user_id or "").strip()
        entity_key = f"{normalized_course_id}/{normalized_user_id}"
        return self._execute(
            mode=self._settings.course_membership,
            domain="course_membership",
            operation="delete",
            entity_key=entity_key,
            action=lambda: self._memberships.delete(
                normalized_course_id, normalized_user_id
            ),
        )
