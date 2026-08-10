from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from app.database import (
    Course,
    CourseMembership,
    CourseObjective,
    User,
    database_session,
)


def _required_text(value: object, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _timestamp(value: object, *, default: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif str(value or "").strip():
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    else:
        parsed = default or datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _iso_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class PostgresUserRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def upsert(self, user: Mapping[str, Any]) -> None:
        payload = dict(user)
        username = _required_text(payload.get("username"), "username")
        user_id = _required_text(payload.get("user_id") or username, "user_id")
        with database_session(engine=self._engine) as session:
            record = session.get(User, user_id)
            if record is None:
                record = User(
                    user_id=user_id,
                    username=username,
                    password_hash=_required_text(
                        payload.get("password_hash"), "password_hash"
                    ),
                    role=_required_text(payload.get("role"), "role"),
                )
                session.add(record)
            record.username = username
            record.password_hash = _required_text(
                payload.get("password_hash"), "password_hash"
            )
            record.role = _required_text(payload.get("role"), "role")
            record.is_disabled = bool(payload.get("is_disabled", False))
            record.created_at = _timestamp(
                payload.get("created_at"), default=record.created_at
            )
            record.updated_at = _timestamp(payload.get("updated_at"))
            record.raw_payload = payload

    def delete(self, user_id: str) -> bool:
        normalized_id = _required_text(user_id, "user_id")
        with database_session(engine=self._engine) as session:
            record = session.get(User, normalized_id)
            if record is None:
                return False
            session.delete(record)
            return True

    def get(self, user_id: str) -> dict[str, Any] | None:
        normalized_id = _required_text(user_id, "user_id")
        with database_session(engine=self._engine) as session:
            record = session.get(User, normalized_id)
            return self._payload(record) if record is not None else None

    def list(self) -> list[dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(select(User).order_by(User.username)).all()
            return [self._payload(record) for record in records]

    @staticmethod
    def _payload(record: User) -> dict[str, Any]:
        payload = dict(record.raw_payload or {})
        payload.update(
            {
                "user_id": record.user_id,
                "username": record.username,
                "password_hash": record.password_hash,
                "role": record.role,
                "is_disabled": record.is_disabled,
                "created_at": _iso_timestamp(record.created_at),
                "updated_at": _iso_timestamp(record.updated_at),
            }
        )
        return payload


class PostgresCourseRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def upsert(self, course: Mapping[str, Any]) -> None:
        payload = dict(course)
        course_id = _required_text(
            payload.get("course_id") or payload.get("id"), "course_id"
        )
        with database_session(engine=self._engine) as session:
            record = session.get(Course, course_id)
            if record is None:
                record = Course(
                    course_id=course_id,
                    title=_required_text(payload.get("title"), "title"),
                )
                session.add(record)
            record.title = _required_text(payload.get("title"), "title")
            record.description = str(payload.get("description") or "")
            record.icon = str(payload.get("icon") or "menu_book")
            record.color = str(payload.get("color") or "#2563eb")
            record.cover_image_ref = _optional_text(
                payload.get("cover_image_ref") or payload.get("coverImage")
            )
            record.revision = int(payload.get("revision") or 0)
            record.created_by = _optional_text(payload.get("created_by"))
            record.created_at = _timestamp(
                payload.get("created_at"), default=record.created_at
            )
            record.updated_at = _timestamp(payload.get("updated_at"))
            record.raw_payload = payload

            session.execute(
                delete(CourseObjective).where(
                    CourseObjective.course_id == course_id
                )
            )
            objectives = payload.get("objectives") or []
            if not isinstance(objectives, list):
                raise ValueError("objectives must be a list")
            for position, objective in enumerate(objectives):
                normalized = str(objective or "").strip()
                if normalized:
                    session.add(
                        CourseObjective(
                            course_id=course_id,
                            position=position,
                            objective=normalized,
                        )
                    )

    def delete(self, course_id: str) -> bool:
        normalized_id = _required_text(course_id, "course_id")
        with database_session(engine=self._engine) as session:
            record = session.get(Course, normalized_id)
            if record is None:
                return False
            session.delete(record)
            return True

    def get(self, course_id: str) -> dict[str, Any] | None:
        normalized_id = _required_text(course_id, "course_id")
        with database_session(engine=self._engine) as session:
            record = session.get(Course, normalized_id)
            return self._payload(record) if record is not None else None

    def list(self) -> list[dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(select(Course).order_by(Course.course_id)).all()
            return [self._payload(record) for record in records]

    @staticmethod
    def _payload(record: Course) -> dict[str, Any]:
        payload = dict(record.raw_payload or {})
        payload.update(
            {
                "id": record.course_id,
                "course_id": record.course_id,
                "title": record.title,
                "description": record.description,
                "icon": record.icon,
                "color": record.color,
                "cover_image_ref": record.cover_image_ref,
                "revision": record.revision,
                "created_by": record.created_by,
                "created_at": _iso_timestamp(record.created_at),
                "updated_at": _iso_timestamp(record.updated_at),
                "objectives": [item.objective for item in record.objectives],
            }
        )
        return payload


class PostgresCourseMembershipRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def upsert(self, membership: Mapping[str, Any]) -> None:
        payload = dict(membership)
        course_id = _required_text(payload.get("course_id"), "course_id")
        user_id = _required_text(payload.get("user_id"), "user_id")
        with database_session(engine=self._engine) as session:
            record = session.get(CourseMembership, (course_id, user_id))
            if record is None:
                record = CourseMembership(course_id=course_id, user_id=user_id)
                session.add(record)
            record.role = _required_text(payload.get("role"), "role")
            record.joined_at = _timestamp(
                payload.get("joined_at"), default=record.joined_at
            )
            record.added_by = _optional_text(payload.get("added_by"))

    def delete(self, course_id: str, user_id: str) -> bool:
        normalized_course_id = _required_text(course_id, "course_id")
        normalized_user_id = _required_text(user_id, "user_id")
        with database_session(engine=self._engine) as session:
            record = session.get(
                CourseMembership,
                (normalized_course_id, normalized_user_id),
            )
            if record is None:
                return False
            session.delete(record)
            return True

    def get(self, course_id: str, user_id: str) -> dict[str, Any] | None:
        normalized_course_id = _required_text(course_id, "course_id")
        normalized_user_id = _required_text(user_id, "user_id")
        with database_session(engine=self._engine) as session:
            record = session.get(
                CourseMembership, (normalized_course_id, normalized_user_id)
            )
            return self._payload(record) if record is not None else None

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        normalized_user_id = _required_text(user_id, "user_id")
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(CourseMembership)
                .where(CourseMembership.user_id == normalized_user_id)
                .order_by(CourseMembership.course_id)
            ).all()
            return [self._payload(record) for record in records]

    def list_for_course(self, course_id: str) -> list[dict[str, Any]]:
        normalized_course_id = _required_text(course_id, "course_id")
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(CourseMembership)
                .where(CourseMembership.course_id == normalized_course_id)
                .order_by(CourseMembership.user_id)
            ).all()
            return [self._payload(record) for record in records]

    @staticmethod
    def _payload(record: CourseMembership) -> dict[str, Any]:
        return {
            "course_id": record.course_id,
            "user_id": record.user_id,
            "role": record.role,
            "joined_at": _iso_timestamp(record.joined_at),
            "added_by": record.added_by or "system",
        }
