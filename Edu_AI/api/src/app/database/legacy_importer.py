from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .models import Course, CourseMembership, CourseObjective, User


VALID_USER_ROLES = {"admin", "teacher", "student"}
VALID_MEMBERSHIP_ROLES = {"owner", "editor", "viewer"}
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class LegacyDataValidationError(ValueError):
    pass


@dataclass(frozen=True)
class LegacyUserRecord:
    user_id: str
    username: str
    password_hash: str
    role: str
    created_at: datetime
    updated_at: datetime
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class LegacyCourseRecord:
    course_id: str
    title: str
    description: str
    icon: str
    color: str
    cover_image_ref: str | None
    revision: int
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class LegacyObjectiveRecord:
    course_id: str
    position: int
    objective: str


@dataclass(frozen=True)
class LegacyMembershipRecord:
    course_id: str
    user_id: str
    role: str
    joined_at: datetime
    added_by: str | None


@dataclass(frozen=True)
class LegacyCoreSnapshot:
    users: tuple[LegacyUserRecord, ...]
    courses: tuple[LegacyCourseRecord, ...]
    objectives: tuple[LegacyObjectiveRecord, ...]
    memberships: tuple[LegacyMembershipRecord, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def summary(self) -> dict[str, Any]:
        return {
            "users": len(self.users),
            "courses": len(self.courses),
            "objectives": len(self.objectives),
            "memberships": len(self.memberships),
            "warnings": list(self.warnings),
        }


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LegacyDataValidationError(f"{label} file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise LegacyDataValidationError(f"{label} file is not valid JSON: {path}") from exc


def _timestamp(value: Any, *, fallback: datetime = EPOCH) -> datetime:
    normalized = str(value or "").strip()
    if not normalized:
        return fallback
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LegacyDataValidationError(f"invalid timestamp: {normalized}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _required_text(value: Any, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise LegacyDataValidationError(f"missing required field {field_name}")
    return normalized


def build_legacy_core_snapshot(
    *,
    users_path: Path | str,
    courses_root: Path | str,
    memberships_path: Path | str,
) -> LegacyCoreSnapshot:
    users_payload = _load_json(Path(users_path), label="users")
    raw_users = users_payload.get("users") if isinstance(users_payload, dict) else users_payload
    if not isinstance(raw_users, list):
        raise LegacyDataValidationError("users payload must contain a users list")

    users: list[LegacyUserRecord] = []
    user_ids: set[str] = set()
    for raw in raw_users:
        if not isinstance(raw, dict):
            raise LegacyDataValidationError("every user record must be an object")
        username = _required_text(raw.get("username"), field_name="users.username")
        if username in user_ids:
            raise LegacyDataValidationError(f"duplicate user {username}")
        role = _required_text(raw.get("role"), field_name=f"users[{username}].role")
        if role not in VALID_USER_ROLES:
            raise LegacyDataValidationError(f"unsupported user role {role}")
        created_at = _timestamp(raw.get("created_at"))
        users.append(
            LegacyUserRecord(
                user_id=username,
                username=username,
                password_hash=_required_text(
                    raw.get("password_hash"),
                    field_name=f"users[{username}].password_hash",
                ),
                role=role,
                created_at=created_at,
                updated_at=_timestamp(raw.get("updated_at"), fallback=created_at),
                raw_payload=dict(raw),
            )
        )
        user_ids.add(username)

    root = Path(courses_root)
    if not root.is_dir():
        raise LegacyDataValidationError(f"courses root does not exist: {root}")
    courses: list[LegacyCourseRecord] = []
    objectives: list[LegacyObjectiveRecord] = []
    course_ids: set[str] = set()
    warnings: list[str] = []
    for course_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        info_path = course_dir / "course_info.json"
        if not info_path.is_file():
            continue
        raw = _load_json(info_path, label=f"course {course_dir.name}")
        if not isinstance(raw, dict):
            raise LegacyDataValidationError(f"course {course_dir.name} must be an object")
        course_id = _required_text(raw.get("id") or course_dir.name, field_name="courses.id")
        if course_id != course_dir.name:
            raise LegacyDataValidationError(
                f"course id {course_id} does not match directory {course_dir.name}"
            )
        if course_id in course_ids:
            raise LegacyDataValidationError(f"duplicate course {course_id}")
        metadata_path = course_dir / "metadata.json"
        metadata = (
            _load_json(metadata_path, label=f"course {course_id} metadata")
            if metadata_path.is_file()
            else {}
        )
        metadata = metadata if isinstance(metadata, dict) else {}
        created_at = _timestamp(raw.get("created_at") or metadata.get("created_at"))
        created_by = str(raw.get("created_by") or "").strip() or None
        if created_by and created_by not in user_ids:
            warnings.append(f"course {course_id} has unknown creator {created_by}; imported as null")
            created_by = None
        courses.append(
            LegacyCourseRecord(
                course_id=course_id,
                title=_required_text(raw.get("title"), field_name=f"courses[{course_id}].title"),
                description=str(raw.get("description") or ""),
                icon=str(raw.get("icon") or "menu_book"),
                color=str(raw.get("color") or "#2563eb"),
                cover_image_ref=str(raw.get("knowledgeGraph") or "").strip() or None,
                revision=int(raw.get("revision") or 0),
                created_by=created_by,
                created_at=created_at,
                updated_at=_timestamp(
                    raw.get("updated_at") or metadata.get("updated_at"),
                    fallback=created_at,
                ),
                raw_payload=dict(raw),
            )
        )
        raw_objectives = raw.get("objectives") or []
        if not isinstance(raw_objectives, list):
            raise LegacyDataValidationError(f"course {course_id} objectives must be a list")
        for position, objective in enumerate(raw_objectives):
            normalized_objective = str(objective or "").strip()
            if normalized_objective:
                objectives.append(
                    LegacyObjectiveRecord(
                        course_id=course_id,
                        position=position,
                        objective=normalized_objective,
                    )
                )
        course_ids.add(course_id)

    memberships_payload = _load_json(Path(memberships_path), label="memberships")
    raw_memberships = (
        memberships_payload.get("memberships")
        if isinstance(memberships_payload, dict)
        else memberships_payload
    )
    if not isinstance(raw_memberships, list):
        raise LegacyDataValidationError("memberships payload must contain a memberships list")
    memberships: list[LegacyMembershipRecord] = []
    membership_keys: set[tuple[str, str]] = set()
    for raw in raw_memberships:
        if not isinstance(raw, dict):
            raise LegacyDataValidationError("every membership record must be an object")
        course_id = _required_text(raw.get("course_id"), field_name="memberships.course_id")
        user_id = _required_text(raw.get("user_id"), field_name="memberships.user_id")
        if course_id not in course_ids:
            raise LegacyDataValidationError(f"membership references unknown course {course_id}")
        if user_id not in user_ids:
            raise LegacyDataValidationError(f"membership references unknown user {user_id}")
        role = _required_text(raw.get("role"), field_name="memberships.role")
        if role not in VALID_MEMBERSHIP_ROLES:
            raise LegacyDataValidationError(f"unsupported membership role {role}")
        key = (course_id, user_id)
        if key in membership_keys:
            raise LegacyDataValidationError(
                f"duplicate membership {course_id}/{user_id}"
            )
        memberships.append(
            LegacyMembershipRecord(
                course_id=course_id,
                user_id=user_id,
                role=role,
                joined_at=_timestamp(raw.get("joined_at")),
                added_by=str(raw.get("added_by") or "").strip() or None,
            )
        )
        membership_keys.add(key)

    return LegacyCoreSnapshot(
        users=tuple(users),
        courses=tuple(courses),
        objectives=tuple(objectives),
        memberships=tuple(memberships),
        warnings=tuple(warnings),
    )


def apply_legacy_core_snapshot(
    session: Session,
    snapshot: LegacyCoreSnapshot,
) -> dict[str, Any]:
    for item in snapshot.users:
        session.merge(
            User(
                user_id=item.user_id,
                username=item.username,
                password_hash=item.password_hash,
                role=item.role,
                created_at=item.created_at,
                updated_at=item.updated_at,
                raw_payload=item.raw_payload,
            )
        )
    session.flush()
    for item in snapshot.courses:
        session.merge(
            Course(
                course_id=item.course_id,
                title=item.title,
                description=item.description,
                icon=item.icon,
                color=item.color,
                cover_image_ref=item.cover_image_ref,
                revision=item.revision,
                created_by=item.created_by,
                created_at=item.created_at,
                updated_at=item.updated_at,
                raw_payload=item.raw_payload,
            )
        )
    session.flush()
    imported_course_ids = [item.course_id for item in snapshot.courses]
    if imported_course_ids:
        session.execute(
            delete(CourseObjective).where(
                CourseObjective.course_id.in_(imported_course_ids)
            )
        )
        session.add_all(
            CourseObjective(
                course_id=item.course_id,
                position=item.position,
                objective=item.objective,
            )
            for item in snapshot.objectives
        )
    for item in snapshot.memberships:
        session.merge(
            CourseMembership(
                course_id=item.course_id,
                user_id=item.user_id,
                role=item.role,
                joined_at=item.joined_at,
                added_by=item.added_by,
            )
        )
    session.flush()
    return snapshot.summary()
