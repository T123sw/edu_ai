from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import assessment as assessment_api
from app.api import course_dependencies, learning
from app.assessment.service import AssessmentService
from app.assessment.store import AssessmentStore
from app.assessment.models import AssessmentItemRecord
from app.learning.service import LearningService
from app.learning.store import LearningStore
from app.services.course_access import CourseAccessService
from app.services.course_membership_store import CourseMembershipStore


class AuthoringApiFactory:
    def __init__(self, tmp_path, *, generator=None):
        self.memberships = CourseMembershipStore(tmp_path / "memberships.json")
        self.memberships.upsert("course-1", "teacher-1", "owner", added_by="fixture")
        self.memberships.upsert("course-1", "student-1", "viewer", added_by="fixture")
        self.access = CourseAccessService(self.memberships)
        self.materials = {
            ("course-1", "quiz", "quiz-1"): {
                "material_id": "quiz-1",
                "material_type": "quiz",
                "visibility": "course",
                "questions": [
                    {
                        "id": "q1",
                        "type": "choice",
                        "stem": "Python 循环关键字是？",
                        "options": ["for", "when", "switch"],
                        "answer": "A",
                        "explanation": "for 用于迭代。",
                    }
                ],
            }
        }

        def material_lookup(course_id, material_type, material_id, _user_id):
            return self.materials.get((course_id, material_type, material_id))

        self.learning_service = LearningService(
            store=LearningStore(tmp_path / "learning.db"),
            material_lookup=material_lookup,
            membership_lookup=self.memberships.list_for_course,
        )
        self.assessment_service = AssessmentService(
            store=AssessmentStore(tmp_path / "assessment.db"),
            learning_service=self.learning_service,
            material_lookup=material_lookup,
            generator=generator,
        )

    def client(self, username: str, role: str) -> TestClient:
        identity = {"username": username, "role": role}
        app = FastAPI()
        app.include_router(learning.router)
        app.include_router(assessment_api.router)
        app.dependency_overrides[course_dependencies.get_current_user] = lambda: identity
        app.dependency_overrides[course_dependencies.get_course_access_service] = lambda: self.access
        app.dependency_overrides[learning.get_learning_service] = lambda: self.learning_service
        app.dependency_overrides[learning.get_assessment_service] = lambda: self.assessment_service
        app.dependency_overrides[assessment_api.get_assessment_service] = lambda: self.assessment_service
        return TestClient(app)


