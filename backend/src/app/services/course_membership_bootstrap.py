"""Development-time course membership backfill and creation hooks."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.course_membership_store import (
    CourseMembershipStore,
    CourseRole,
)
from core import Config


@dataclass(frozen=True)
class CourseMembershipSyncSummary:
    created: int = 0
    updated: int = 0
    unchanged: int = 0


class CourseMembershipBootstrap:
    def __init__(
        self,
        *,
        store: CourseMembershipStore,
        enabled: bool,
        users_provider: Callable[[], Iterable[Mapping[str, Any]]] | None = None,
        course_ids_provider: Callable[[], Iterable[str]] | None = None,
    ) -> None:
        self.store = store
        self.enabled = bool(enabled)
        self._users_provider = users_provider or (lambda: ())
        self._course_ids_provider = course_ids_provider or (lambda: ())

    def sync_existing(
        self,
        *,
        users: Iterable[Mapping[str, Any]] | None = None,
        course_ids: Iterable[str] | None = None,
    ) -> CourseMembershipSyncSummary:
        if not self.enabled:
            return CourseMembershipSyncSummary()
        resolved_users = list(users if users is not None else self._users_provider())
        resolved_course_ids = list(
            course_ids if course_ids is not None else self._course_ids_provider()
        )
        created = updated = unchanged = 0
        for course_id in self._normalize_course_ids(resolved_course_ids):
            for user in resolved_users:
                result = self._ensure_membership(course_id, user)
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
                else:
                    unchanged += 1
        return CourseMembershipSyncSummary(
            created=created,
            updated=updated,
            unchanged=unchanged,
        )

    def on_user_created(
        self, user: Mapping[str, Any]
    ) -> CourseMembershipSyncSummary:
        return self.sync_existing(users=[user], course_ids=self._course_ids_provider())

    def on_course_created(self, course_id: str) -> CourseMembershipSyncSummary:
        return self.sync_existing(
            users=self._users_provider(), course_ids=[course_id]
        )

    def _ensure_membership(
        self, course_id: str, user: Mapping[str, Any]
    ) -> str:
        user_id = str(user.get("username") or "").strip()
        if not user_id:
            return "unchanged"
        desired_role = self._development_role(str(user.get("role") or ""))
        current = self.store.get(course_id, user_id)
        if current is None:
            self.store.upsert(
                course_id, user_id, desired_role, added_by="development-auto-enroll"
            )
            return "created"
        if current.role == "owner" or current.role == desired_role:
            return "unchanged"
        self.store.upsert(
            course_id, user_id, desired_role, added_by="development-auto-enroll"
        )
        return "updated"

    @staticmethod
    def _development_role(system_role: str) -> CourseRole:
        return "editor" if system_role.strip().lower() in {"teacher", "admin"} else "viewer"

    @staticmethod
    def _normalize_course_ids(course_ids: Iterable[str]) -> list[str]:
        return list(
            dict.fromkeys(
                normalized
                for item in course_ids
                if (normalized := str(item or "").strip())
            )
        )


def _default_users() -> list[dict[str, Any]]:
    from core.user_storage import user_storage

    return user_storage.list_users()


def _default_course_ids() -> list[str]:
    from app.services.course_service import _get_manager

    manager = _get_manager()
    return sorted(
        str(course.get("id") or course.get("course_id") or "").strip()
        for course in manager.list_course_infos()
        if str(course.get("id") or course.get("course_id") or "").strip()
    )


def get_course_membership_bootstrap() -> CourseMembershipBootstrap:
    configured_path = Path(
        getattr(
            Config,
            "COURSE_MEMBERSHIPS_FILE",
            Path(Config.STORAGE_ROOT) / "course_memberships.json",
        )
    )
    return CourseMembershipBootstrap(
        store=CourseMembershipStore(configured_path),
        enabled=bool(getattr(Config, "DEV_AUTO_ENROLL_ALL_COURSES", True)),
        users_provider=_default_users,
        course_ids_provider=_default_course_ids,
    )
