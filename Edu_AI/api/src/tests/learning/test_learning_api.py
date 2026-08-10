from __future__ import annotations

import json

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

        def material_lookup(course_id, material_type, material_id, user_id):
            del user_id
            if (course_id, material_type, material_id) == ("course-1", "report", "report-1"):
                return {"visibility": "course"}
            return None

        self.service = LearningService(
            store=LearningStore(tmp_path / "learning.db"),
            material_lookup=material_lookup,
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


def test_learning_event_api_persists_evidence_payload(tmp_path):
    factory = LearningApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    student = factory.client("student-1", "student")
    created = teacher.post(
        "/api/courses/course-1/learning/tasks",
        json={
            "title": "Assessment",
            "instructions": "",
            "resource_refs": [{"material_type": "report", "material_id": "report-1"}],
            "knowledge_point_ids": [],
        },
    ).json()
    task_id = created["task_id"]
    teacher.post(f"/api/courses/course-1/learning/tasks/{task_id}/publish")

    response = student.post(
        f"/api/courses/course-1/learning/tasks/{task_id}/events",
        json={
            "event_id": "evt-api-score",
            "event_type": "assessment_scored",
            "progress_percent": 100,
            "resource_ref": {"material_type": "report", "material_id": "report-1"},
            "evidence": {
                "evidence_type": "score",
                "source_type": "quiz",
                "source_id": "quiz-attempt-1",
                "value": 92.0,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["progress"]["completion_basis"] == "assessment_verified"
    stored = factory.service.store._connection.execute(
        "SELECT evidence_json FROM learning_events WHERE event_id='evt-api-score'"
    ).fetchone()
    evidence = json.loads(stored["evidence_json"])
    assert evidence.pop("occurred_at")
    assert evidence == {
        "evidence_type": "score",
        "source_type": "quiz",
        "source_id": "quiz-attempt-1",
        "value": 92.0,
    }


def test_learning_overview_is_role_scoped_and_requires_teacher_edit_access(tmp_path):
    factory = LearningApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    student = factory.client("student-1", "student")
    teacher_viewer = factory.client("teacher-viewer", "teacher")
    task = teacher.post(
        "/api/courses/course-1/learning/tasks",
        json={"title": "Task", "instructions": "", "resource_refs": [], "knowledge_point_ids": []},
    ).json()
    teacher.post(f"/api/courses/course-1/learning/tasks/{task['task_id']}/publish")
    student.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/events",
        json={"event_id": "evt-overview", "event_type": "completed", "progress_percent": 100},
    )

    student_overview = student.get("/api/courses/course-1/learning/overview")
    assert student_overview.status_code == 200
    assert student_overview.json()["self_reported_completed_tasks"] == 1
    assert student_overview.json()["enrolled_students"] is None
    assert "teacher-viewer" not in student_overview.text

    teacher_overview = teacher.get("/api/courses/course-1/learning/overview")
    assert teacher_overview.status_code == 200
    assert teacher_overview.json()["enrolled_students"] == 2
    assert teacher_overview.json()["self_reported_students"] == 1
    assert "student-1" not in teacher_overview.text

    assert teacher_viewer.get("/api/courses/course-1/learning/overview").status_code == 403


def test_learning_overview_rejects_student_outside_course(tmp_path):
    factory = LearningApiFactory(tmp_path)
    outsider = factory.client("student-outsider", "student")

    response = outsider.get("/api/courses/course-1/learning/overview")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "COURSE_ACCESS_DENIED"
