from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import course_dependencies
from app.api.resource_qa import get_resource_qa_service, router
from app.services.classroom_qa_store import ClassroomQaSessionStore
from app.services.resource_qa_service import ResourceQaService
from course_api_test_support import CourseApiTestFactory


class Repository:
    def __init__(self):
        self.approved_version = 2

    def get(self, course_id, material_type, material_id):
        return {
            "origin_type": "standard", "standard_kind": "study_guide",
            "approved_version": self.approved_version, "version": 2,
        }

    def get_version(self, course_id, material_type, material_id, version):
        return {
            "title": "递归指南", "origin_type": "standard", "standard_kind": "study_guide",
            "version": version, "sections": [{"text": "递归必须有终止条件。"}],
        }


class Gateway:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        return json.dumps({"answer_text": "终止条件避免无限递归。", "transition_text": "继续阅读。"}, ensure_ascii=False)


class FileTts:
    async def synthesize_and_store(self, *, session_dir: Path, turn_id: str, text: str):
        audio_dir = session_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{turn_id}.mp3"
        (audio_dir / filename).write_bytes(b"ID3-resource-audio")
        return filename, "audio/mpeg"


class Harness:
    def __init__(self, tmp_path, monkeypatch):
        self.course = CourseApiTestFactory(tmp_path, monkeypatch)
        self.course.users.append({"username": "student-b", "role": "student"})
        self.course.memberships.upsert("course-1", "student-b", "viewer", added_by="fixture")
        self.repository = Repository()
        self.gateway = Gateway()
        self.store = ClassroomQaSessionStore(self.course.manager)
        self.service = ResourceQaService(
            repository=self.repository, store=self.store, storage=self.course.manager,
            gateway=self.gateway, tts=FileTts(),
        )

    def client(self, username="student-a", role="student"):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[course_dependencies.get_current_user] = lambda: {"username": username, "role": role}
        app.dependency_overrides[course_dependencies.get_course_access_service] = lambda: self.course.access
        app.dependency_overrides[get_resource_qa_service] = lambda: self.service
        return TestClient(app)

    def anonymous(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[course_dependencies.get_course_access_service] = lambda: self.course.access
        app.dependency_overrides[get_resource_qa_service] = lambda: self.service
        return TestClient(app)


@pytest.fixture
def qa(tmp_path, monkeypatch):
    return Harness(tmp_path, monkeypatch)


def base_route():
    return "/api/courses/course-1/resources/study_guide/guide-1/qa"


def payload(client_turn_id=None):
    return {
        "client_turn_id": str(client_turn_id or uuid4()),
        "question": "为什么需要终止条件？",
        "resource_version": 2,
        "context_scope": "full_resource",
        "anchor": {"page_number": 1},
    }


def test_session_requires_auth_membership_and_approved_version(qa):
    url = f"{base_route()}/session?resource_version=2"
    assert qa.anonymous().get(url).status_code == 401
    assert qa.client("outsider").get(url).status_code == 403
    assert qa.client().get(url).status_code == 200
    qa.repository.approved_version = 1
    assert qa.client().get(url).status_code == 404


def test_turn_is_idempotent_and_audio_is_owner_protected(qa):
    turn_id = uuid4()
    client = qa.client("student-a")
    first = client.post(f"{base_route()}/turns", json=payload(turn_id))
    second = client.post(f"{base_route()}/turns", json=payload(turn_id))

    assert first.status_code == 200
    assert first.json() == second.json()
    assert qa.gateway.calls == 1
    audio_url = first.json()["turn"]["audio_url"]
    assert client.get(audio_url).content == b"ID3-resource-audio"
    assert qa.client("student-b").get(audio_url).status_code == 404
    assert client.get(audio_url.rsplit("/", 1)[0] + "/unknown.mp3?resource_version=2").status_code == 404
    assert client.get(audio_url.rsplit("/", 1)[0] + "/..%2Fsession.json?resource_version=2").status_code == 404


def test_resource_kind_is_restricted_by_the_route(qa):
    response = qa.client().get(
        "/api/courses/course-1/resources/classroom/guide-1/qa/session?resource_version=2"
    )
    assert response.status_code == 422
