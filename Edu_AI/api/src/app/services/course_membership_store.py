"""Atomic persistence for course membership records."""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, cast


CourseRole = Literal["owner", "editor", "viewer"]
COURSE_ROLES = frozenset({"owner", "editor", "viewer"})


@dataclass(frozen=True)
class CourseMembership:
    course_id: str
    user_id: str
    role: CourseRole
    joined_at: str
    added_by: str


class CourseMembershipStore:
    """Store memberships in a versioned JSON file with atomic replacement."""

    SCHEMA_VERSION = 1

    def __init__(self, path: Path | str):
        self._path = Path(path)
        self._lock = threading.RLock()

    def get(self, course_id: str, user_id: str) -> CourseMembership | None:
        key = (self._normalize_id(course_id, "course_id"), self._normalize_id(user_id, "user_id"))
        with self._lock:
            return next(
                (
                    item
                    for item in self._read_unlocked()
                    if (item.course_id, item.user_id) == key
                ),
                None,
            )

    def upsert(
        self,
        course_id: str,
        user_id: str,
        role: CourseRole,
        *,
        added_by: str,
    ) -> CourseMembership:
        normalized_course_id = self._normalize_id(course_id, "course_id")
        normalized_user_id = self._normalize_id(user_id, "user_id")
        normalized_added_by = self._normalize_id(added_by, "added_by")
        if role not in COURSE_ROLES:
            raise ValueError(f"unsupported course role: {role}")

        with self._lock:
            items = self._read_unlocked()
            previous = next(
                (
                    item
                    for item in items
                    if item.course_id == normalized_course_id
                    and item.user_id == normalized_user_id
                ),
                None,
            )
            membership = CourseMembership(
                course_id=normalized_course_id,
                user_id=normalized_user_id,
                role=cast(CourseRole, role),
                joined_at=(
                    previous.joined_at
                    if previous is not None
                    else datetime.now(timezone.utc).isoformat()
                ),
                added_by=normalized_added_by,
            )
            updated = [
                item
                for item in items
                if not (
                    item.course_id == normalized_course_id
                    and item.user_id == normalized_user_id
                )
            ]
            updated.append(membership)
            self._write_unlocked(updated)
            return membership

    def list_for_user(self, user_id: str) -> list[CourseMembership]:
        normalized_user_id = self._normalize_id(user_id, "user_id")
        with self._lock:
            return sorted(
                (
                    item
                    for item in self._read_unlocked()
                    if item.user_id == normalized_user_id
                ),
                key=lambda item: item.course_id,
            )

    def list_for_course(self, course_id: str) -> list[CourseMembership]:
        normalized_course_id = self._normalize_id(course_id, "course_id")
        with self._lock:
            return sorted(
                (
                    item
                    for item in self._read_unlocked()
                    if item.course_id == normalized_course_id
                ),
                key=lambda item: item.user_id,
            )

    def delete(self, course_id: str, user_id: str) -> bool:
        normalized_course_id = self._normalize_id(course_id, "course_id")
        normalized_user_id = self._normalize_id(user_id, "user_id")
        with self._lock:
            items = self._read_unlocked()
            retained = [
                item
                for item in items
                if not (
                    item.course_id == normalized_course_id
                    and item.user_id == normalized_user_id
                )
            ]
            if len(retained) == len(items):
                return False
            self._write_unlocked(retained)
            return True

    def _read_unlocked(self) -> list[CourseMembership]:
        if not self._path.exists():
            return []
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != self.SCHEMA_VERSION:
            raise ValueError("unsupported course membership schema")
        records = payload.get("memberships")
        if not isinstance(records, list):
            raise ValueError("course memberships must be a list")
        result: list[CourseMembership] = []
        for record in records:
            role = str(record.get("role") or "")
            if role not in COURSE_ROLES:
                raise ValueError(f"unsupported course role: {role}")
            result.append(
                CourseMembership(
                    course_id=self._normalize_id(record.get("course_id"), "course_id"),
                    user_id=self._normalize_id(record.get("user_id"), "user_id"),
                    role=cast(CourseRole, role),
                    joined_at=self._normalize_id(record.get("joined_at"), "joined_at"),
                    added_by=self._normalize_id(record.get("added_by"), "added_by"),
                )
            )
        return result

    def _write_unlocked(self, items: list[CourseMembership]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(items, key=lambda item: (item.course_id, item.user_id))
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "memberships": [asdict(item) for item in ordered],
        }
        temporary_path = self._path.with_name(
            f".{self._path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self._path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _normalize_id(value: object, field: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field} is required")
        return normalized
