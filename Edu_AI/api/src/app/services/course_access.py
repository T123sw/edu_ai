"""Course capability checks independent of HTTP and storage transport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from app.services.course_membership_store import (
    CourseMembershipStore,
    CourseRole,
)


CourseCapability = Literal[
    "read",
    "edit",
    "generate",
    "manage_resources",
    "manage_members",
    "delete_course",
]

ROLE_CAPABILITIES: dict[CourseRole, frozenset[CourseCapability]] = {
    "viewer": frozenset({"read"}),
    "editor": frozenset({"read", "edit", "generate", "manage_resources"}),
    "owner": frozenset(
        {
            "read",
            "edit",
            "generate",
            "manage_resources",
            "manage_members",
            "delete_course",
        }
    ),
}


@dataclass(frozen=True)
class CoursePrincipal:
    course_id: str
    user_id: str
    system_role: str
    course_role: CourseRole


class CourseAccessDenied(PermissionError):
    def __init__(
        self,
        *,
        course_id: str,
        user_id: str,
        capability: CourseCapability,
    ) -> None:
        super().__init__(
            f"user {user_id or '<anonymous>'} cannot {capability} course {course_id}"
        )
        self.course_id = course_id
        self.user_id = user_id
        self.capability = capability


class CourseAccessService:
    def __init__(self, store: CourseMembershipStore):
        self._store = store

    def require(
        self,
        course_id: str,
        user: Mapping[str, Any],
        capability: CourseCapability,
    ) -> CoursePrincipal:
        normalized_course_id = str(course_id or "").strip()
        user_id = str(user.get("username") or "").strip()
        membership = (
            self._store.get(normalized_course_id, user_id)
            if normalized_course_id and user_id
            else None
        )
        if (
            membership is None
            or capability not in ROLE_CAPABILITIES[membership.role]
        ):
            raise CourseAccessDenied(
                course_id=normalized_course_id,
                user_id=user_id,
                capability=capability,
            )
        return CoursePrincipal(
            course_id=normalized_course_id,
            user_id=user_id,
            system_role=str(user.get("role") or "").strip(),
            course_role=membership.role,
        )
