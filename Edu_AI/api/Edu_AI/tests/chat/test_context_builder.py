from pathlib import Path
import uuid

from app.chat.domain.contracts import ChatRequestV2
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from core.conversation_storage import ConversationStorage


class DummyMemoryReader:
    def read(self, *, user_id: str, conversation_id: str | None):
        return {"summary": f"memory:{user_id}:{conversation_id}"}


def test_context_builder_uses_conversation_and_memory():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-ctx", "你好")
    storage.append_message("conv-ctx", "user", "上节课我们讲了牛顿第二定律")
    storage.update_state(
        "conv-ctx",
        {
            "workflow_state": {
                "workflow_id": "wf-1",
                "workflow_type": "report",
                "status": "running",
                "stage": "collecting",
            }
        },
    )
    adapter = ConversationStoreAdapter(storage=storage)
    builder = ContextBuilder(conversation_store=adapter, memory_reader=DummyMemoryReader())

    snapshot = builder.build(ChatRequestV2(question="继续", conversation_id="conv-ctx", owner="teacher-a"))

    assert snapshot.recent_messages[-1]["content"] == "上节课我们讲了牛顿第二定律"
    assert snapshot.conversation_id == "conv-ctx"
    assert snapshot.summary == "memory:teacher-a:conv-ctx"
    assert snapshot.workflow_state.workflow_type == "report"


def test_context_builder_exposes_active_task_and_artifact():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-active", "你好")
    storage.update_state(
        "conv-active",
        {
            "active_task": "chat.rewrite",
            "active_artifact": {
                "artifact_id": "artifact-1",
                "artifact_type": "report",
                "title": "课堂总结",
            },
        },
    )
    adapter = ConversationStoreAdapter(storage=storage)
    builder = ContextBuilder(conversation_store=adapter, memory_reader=None)

    snapshot = builder.build(ChatRequestV2(question="再正式一点", conversation_id="conv-active", owner="teacher-a"))

    assert snapshot.active_task == "chat.rewrite"
    assert snapshot.active_artifact is not None
    assert snapshot.active_artifact.artifact_id == "artifact-1"


def test_context_builder_preserves_request_capability():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-cap", "hello")
    adapter = ConversationStoreAdapter(storage=storage)
    builder = ContextBuilder(conversation_store=adapter, memory_reader=None)

    snapshot = builder.build(
        ChatRequestV2(
            question="hello",
            conversation_id="conv-cap",
            owner="teacher-a",
            capability={
                "allow_rag": True,
                "allow_web": False,
                "allow_tools": True,
                "selected_doc_ids": ["doc-1"],
            },
        )
    )

    assert snapshot.capability.allow_rag is True
    assert snapshot.capability.allow_web is False
    assert snapshot.capability.selected_doc_ids == ["doc-1"]


def test_context_builder_exposes_structured_report_context_fields():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-structured", "生成报告")
    storage.update_state(
        "conv-structured",
        {
            "conversation_summary": {"summary_text": "课堂问题集中在参与度"},
            "conversation_memory": {
                "current_topics": ["课堂参与度"],
                "confirmed_facts": ["前10分钟学生分心明显"],
                "constraints": {"audience": "教研组", "style_notes": []},
                "teaching_issues": ["开场吸引力不足"],
                "evidence_points": [
                    {"type": "observation", "content": "前10分钟学生分心明显"}
                ],
                "referenced_artifact_ids": ["artifact-1"],
            },
            "active_context": {
                "current_course_id": "course-1",
                "active_artifact_id": "artifact-2",
                "active_artifact_type": "report_outline",
                "pinned_doc_ids": ["doc-1"],
            },
        },
    )
    adapter = ConversationStoreAdapter(storage=storage)
    builder = ContextBuilder(conversation_store=adapter, memory_reader=None)

    snapshot = builder.build(
        ChatRequestV2(
            question="生成报告",
            conversation_id="conv-structured",
            owner="teacher-a",
        )
    )

    assert snapshot.summary == "课堂问题集中在参与度"
    assert snapshot.conversation_memory["current_topics"] == ["课堂参与度"]
    assert snapshot.active_context["current_course_id"] == "course-1"
    assert snapshot.referenced_artifact_ids == ["artifact-1"]
