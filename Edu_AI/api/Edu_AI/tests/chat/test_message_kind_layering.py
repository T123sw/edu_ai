from pathlib import Path
import uuid
from types import SimpleNamespace

from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from core.conversation_storage import ConversationStorage


def _request(question: str):
    return SimpleNamespace(
        question=question,
        owner="teacher-a",
        course_id="course-1",
        capability=SimpleNamespace(allow_rag=False, allow_web=False, selected_doc_ids=[]),
    )


def test_write_v2_result_tags_workflow_control_messages():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)

    adapter.write_v2_result(
        "conv-msg-kind-control",
        _request("请基于当前内容生成一份报告"),
        {
            "message": {"content": "我将基于当前对话内容先生成一版报告。可以直接开始吗？"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "soft_confirm"},
        },
    )

    messages = storage.get_messages("conv-msg-kind-control")

    assert messages[0]["message_kind"] == "workflow_control"
    assert messages[1]["message_kind"] == "workflow_control"


def test_write_v2_result_tags_normal_chat_messages_as_content():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)

    adapter.write_v2_result(
        "conv-msg-kind-chat",
        _request("介绍下水淹七军"),
        {
            "message": {"content": "水淹七军是关羽北伐中的关键战役。"},
            "action": {"name": "chat.reply"},
        },
    )

    messages = storage.get_messages("conv-msg-kind-chat")

    assert messages[0]["message_kind"] == "user_content"
    assert messages[1]["message_kind"] == "assistant_content"
