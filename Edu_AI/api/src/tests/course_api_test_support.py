from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import course_dependencies, courses
from app.services.course_access import CourseAccessService
from app.services.course_membership_bootstrap import CourseMembershipBootstrap
from app.services.course_membership_store import CourseMembershipStore
from app.services.course_enrollment_service import CourseEnrollmentService
from core.course_storage import CourseStorageManager


COURSE_FIXTURE = {
    "id": "course-1",
    "title": "Course one",
    "description": "Shared course",
    "icon": "BookOutlined",
    "color": "#3157d5",
    "objectives": ["Understand shared state"],
    "knowledgeGraph": "",
}


def course_update_payload(
    course: Mapping[str, Any], *, title: str | None = None
) -> dict[str, Any]:
    return {
        "title": title if title is not None else course["title"],
        "description": course["description"],
        "icon": course["icon"],
        "color": course["color"],
        "objectives": course.get("objectives"),
        "knowledgeGraph": course.get("knowledgeGraph"),
        "expected_revision": course["revision"],
    }


class CourseApiTestFactory:
    def __init__(self, tmp_path: Path, monkeypatch) -> None:
        self.manager = CourseStorageManager(root_path=str(tmp_path / "courses"))
        self.manager.create_course_structure("course-1")
        self.manager.save_course_info("course-1", dict(COURSE_FIXTURE))
        self.memberships = CourseMembershipStore(tmp_path / "memberships.json")
        self.users = [
            {"username": "teacher-a", "role": "teacher"},
            {"username": "teacher-b", "role": "teacher"},
            {"username": "student-a", "role": "student"},
        ]
        self.memberships.upsert(
            "course-1", "teacher-a", "editor", added_by="fixture"
        )
        self.memberships.upsert(
            "course-1", "teacher-b", "editor", added_by="fixture"
        )
        self.memberships.upsert(
            "course-1", "student-a", "viewer", added_by="fixture"
        )
        self.access = CourseAccessService(self.memberships)
        self.enrollment = CourseEnrollmentService(
            manager=self.manager,
            memberships=self.memberships,
            users_provider=lambda: list(self.users),
        )
        self.bootstrap = CourseMembershipBootstrap(
            store=self.memberships,
            enabled=True,
            users_provider=lambda: list(self.users),
            course_ids_provider=lambda: ["course-1"],
        )
        monkeypatch.setattr(courses._svc, "_get_manager", lambda: self.manager)
        monkeypatch.setattr(
            courses,
            "get_course_membership_store",
            lambda: self.memberships,
        )

    def client_for(self, username: str, system_role: str) -> TestClient:
        app = self._app()
        identity = {"username": username, "role": system_role}
        app.dependency_overrides[courses.get_current_user] = lambda: identity
        app.dependency_overrides[course_dependencies.get_current_user] = (
            lambda: identity
        )
        return TestClient(app)

    def anonymous(self) -> TestClient:
        return TestClient(self._app())

    def _app(self) -> FastAPI:
        app = FastAPI()
        app.include_router(courses.router)
        app.dependency_overrides[
            course_dependencies.get_course_membership_store
        ] = lambda: self.memberships
        app.dependency_overrides[
            course_dependencies.get_course_access_service
        ] = lambda: self.access
        app.dependency_overrides[courses.get_course_enrollment_service] = (
            lambda: self.enrollment
        )
        return app
