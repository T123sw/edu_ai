from __future__ import annotations

import re
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import course_dependencies, learning
from app.chat.domain.contracts import ChatRequestV2
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.runtime.fast_chat_runtime import FastChatRuntime
from app.learning.context_reader import LearningContextReader
from app.learning.service import LearningRuleError, LearningService
from app.learning.store import LearningStore
from app.services.course_access import CourseAccessService
from app.services.course_membership_store import CourseMembershipStore


@dataclass(frozen=True)
class Membership:
    user_id: str
    role: str


class CaptureGateway:
    def __init__(self, response: str):
        self.messages = []
        self.response = response

    def chat(self, messages):
        self.messages = messages
        return self.response


def _request(*, actor_role: str, owner: str, question: str) -> ChatRequestV2:
    return ChatRequestV2(
        question=question,
        actor_role=actor_role,
        owner=owner,
        course_id="course-1",
        conversation_id=None,
    )


def _prompt_for(service: LearningService, request: ChatRequestV2, answer: str) -> str:
    snapshot = ContextBuilder(
        conversation_store=SimpleNamespace(),
        learning_context_reader=LearningContextReader(service),
    ).build(request)
    gateway = CaptureGateway(answer)
    result = FastChatRuntime(model_gateway=gateway).run(
        request=request,
        snapshot=snapshot,
        decision=None,
    )
    assert result["message"]["content"] == answer
    return gateway.messages[0]["content"]


def test_teacher_student_learning_loop_reaches_role_scoped_agent_conversations(tmp_path):
    memberships = [
        Membership("teacher-1", "owner"),
        Membership("student-1", "viewer"),
    ]
    service = LearningService(
        store=LearningStore(tmp_path / "learning.db"),
        material_lookup=lambda *args: None,
        membership_lookup=lambda course_id: memberships if course_id == "course-1" else [],
    )
    task = service.create_task(
        course_id="course-1",
        teacher_id="teacher-1",
        title="完成快速排序学习",
        instructions="阅读课程资料并完成学习",
        resource_refs=[],
        knowledge_point_ids=["quick-sort"],
    )
    service.publish_task(
        course_id="course-1",
        task_id=task.task_id,
        teacher_id="teacher-1",
    )
    service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="evt-start",
        event_type="started",
        progress_percent=1,
        resource_ref=None,
    )
    service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="evt-complete",
        event_type="completed",
        progress_percent=100,
        resource_ref=None,
    )

    summary = service.get_task_summary(
        course_id="course-1",
        task_id=task.task_id,
        teacher_id="teacher-1",
    )
    assert summary.completed_students == 1
    assert summary.completion_rate == 1.0

    student_prompt = _prompt_for(
        service,
        _request(
            actor_role="student",
            owner="student-1",
            question="我刚完成了什么学习任务？下一步做什么？",
        ),
        "完成快速排序学习：学生自报完成；下一步复盘快速排序分区过程。",
    )
    teacher_prompt = _prompt_for(
        service,
        _request(
            actor_role="teacher",
            owner="teacher-1",
            question="这门课最新学习任务完成情况怎样？只根据学习记录回答。",
        ),
        "完成快速排序学习：1/1 名学生自报完成；自报不等于测评通过。",
    )

    assert "【当前学习状态】" in student_prompt
    assert "完成快速排序学习" in student_prompt
    assert '"task_id":"lt_' in student_prompt
    assert '"status":"completed"' in student_prompt
    assert '"completion_basis":"self_reported"' in student_prompt
    assert re.search(r"job_[a-z0-9]+", student_prompt) is None

    assert "【当前学习状态】" in teacher_prompt
    assert "完成快速排序学习" in teacher_prompt
    assert '"enrolled_students":1' in teacher_prompt
    assert '"started_students":1' in teacher_prompt
    assert '"completed_students":1' in teacher_prompt
    assert '"completion_basis_counts":{"self_reported":1' in teacher_prompt
    assert "student-1" not in teacher_prompt
    assert re.search(r"job_[a-z0-9]+", teacher_prompt) is None


