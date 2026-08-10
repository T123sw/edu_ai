from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.contracts import ChatRequestV2
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.runtime.fast_chat_runtime import FastChatRuntime
from app.chat.runtime.react_agent import ReActAgent
from app.learning.context_reader import LearningContextReader
from app.learning.service import LearningService
from app.learning.store import LearningStore


@dataclass(frozen=True)
class Membership:
    user_id: str
    role: str


class CaptureGateway:
    def __init__(self):
        self.messages = []

    def chat(self, messages):
        self.messages = messages
        return "ok"


def _reader(tmp_path):
    memberships = [
        Membership("teacher-1", "owner"),
        Membership("student-1", "viewer"),
        Membership("student-2", "viewer"),
    ]
    service = LearningService(
        store=LearningStore(tmp_path / "learning.db"),
        material_lookup=lambda *args: None,
        membership_lookup=lambda course_id: memberships if course_id == "course-1" else [],
    )
    task = service.create_task(
        course_id="course-1",
        teacher_id="teacher-1",
        title="学习快速排序",
        instructions="阅读后完成",
        resource_refs=[],
        knowledge_point_ids=["quick-sort"],
    )
    service.publish_task(course_id="course-1", task_id=task.task_id, teacher_id="teacher-1")
    service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-2",
        event_id="evt-student-2",
        event_type="completed",
        progress_percent=100,
        resource_ref=None,
    )
    return LearningContextReader(service)


def test_student_context_contains_only_own_learning_state(tmp_path):
    context = _reader(tmp_path).read(
        user_id="student-1",
        course_id="course-1",
        actor_role="student",
    )

    assert context["projection"] == "student"
    assert context["overview"]["course_id"] == "course-1"
    assert context["as_of"]
    assert {"completion_basis", "last_activity_at", "knowledge_point_ids"}.issubset(
        context["pending_tasks"][0]
    )
    assert context["pending_tasks"][0]["title"] == "学习快速排序"
    assert "student-2" not in json.dumps(context, ensure_ascii=False)


def test_teacher_context_contains_aggregate_not_private_conversations(tmp_path):
    context = _reader(tmp_path).read(
        user_id="teacher-1",
        course_id="course-1",
        actor_role="teacher",
    )

    assert context["projection"] == "teacher"
    assert context["overview"]["enrolled_students"] == 2
    assert context["overview"]["self_reported_students"] == 1
    assert context["as_of"]
    assert context["task_summaries"][0]["completed_students"] == 1
    serialized = json.dumps(context, ensure_ascii=False)
    assert "conversation" not in serialized
    assert "student-2" not in serialized


def test_context_builder_loads_learning_context_without_existing_conversation(tmp_path):
    reader = _reader(tmp_path)
    request = ChatRequestV2(
        question="我接下来学什么？",
        actor_role="student",
        owner="student-1",
        course_id="course-1",
    )

    snapshot = ContextBuilder(
        conversation_store=SimpleNamespace(),
        learning_context_reader=reader,
    ).build(request)

    assert snapshot.learning_context["projection"] == "student"


def test_fast_and_react_prompts_receive_role_scoped_learning_context(tmp_path):
    context = _reader(tmp_path).read(
        user_id="student-1",
        course_id="course-1",
        actor_role="student",
    )
    snapshot = SimpleNamespace(
        recent_messages=[],
        active_artifact=None,
        capability=CapabilityPolicy(),
        learning_context=context,
    )
    request = ChatRequestV2(
        question="我接下来学什么？",
        actor_role="student",
        owner="student-1",
        course_id="course-1",
    )
    gateway = CaptureGateway()
    runtime = FastChatRuntime(model_gateway=gateway)
    runtime.run(request=request, snapshot=snapshot, decision=None)
    fast_system = gateway.messages[0]["content"]

    agent = ReActAgent(
        agent_gateway=gateway,
        fast_runtime=runtime,
        agent_run_store=SimpleNamespace(),
    )
    react_messages = agent._build_messages(request, snapshot)
    react_system = "\n".join(
        item["content"] for item in react_messages if item["role"] == "system"
    )

    assert "【当前学习状态】" in fast_system
    assert "【当前学习状态】" in react_system
    assert "学习快速排序" in fast_system
    assert "student-2" not in fast_system
    assert "student-2" not in react_system
