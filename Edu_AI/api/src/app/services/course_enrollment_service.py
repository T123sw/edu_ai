"""Course self-enrollment and owner-managed membership operations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict
from typing import Any, Literal

from app.services.course_code_service import CourseCodeError, normalize_course_code
from app.services.course_membership_store import CourseMembershipStore, CourseRole


class CourseEnrollmentError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class CourseEnrollmentService:
    def __init__(
        self,
        *,
        manager,
        memberships: CourseMembershipStore,
        users_provider: Callable[[], list[Mapping[str, Any]]],
    ) -> None:
        self._manager = manager
        self._memberships = memberships
        self._users_provider = users_provider

    def course_code_exists(self, course_code: str) -> bool:
        return self.find_course(course_code) is not None

    def find_course(self, course_code: object) -> dict[str, Any] | None:
        try:
            normalized = normalize_course_code(course_code)
        except CourseCodeError:
            return None
        if self._manager._course_uses_postgres():
            return self._manager._course_repository().get_by_course_code(normalized)
        if not self._manager.courses_dir.exists():
            return None
        for path in self._manager.courses_dir.iterdir():
            if not path.is_dir():
                continue
            info = self._manager.get_course_info(path.name)
            if info and str(info.get("course_code") or "").upper() == normalized:
                return info
        return None

    def join(self, *, course_code: object, user_id: str, system_role: str) -> dict[str, Any]:
        if str(system_role or "").lower() != "student":
            raise CourseEnrollmentError("STUDENT_JOIN_ONLY", "仅学生可以使用课程码加入课程", 403)
        course = self.find_course(course_code)
        if course is None:
            raise CourseEnrollmentError("COURSE_CODE_NOT_FOUND", "课程码无效或课程不存在", 404)
        course_id = str(course.get("id") or course.get("course_id") or "").strip()
        self._memberships.upsert(course_id, user_id, "viewer", added_by=user_id)
        return course

    def list_members(self, course_id: str) -> list[dict[str, Any]]:
        users = {str(item.get("username") or item.get("user_id") or ""): item for item in self._users_provider()}
        result: list[dict[str, Any]] = []
        for membership in self._memberships.list_for_course(course_id):
            user = users.get(membership.user_id, {})
            result.append(
                {
                    **asdict(membership),
                    "username": str(user.get("username") or membership.user_id),
                    "system_role": str(user.get("role") or ""),
                }
            )
        return result

    def add_member(
        self,
        *,
        course_id: str,
        user_id: str,
        role: CourseRole,
        added_by: str,
    ) -> dict[str, Any]:
        user = self._require_user(user_id)
        self._validate_role_assignment(str(user.get("role") or ""), role)
        membership = self._memberships.upsert(course_id, user_id, role, added_by=added_by)
        return {**asdict(membership), "username": user_id, "system_role": user.get("role")}

    def update_member(
        self,
        *,
        course_id: str,
        user_id: str,
        role: CourseRole,
        added_by: str,
    ) -> dict[str, Any]:
        current = self._memberships.get(course_id, user_id)
        if current is None:
            raise CourseEnrollmentError("MEMBER_NOT_FOUND", "课程成员不存在", 404)
        if current.role == "owner" and role != "owner" and self._owner_count(course_id) <= 1:
            raise CourseEnrollmentError("LAST_OWNER_REQUIRED", "课程必须保留至少一名负责人", 409)
        return self.add_member(
            course_id=course_id,
            user_id=user_id,
            role=role,
            added_by=added_by,
        )

    def remove_member(self, *, course_id: str, user_id: str) -> None:
        current = self._memberships.get(course_id, user_id)
        if current is None:
            raise CourseEnrollmentError("MEMBER_NOT_FOUND", "课程成员不存在", 404)
        if current.role == "owner" and self._owner_count(course_id) <= 1:
            raise CourseEnrollmentError("LAST_OWNER_REQUIRED", "课程必须保留至少一名负责人", 409)
        self._memberships.delete(course_id, user_id)

    def _require_user(self, user_id: str) -> Mapping[str, Any]:
        normalized = str(user_id or "").strip()
        for user in self._users_provider():
            if str(user.get("username") or user.get("user_id") or "") == normalized:
                return user
        raise CourseEnrollmentError("USER_NOT_FOUND", "用户不存在", 404)

    @staticmethod
    def _validate_role_assignment(system_role: str, course_role: CourseRole) -> None:
        normalized = system_role.lower()
        if course_role == "viewer" and normalized != "student":
            raise CourseEnrollmentError("ROLE_MISMATCH", "教师不能被设置为学生成员", 422)
        if course_role in {"owner", "editor"} and normalized not in {"teacher", "admin"}:
            raise CourseEnrollmentError("ROLE_MISMATCH", "学生不能被设置为课程管理成员", 422)

    def _owner_count(self, course_id: str) -> int:
        return sum(item.role == "owner" for item in self._memberships.list_for_course(course_id))