def test_learning_events_are_idempotent_monotonic_and_survive_store_restart(tmp_path):
    db_path = tmp_path / "learning.db"
    memberships = [
        Membership("teacher-1", "owner"),
        Membership("student-1", "viewer"),
    ]

    def build_service() -> LearningService:
        return LearningService(
            store=LearningStore(db_path),
            material_lookup=lambda *_args: {
                "visibility": "course",
                "material_type": "report",
                "material_id": "report-1",
            },
            membership_lookup=lambda course_id: memberships if course_id == "course-1" else [],
        )

    service = build_service()
    task = service.create_task(
        course_id="course-1",
        teacher_id="teacher-1",
        title="E2E-LOOP2-persistence",
        instructions="open, then complete",
        resource_refs=[{"material_type": "report", "material_id": "report-1"}],
        knowledge_point_ids=["quick-sort"],
    )
    service.publish_task(course_id="course-1", task_id=task.task_id, teacher_id="teacher-1")
    first = service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="evt-open",
        event_type="resource_opened",
        progress_percent=1,
        resource_ref={"material_type": "report", "material_id": "report-1"},
    )
    duplicate = service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="evt-open",
        event_type="resource_opened",
        progress_percent=1,
        resource_ref={"material_type": "report", "material_id": "report-1"},
    )
    completed = service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="evt-complete",
        event_type="completed",
        progress_percent=100,
        resource_ref=None,
    )
    late_started = service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="evt-late-started",
        event_type="started",
        progress_percent=1,
        resource_ref=None,
    )

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.progress.evidence_count == first.progress.evidence_count
    assert completed.progress.completion_basis == "self_reported"
    assert late_started.progress.progress_percent == 100
    assert late_started.progress.completion_basis == "self_reported"

    restarted = build_service()
    persisted_task = restarted.list_tasks(
        course_id="course-1",
        user_id="student-1",
        include_unpublished=False,
    )[0]
    assert persisted_task.task.task_id == task.task_id
    assert persisted_task.my_progress is not None
    assert persisted_task.my_progress.progress_percent == 100
    assert persisted_task.my_progress.completion_basis == "self_reported"


class AcceptanceApi:
    def __init__(self, tmp_path):
        self.memberships = CourseMembershipStore(tmp_path / "memberships.json")
        self.memberships.upsert("course-1", "teacher-1", "owner", added_by="fixture")
        self.memberships.upsert("course-1", "student-1", "viewer", added_by="fixture")
        self.access = CourseAccessService(self.memberships)
        self.service = LearningService(
            store=LearningStore(tmp_path / "learning.db"),
            material_lookup=lambda *_args: None,
            membership_lookup=self.memberships.list_for_course,
        )

    def client(self, username: str, role: str) -> TestClient:
        app = FastAPI()
        app.include_router(learning.router)
        app.dependency_overrides[course_dependencies.get_current_user] = lambda: {
            "username": username,
            "role": role,
        }
        app.dependency_overrides[course_dependencies.get_course_access_service] = lambda: self.access
        app.dependency_overrides[learning.get_learning_service] = lambda: self.service
        return TestClient(app)


def test_learning_loop_role_boundaries_are_enforced_by_the_http_api(tmp_path):
    api = AcceptanceApi(tmp_path)
    teacher = api.client("teacher-1", "teacher")
    student = api.client("student-1", "student")
    created = teacher.post(
        "/api/courses/course-1/learning/tasks",
        json={
            "title": "E2E-LOOP2-permissions",
            "instructions": "",
            "resource_refs": [],
            "knowledge_point_ids": [],
        },
    ).json()
    teacher.post(f"/api/courses/course-1/learning/tasks/{created['task_id']}/publish")

    assert student.post(
        "/api/courses/course-1/learning/tasks",
        json={
            "title": "forbidden",
            "instructions": "",
            "resource_refs": [],
            "knowledge_point_ids": [],
        },
    ).status_code == 403
    assert student.get(
        f"/api/courses/course-1/learning/tasks/{created['task_id']}/progress"
    ).status_code == 403
    response = teacher.post(
        f"/api/courses/course-1/learning/tasks/{created['task_id']}/events",
        json={
            "event_id": "evt-teacher-impersonation",
            "event_type": "started",
            "progress_percent": 1,
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "STUDENT_ROLE_REQUIRED"


def test_student_cannot_read_another_students_learning_context(tmp_path):
    service = LearningService(
        store=LearningStore(tmp_path / "learning.db"),
        material_lookup=lambda *_args: None,
        membership_lookup=lambda _course_id: [
            Membership("teacher-1", "owner"),
            Membership("student-1", "viewer"),
        ],
    )

    with pytest.raises(LearningRuleError, match="Course read permission") as error:
        service.get_student_agent_context(course_id="course-1", student_id="student-2")

    assert error.value.code == "COURSE_READ_REQUIRED"
