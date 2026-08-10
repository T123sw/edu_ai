from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class UserRepository(Protocol):
    def upsert(self, user: Mapping[str, Any]) -> None: ...

    def delete(self, user_id: str) -> bool: ...


class CourseRepository(Protocol):
    def upsert(self, course: Mapping[str, Any]) -> None: ...

    def delete(self, course_id: str) -> bool: ...


class CourseMembershipRepository(Protocol):
    def upsert(self, membership: Mapping[str, Any]) -> None: ...

    def delete(self, course_id: str, user_id: str) -> bool: ...
