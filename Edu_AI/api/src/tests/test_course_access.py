from __future__ import annotations

import pytest

from app.services.course_access import (
    CourseAccessDenied,
    CourseAccessService,
    CoursePrincipal,
    can_manage_course_resources,
)
from app.services.course_membership_store import CourseMembershipStore


@pytest.fixture
def store(tmp_path):
    return CourseMembershipStore(tmp_path / "memberships.json")


@pytest.mark.parametrize(
    ("role", "capability", "allowed"),
    [
        ("viewer", "read", True),
        ("viewer", "edit", False),
        ("viewer", "generate", False),
        ("editor", "edit", True),
        ("editor", "generate", True),
        ("editor", "manage_resources", True),
        ("editor", "manage_members", False),
        ("owner", "manage_members", True),
        ("owner", "delete_course", True),
    ],
)
def test_course_access_matrix(store, role, capability, allowed):
    store.upsert("course-1", "user-a", role, added_by="system")
    service = CourseAccessService(store)
    user = {"username": "user-a", "role": "teacher"}

    if allowed:
        assert service.require("course-1", user, capability).course_role == role
    else:
        with pytest.raises(CourseAccessDenied) as caught:
            service.require("course-1", user, capability)
        assert caught.value.capability == capability


def test_missing_membership_is_denied(store):
    service = CourseAccessService(store)

    with pytest.raises(CourseAccessDenied) as caught:
        service.require(
            "course-1",
            {"username": "outsider", "role": "teacher"},
            "read",
        )

    assert caught.value.course_id == "course-1"
    assert caught.value.user_id == "outsider"


def test_missing_authenticated_identity_is_denied(store):
    service = CourseAccessService(store)

    with pytest.raises(CourseAccessDenied):
        service.require("course-1", {"role": "teacher"}, "read")


def test_course_resource_management_capability_is_derived_from_course_role():
    assert can_manage_course_resources(CoursePrincipal(
        course_id="course-1",
        user_id="teacher-a",
        system_role="teacher",
        course_role="editor",
    )) is True
    assert can_manage_course_resources(CoursePrincipal(
        course_id="course-1",
        user_id="student-a",
        system_role="student",
        course_role="viewer",
    )) is False
