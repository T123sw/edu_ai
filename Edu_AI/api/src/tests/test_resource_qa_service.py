from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.schemas.resource_qa import ResourceQaTurnRequest
from app.services.classroom_qa_store import ClassroomQaSessionStore, resource_session_id
from app.services.resource_qa_service import ResourceQaError, ResourceQaService
from core.course_storage import CourseStorageManager


pytestmark = pytest.mark.anyio


class FakeRepository:
    def __init__(self, *, kind="study_guide", approved_version=2, current_version=2):
        self.kind = kind
        self.approved_version = approved_version
        self.current_version = current_version
        self.requested_version = None

    def get(self, course_id, material_type, material_id):
        return {
            "course_id": course_id,
            "material_type": material_type,
            "material_id": material_id,
            "origin_type": "standard",
            "standard_kind": self.kind,
            "approved_version": self.approved_version,
            "version": self.current_version,
        }

    def get_version(self, course_id, material_type, material_id, version):
        self.requested_version = version
        if version > self.current_version:
            return None
        if self.kind == "practice":
            return {
                "title": "练习",
                "questions": [{"id": "q-1", "stem": "1+1 等于几？", "correct_answer": "2", "explanation": "相加"}],
                "version": version,
                "origin_type": "standard",
                "standard_kind": self.kind,
            }
        return {
            "title": "指南",
            "sections": [{"heading": "递归", "content": "递归需要终止条件。"}],
            "version": version,
            "origin_type": "standard",
            "standard_kind": self.kind,
        }


class FakeGateway:
    def __init__(self):
        self.calls = 0
        self.messages = None

    def chat(self, messages, temperature=0.2, max_tokens=800):
        self.calls += 1
        self.messages = messages
        return json.dumps({"answer_text": "需要明确终止条件。", "transition_text": "继续查看资料。"}, ensure_ascii=False)


class FakeTts:
    async def synthesize_and_store(self, *, session_dir, turn_id, text):
        return f"{turn_id}.mp3", "audio/mpeg"


def request(*, version=2, client_turn_id=None):
    return ResourceQaTurnRequest(
        client_turn_id=client_turn_id or uuid4(),
        question="为什么需要终止条件？",
        resource_version=version,
    )


def create_service(tmp_path, repository):
    gateway = FakeGateway()
    store = ClassroomQaSessionStore(CourseStorageManager(root_path=str(tmp_path)))
    return ResourceQaService(repository=repository, store=store, gateway=gateway, tts=FakeTts()), gateway


async def test_submit_is_idempotent_and_loads_the_exact_version(tmp_path):
    repository = FakeRepository(approved_version=2, current_version=2)
    service, gateway = create_service(tmp_path, repository)
    turn = request(version=2)
    args = dict(
        course_id="course-1",
        resource_kind="study_guide",
        resource_id="guide-1",
        resource_version=2,
        owner_user_id="student-a",
        course_role="viewer",
        request=turn,
    )

    result = await service.submit_turn(**args)
    repeat = await service.submit_turn(**args)

    assert result == repeat
    assert gateway.calls == 1
    assert repository.requested_version == 2
    assert result["turn"]["audio_url"].endswith("resource_version=2")


async def test_viewer_is_limited_to_approved_version_but_editor_can_read_current(tmp_path):
    repository = FakeRepository(approved_version=1, current_version=2)
    service, _ = create_service(tmp_path, repository)

    with pytest.raises(ResourceQaError) as hidden:
        await service.get_session(
            course_id="course-1", resource_kind="study_guide", resource_id="guide-1",
            resource_version=2, owner_user_id="student-a", course_role="viewer",
        )
    assert hidden.value.status_code == 404

    session = await service.get_session(
        course_id="course-1", resource_kind="study_guide", resource_id="guide-1",
        resource_version=2, owner_user_id="teacher-a", course_role="editor",
    )
    assert session["resource_version"] == 2


async def test_versions_and_resource_kinds_have_distinct_sessions(tmp_path):
    repository = FakeRepository(approved_version=2, current_version=2)
    service, _ = create_service(tmp_path, repository)
    first = await service.get_session(
        course_id="course-1", resource_kind="study_guide", resource_id="guide-1",
        resource_version=1, owner_user_id="teacher-a", course_role="owner",
    )
    second = await service.get_session(
        course_id="course-1", resource_kind="study_guide", resource_id="guide-1",
        resource_version=2, owner_user_id="teacher-a", course_role="owner",
    )
    assert first["session_id"] != second["session_id"]
    assert resource_session_id(resource_kind="study_guide", resource_id="guide-1", resource_version=1) != resource_session_id(
        resource_kind="study_guide", resource_id="guide-1", resource_version=2
    )


async def test_student_practice_messages_never_contain_answers(tmp_path):
    repository = FakeRepository(kind="practice", approved_version=1, current_version=1)
    service, gateway = create_service(tmp_path, repository)
    await service.submit_turn(
        course_id="course-1", resource_kind="practice", resource_id="quiz-1",
        resource_version=1, owner_user_id="student-a", course_role="viewer", request=request(version=1),
    )
    rendered = json.dumps(gateway.messages, ensure_ascii=False)
    assert "correct_answer" not in rendered
    assert "相加" not in rendered
    assert "标准答案" not in rendered
