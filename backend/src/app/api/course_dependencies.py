"""FastAPI adapters for the course authorization service."""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import Depends, HTTPException, status

from app.auth import get_current_user
from app.services.course_access import (
    CourseAccessDenied,
    CourseAccessService,
    CourseCapability,
    CoursePrincipal,
)
from app.services.course_membership_store import CourseMembershipStore
from core import Config


_dependency_lock = threading.RLock()
_cached_membership_path: Path | None = None
_cached_membership_store: CourseMembershipStore | None = None


def get_course_membership_store() -> CourseMembershipStore:
    global _cached_membership_path, _cached_membership_store
    configured = getattr(
        Config,
        "COURSE_MEMBERSHIPS_FILE",
        Path(Config.STORAGE_ROOT) / "course_memberships.json",
    )
    path = Path(configured)
    with _dependency_lock:
        if _cached_membership_store is None or _cached_membership_path != path:
            _cached_membership_path = path
            _cached_membership_store = CourseMembershipStore(path)
        return _cached_membership_store


def get_course_access_service() -> CourseAccessService:
    return CourseAccessService(get_course_membership_store())


def require_course_capability(
    course_id: str,
    current_user: dict,
    capability: CourseCapability,
    access_service: CourseAccessService,
) -> CoursePrincipal:
    try:
        return access_service.require(course_id, current_user, capability)
    except CourseAccessDenied as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "COURSE_ACCESS_DENIED",
                "course_id": exc.course_id,
                "capability": exc.capability,
            },
        ) from exc


def require_course_read(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    access_service: CourseAccessService = Depends(get_course_access_service),
) -> CoursePrincipal:
    return require_course_capability(course_id, current_user, "read", access_service)


def require_course_edit(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    access_service: CourseAccessService = Depends(get_course_access_service),
) -> CoursePrincipal:
    return require_course_capability(course_id, current_user, "edit", access_service)


def require_course_generate(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    access_service: CourseAccessService = Depends(get_course_access_service),
) -> CoursePrincipal:
    return require_course_capability(
        course_id, current_user, "generate", access_service
    )


def require_course_manage_resources(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    access_service: CourseAccessService = Depends(get_course_access_service),
) -> CoursePrincipal:
    return require_course_capability(
        course_id, current_user, "manage_resources", access_service
    )


def require_course_owner(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    access_service: CourseAccessService = Depends(get_course_access_service),
) -> CoursePrincipal:
    return require_course_capability(
        course_id, current_user, "manage_members", access_service
    )
