from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Course, CourseMembership, CourseObjective, User
from app.database.legacy_importer import LegacyCoreSnapshot


@dataclass(frozen=True)
class DomainParity:
    source_count: int
    target_count: int
    missing_in_database: tuple[str, ...]
    extra_in_database: tuple[str, ...]
    mismatched: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (
            self.missing_in_database
            or self.extra_in_database
            or self.mismatched
        )

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for field in (
            "missing_in_database",
            "extra_in_database",
            "mismatched",
        ):
            payload[field] = list(payload[field])
        return payload


@dataclass(frozen=True)
class CoreParityReport:
    domains: dict[str, DomainParity]

    @property
    def ok(self) -> bool:
        return all(domain.ok for domain in self.domains.values())

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "domains": {
                name: parity.as_dict() for name, parity in self.domains.items()
            },
        }


def _compare(
    source: dict[str, tuple[Any, ...]],
    target: dict[str, tuple[Any, ...]],
) -> DomainParity:
    source_keys = set(source)
    target_keys = set(target)
    shared_keys = source_keys & target_keys
    return DomainParity(
        source_count=len(source),
        target_count=len(target),
        missing_in_database=tuple(sorted(source_keys - target_keys)),
        extra_in_database=tuple(sorted(target_keys - source_keys)),
        mismatched=tuple(
            sorted(key for key in shared_keys if source[key] != target[key])
        ),
    )


def _datetime_key(value: datetime) -> str:
    normalized = value
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat()


def reconcile_core_snapshot(
    session: Session,
    snapshot: LegacyCoreSnapshot,
) -> CoreParityReport:
    source_users = {
        item.user_id: (item.username, item.password_hash, item.role)
        for item in snapshot.users
    }
    target_users = {
        item.user_id: (item.username, item.password_hash, item.role)
        for item in session.scalars(select(User)).all()
    }

    source_courses = {
        item.course_id: (
            item.title,
            item.description,
            item.icon,
            item.color,
            item.cover_image_ref,
            item.revision,
            item.created_by,
        )
        for item in snapshot.courses
    }
    target_courses = {
        item.course_id: (
            item.title,
            item.description,
            item.icon,
            item.color,
            item.cover_image_ref,
            item.revision,
            item.created_by,
        )
        for item in session.scalars(select(Course)).all()
    }

    source_objectives = {
        f"{item.course_id}:{item.position}": (item.objective,)
        for item in snapshot.objectives
    }
    target_objectives = {
        f"{item.course_id}:{item.position}": (item.objective,)
        for item in session.scalars(select(CourseObjective)).all()
    }

    source_memberships = {
        f"{item.course_id}/{item.user_id}": (
            item.role,
            _datetime_key(item.joined_at),
            item.added_by,
        )
        for item in snapshot.memberships
    }
    target_memberships = {
        f"{item.course_id}/{item.user_id}": (
            item.role,
            _datetime_key(item.joined_at),
            item.added_by,
        )
        for item in session.scalars(select(CourseMembership)).all()
    }

    return CoreParityReport(
        domains={
            "users": _compare(source_users, target_users),
            "courses": _compare(source_courses, target_courses),
            "objectives": _compare(source_objectives, target_objectives),
            "memberships": _compare(source_memberships, target_memberships),
        }
    )