def _create_task(teacher: TestClient) -> dict:
    response = teacher.post(
        "/api/courses/course-1/learning/tasks",
        json={
            "title": "循环学习",
            "instructions": "阅读并完成测评",
            "resource_refs": [{"material_type": "quiz", "material_id": "quiz-1"}],
            "knowledge_point_ids": ["loops"],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_new_task_cannot_publish_without_confirmed_assessment(tmp_path):
    factory = AuthoringApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    task = _create_task(teacher)

    response = teacher.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/publish"
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ASSESSMENT_REQUIRED"
    stored = factory.learning_service.store.get_task(task["task_id"], course_id="course-1")
    assert stored.status == "draft"


def test_reading_task_publishes_without_assessment(tmp_path):
    factory = AuthoringApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    created = teacher.post(
        "/api/courses/course-1/learning/tasks",
        json={
            "task_type": "reading",
            "title": "阅读学习",
            "instructions": "阅读材料后标记完成",
            "resource_refs": [
                {"material_type": "quiz", "material_id": "quiz-1"}
            ],
            "knowledge_point_ids": ["loops"],
        },
    )
    assert created.status_code == 201

    published = teacher.post(
        f"/api/courses/course-1/learning/tasks/{created.json()['task_id']}/publish",
        json={},
    )

    assert published.status_code == 200
    assert published.json()["task_type"] == "reading"
    assert published.json()["status"] == "published"


def test_existing_quiz_is_detected_validated_and_published_with_task(tmp_path):
    factory = AuthoringApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    student = factory.client("student-1", "student")
    task = _create_task(teacher)

    detected = teacher.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment/detect"
    )
    assert detected.status_code == 200
    assert detected.json()["source_mode"] == "imported"
    assert detected.json()["draft_revision"] == 1
    assert detected.json()["items"][0]["created_origin"] == "imported"
    assert detected.json()["quality"]["publishable"] is True

    published = teacher.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/publish"
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert student.get("/api/courses/course-1/learning/tasks").json()[0]["task_id"] == task["task_id"]

    restored = teacher.get(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment/draft"
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "published"
    assert restored.json()["content_hash"]


def test_student_cannot_open_teacher_assessment_draft(tmp_path):
    factory = AuthoringApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    student = factory.client("student-1", "student")
    task = _create_task(teacher)

    response = student.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment/detect"
    )

    assert response.status_code == 403


def test_teacher_updates_settings_with_optimistic_revision(tmp_path):
    factory = AuthoringApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    task = _create_task(teacher)
    draft = teacher.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment/detect"
    ).json()
    payload = {
        "expected_revision": draft["draft_revision"],
        "pass_threshold": 70,
        "mastery_threshold": 90,
        "max_attempts": 2,
        "assessment_mode": draft["assessment_mode"],
        "answer_reveal_policy": draft["answer_reveal_policy"],
        "shuffle_questions": True,
        "shuffle_options": True,
        "items": draft["items"],
    }

    updated = teacher.put(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment/draft",
        json=payload,
    )

    assert updated.status_code == 200
    assert updated.json()["draft_revision"] == draft["draft_revision"] + 1
    assert updated.json()["pass_threshold"] == 70
    assert updated.json()["max_attempts"] == 2
    stale = teacher.put(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment/draft",
        json=payload,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "DRAFT_REVISION_CONFLICT"


def test_teacher_generates_only_missing_coverage_from_course_material(tmp_path):
    class FakeGenerator:
        def generate(self, **kwargs):
            knowledge_point = kwargs["coverage_gaps"][0]
            return [
                AssessmentItemRecord.new(
                    assessment_version_id=kwargs["assessment_version_id"],
                    position=1,
                    item_type="code_trace",
                    prompt={"stem": "What does this loop print?"},
                    scoring_key={"accepted_answers": ["0 1 2"]},
                    rubric={},
                    max_score=10,
                    grading_provider="deterministic",
                    knowledge_point_ids=[knowledge_point],
                    source_refs=[{"material_type": "report", "material_id": "report-1"}],
                    created_origin="generated",
                )
            ]

    factory = AuthoringApiFactory(tmp_path, generator=FakeGenerator())
    factory.materials[("course-1", "report", "report-1")] = {
        "material_id": "report-1",
        "material_type": "report",
        "visibility": "course",
        "content": "A Python for loop visits each value in a sequence.",
    }
    teacher = factory.client("teacher-1", "teacher")
    created = teacher.post(
        "/api/courses/course-1/learning/tasks",
        json={
            "title": "Loop tracing",
            "instructions": "Read and assess",
            "resource_refs": [{"material_type": "report", "material_id": "report-1"}],
            "knowledge_point_ids": ["loops"],
        },
    ).json()
    draft = teacher.post(
        f"/api/courses/course-1/learning/tasks/{created['task_id']}/assessment/detect"
    ).json()

    generated = teacher.post(
        f"/api/courses/course-1/learning/tasks/{created['task_id']}/assessment/generate",
        json={"expected_revision": draft["draft_revision"], "difficulty": "medium"},
    )

    assert generated.status_code == 200
    assert generated.json()["items"][0]["item_type"] == "code_trace"
    assert generated.json()["items"][0]["created_origin"] == "generated"
    assert generated.json()["quality"]["publishable"] is True


def test_generation_infers_assessment_context_when_task_has_no_knowledge_points(tmp_path):
    class MaterialDrivenGenerator:
        def __init__(self):
            self.calls = []

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            return [
                AssessmentItemRecord.new(
                    assessment_version_id=kwargs["assessment_version_id"],
                    position=1,
                    item_type="code_trace",
                    prompt={"stem": "What is the partition result?"},
                    scoring_key={"accepted_answers": ["[1, 2, 3]"]},
                    rubric={},
                    max_score=10,
                    grading_provider="deterministic",
                    knowledge_point_ids=["partition"],
                    source_refs=[{"material_type": "report", "material_id": "report-1"}],
                    created_origin="generated",
                )
            ]

    generator = MaterialDrivenGenerator()
    factory = AuthoringApiFactory(tmp_path, generator=generator)
    factory.materials[("course-1", "report", "report-1")] = {
        "material_id": "report-1",
        "material_type": "report",
        "visibility": "course",
        "content": "Quick sort partitions a sequence around a pivot.",
    }
    teacher = factory.client("teacher-1", "teacher")
    created = teacher.post(
        "/api/courses/course-1/learning/tasks",
        json={
            "title": "Quick sort",
            "instructions": "Read and assess",
            "resource_refs": [{"material_type": "report", "material_id": "report-1"}],
            "knowledge_point_ids": [],
        },
    ).json()
    draft = teacher.post(
        f"/api/courses/course-1/learning/tasks/{created['task_id']}/assessment/detect"
    ).json()

    generated = teacher.post(
        f"/api/courses/course-1/learning/tasks/{created['task_id']}/assessment/generate",
        json={"expected_revision": draft["draft_revision"], "difficulty": "medium"},
    )

    assert generated.status_code == 200
    assert generated.json()["items"][0]["knowledge_point_ids"] == ["partition"]
    assert generator.calls[0]["coverage_gaps"] == []
    assert generator.calls[0]["task_title"] == "Quick sort"
    assert generator.calls[0]["task_instructions"] == "Read and assess"


def test_publish_rejects_a_stale_assessment_revision(tmp_path):
    factory = AuthoringApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    task = _create_task(teacher)
    draft = teacher.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment/detect"
    ).json()
    update_payload = {
        "expected_revision": draft["draft_revision"],
        "pass_threshold": 65,
        "mastery_threshold": 85,
        "max_attempts": 3,
        "assessment_mode": draft["assessment_mode"],
        "answer_reveal_policy": draft["answer_reveal_policy"],
        "shuffle_questions": False,
        "shuffle_options": False,
        "items": draft["items"],
    }
    assert teacher.put(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment/draft",
        json=update_payload,
    ).status_code == 200

    response = teacher.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/publish",
        json={"expected_revision": draft["draft_revision"]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DRAFT_REVISION_CONFLICT"
    assert factory.learning_service.store.get_task(
        task["task_id"], course_id="course-1"
    ).status == "draft"
