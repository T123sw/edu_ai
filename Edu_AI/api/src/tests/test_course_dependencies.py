from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.course_dependencies import require_course_capability
from app.services.course_access import CourseAccessService
from app.services.course_membership_store import CourseMembershipStore


def test_http_adapter_returns_course_principal(tmp_path):
    store = CourseMembershipStore(tmp_path / "memberships.json")
    store.upsert("course-1", "teacher-a", "editor", added_by="system")

    principal = require_course_capability(
        "course-1",
        {"username": "teacher-a", "role": "teacher"},
        "edit",
        CourseAccessService(store),
    )

    assert principal.user_id == "teacher-a"
    assert principal.course_role == "editor"


def test_http_adapter_maps_denial_to_stable_403(tmp_path):
    service = CourseAccessService(
        CourseMembershipStore(tmp_path / "memberships.json")
    )

    with pytest.raises(HTTPException) as caught:
        require_course_capability(
            "course-1",
            {"username": "outsider", "role": "teacher"},
            "read",
            service,
        )

    assert caught.value.status_code == 403
    assert caught.value.detail == {
        "code": "COURSE_ACCESS_DENIED",
        "course_id": "course-1",
        "capability": "read",
    }
