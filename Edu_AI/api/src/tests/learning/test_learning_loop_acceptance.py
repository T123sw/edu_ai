from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.chat.domain.contracts import ChatRequestV2
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.runtime.fast_chat_runtime import FastChatRuntime
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
        return "继续保持，你已经完成了当前任务。"


def test_teacher_student_learning_loop_reaches_a_new_agent_conversation(tmp_path):
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

    request = ChatRequestV2(
        question="我完成了吗？",
        actor_role="student",
        owner="student-1",
        course_id="course-1",
        conversation_id=None,
    )
    snapshot = ContextBuilder(
        conversation_store=SimpleNamespace(),
        learning_context_reader=LearningContextReader(service),
    ).build(request)
    gateway = CaptureGateway()
    FastChatRuntime(model_gateway=gateway).run(
        request=request,
        snapshot=snapshot,
        decision=None,
    )
    system_prompt = gateway.messages[0]["content"]

    assert "【当前学习状态】" in system_prompt
    assert "完成快速排序学习" in system_prompt
    assert '"status":"completed"' in system_prompt
