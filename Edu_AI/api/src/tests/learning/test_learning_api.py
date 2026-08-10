from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import course_dependencies, learning
from app.learning.service import LearningService
from app.learning.store import LearningStore
from app.services.course_access import CourseAccessService
from app.services.course_membership_store import CourseMembershipStore


class LearningApiFactory:
    def __init__(self, tmp_path):
        self.memberships = CourseMembershipStore(tmp_path / "memberships.json")
        self.memberships.upsert("course-1", "teacher-1", "owner", added_by="fixture")
        self.memberships.upsert("course-1", "student-1", "viewer", added_by="fixture")
        self.memberships.upsert("course-1", "teacher-viewer", "viewer", added_by="fixture")
        self.access = CourseAccessService(self.memberships)
        self.service = LearningService(
            store=LearningStore(tmp_path / "learning.db"),
            material_lookup=lambda *args: None,
            membership_lookup=self.memberships.list_for_course,
        )

    def client(self, username: str, role: str) -> TestClient:
        identity = {"username": username, "role": role}
        app = FastAPI()
        app.include_router(learning.router)
        app.dependency_overrides[course_dependencies.get_current_user] = lambda: identity
        app.dependency_overrides[course_dependencies.get_course_access_service] = lambda: self.access
        app.dependency_overrides[learning.get_learning_service] = lambda: self.service
        return TestClient(app)


def test_teacher_student_learning_api_round_trip(tmp_path):
    factory = LearningApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    student = factory.client("student-1", "student")

    created = teacher.post(
        "/api/courses/course-1/learning/tasks",
        json={
            "title": "Quick sort practice",
            "instructions": "Read and complete",
            "knowledge_point_ids": ["quick-sort"],
            "resource_refs": [],
        },
    )
    assert created.status_code == 201
    task_id = created.json()["task_id"]
    assert created.json()["status"] == "draft"
    assert student.get("/api/courses/course-1/learning/tasks").json() == []

    published = teacher.post(
        f"/api/courses/course-1/learning/tasks/{task_id}/publish"
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    student_tasks = student.get("/api/courses/course-1/learning/tasks")
    assert student_tasks.status_code == 200
    assert student_tasks.json()[0]["task_id"] == task_id
    assert student_tasks.json()[0]["my_progress"] is None

    event = student.post(
        f"/api/courses/course-1/learning/tasks/{task_id}/events",
        json={
            "event_id": "evt-api-complete",
            "event_type": "completed",
            "progress_percent": 100,
        },
    )
    assert event.status_code == 200
    assert event.json()["created"] is True
    assert event.json()["progress"]["status"] == "completed"

    summary = teacher.get(
        f"/api/courses/course-1/learning/tasks/{task_id}/progress"
    )
    assert summary.status_code == 200
    assert summary.json()["completed_students"] == 1
    assert summary.json()["completion_rate"] == 0.5


def test_only_students_can_submit_learning_events(tmp_path):
    factory = LearningApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    teacher_viewer = factory.client("teacher-viewer", "teacher")
    created = teacher.post(
        "/api/courses/course-1/learning/tasks",
        json={"title": "Task", "instructions": "", "resource_refs": [], "knowledge_point_ids": []},
    ).json()
    teacher.post(
        f"/api/courses/course-1/learning/tasks/{created['task_id']}/publish"
    )

    response = teacher_viewer.post(
        f"/api/courses/course-1/learning/tasks/{created['task_id']}/events",
        json={
            "event_id": "evt-invalid-role",
            "event_type": "started",
            "progress_percent": 1,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "STUDENT_ROLE_REQUIRED"
