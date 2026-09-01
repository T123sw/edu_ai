from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.course_dependencies import get_course_access_service
from app.auth import get_current_user
from app.chat.api import routes_v2
from app.services.course_access import CourseAccessDenied, CoursePrincipal


class FakeCourseAccessService:
    def __init__(self, *, allow_read: bool = True):
        self.allow_read = allow_read
        self.calls: list[tuple[str, str]] = []

    def require(self, course_id, user, capability):
        self.calls.append((course_id, capability))
        if capability == "read" and not self.allow_read:
            raise CourseAccessDenied(
                course_id=course_id,
                user_id=str(user.get("username") or ""),
                capability="read",
            )
        return CoursePrincipal(
            course_id=course_id,
            user_id=str(user.get("username") or ""),
            system_role=str(user.get("role") or ""),
            course_role="viewer",
        )


@pytest.fixture()
def authorization_client(monkeypatch):
    active_user = {"username": "user-a", "role": "student"}
    access_service = FakeCourseAccessService()
    app = FastAPI()
    app.include_router(routes_v2.router)
    app.dependency_overrides[get_current_user] = lambda: active_user
    app.dependency_overrides[get_course_access_service] = lambda: access_service

    monkeypatch.setattr(
        routes_v2,
        "_get_generation_source_resolver",
        lambda: SimpleNamespace(
            validate=lambda *_args, **_kwargs: (),
            resolve=lambda *_args, **_kwargs: SimpleNamespace(documents=()),
        ),
    )
    monkeypatch.setattr(
        routes_v2.generation_command_service,
        "submit",
        lambda _command: SimpleNamespace(edu_job_id="job-1"),
    )
    with TestClient(app) as client:
        yield client, active_user, access_service


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/api/chat/v2/lesson-plan/direct",
            {
                "course_id": "c1",
                "topic": "函数",
                "source_mode": "none",
                "selected_doc_ids": [],
            },
        ),
        (
            "/api/chat/v2/blog/direct",
            {
                "course_id": "c1",
                "topic": "函数",
                "idempotency_key": "student-blog",
                "source_mode": "none",
                "selected_doc_ids": [],
            },
        ),
    ],
)
def test_student_cannot_call_teacher_only_direct_tools(
    authorization_client,
    path,
    payload,
):
    client, _, _ = authorization_client

    response = client.post(path, json=payload)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERSONAL_TOOL_ACCESS_DENIED"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/api/chat/v2/flashcard/direct",
            {
                "course_id": "c1",
                "flashcard_config": {"title": "复习"},
                "idempotency_key": "teacher-flashcard",
                "source_mode": "none",
                "selected_doc_ids": [],
            },
        ),
        (
            "/api/chat/v2/game/direct",
            {
                "course_id": "c1",
                "game_type": "drag_match",
                "idempotency_key": "teacher-game",
                "source_mode": "none",
                "selected_doc_ids": [],
            },
        ),
    ],
)
def test_teacher_cannot_call_student_only_direct_tools(
    authorization_client,
    path,
    payload,
):
    client, active_user, _ = authorization_client
    active_user["role"] = "teacher"

    response = client.post(path, json=payload)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERSONAL_TOOL_ACCESS_DENIED"


def test_allowed_student_direct_tool_uses_course_read_not_generate(
    authorization_client,
):
    client, _, access_service = authorization_client

    response = client.post(
        "/api/chat/v2/quiz/direct",
        json={
            "course_id": "c1",
            "quiz_config": {"topic": "函数"},
            "idempotency_key": "student-quiz",
            "source_mode": "none",
            "selected_doc_ids": [],
        },
    )

    assert response.status_code == 202
    assert access_service.calls == [("c1", "read")]

