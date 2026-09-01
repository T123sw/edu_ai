from pathlib import Path
from types import SimpleNamespace
import uuid

from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor
from core.conversation_storage import ConversationStorage


def test_conversation_storage_appends_messages_with_message_id():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-msg-id", "hello")

    storage.append_message("conv-msg-id", "user", "hello")
    messages = storage.get_messages("conv-msg-id")

    assert messages
    assert messages[0]["message_id"]


def test_extractor_adds_evidence_source_metadata_from_recent_messages():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=SimpleNamespace(
            question="请分析这节课的课堂观察证据",
            course_id=None,
            capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
        ),
        result={
            "message": {
                "content": "课堂前10分钟举手响应较少，后排学生多次走神，说明注意力维持不足。"
            },
            "action": {"name": "chat.reply"},
        },
        existing_state={},
        recent_messages=[
            {"message_id": "msg-user-1", "role": "user", "content": "请分析这节课的课堂观察证据"},
            {"message_id": "msg-assistant-1", "role": "assistant", "content": "课堂前10分钟举手响应较少，后排学生多次走神，说明注意力维持不足。"},
        ],
    )

    evidence = patch["conversation_memory"]["evidence_points"][0]

    assert evidence["source_type"] == "assistant_message"
    assert evidence["source_message_ids"] == ["msg-assistant-1"]
    assert evidence["confidence"] == "low"


def test_extractor_merges_repeated_evidence_and_upgrades_confidence():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=SimpleNamespace(
            question="继续分析课堂观察证据",
            course_id=None,
            capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
        ),
        result={
            "message": {
                "content": "课堂前10分钟举手响应较少，说明学生进入状态偏慢。"
            },
            "action": {"name": "chat.reply"},
        },
        existing_state={
            "conversation_memory": {
                "evidence_points": [
                    {
                        "type": "observation",
                        "content": "课堂前10分钟举手响应较少",
                        "source_type": "assistant_message",
                        "source_message_ids": ["msg-assistant-1"],
                        "confidence": "low",
                    }
                ]
            }
        },
        recent_messages=[
            {"message_id": "msg-user-2", "role": "user", "content": "继续分析课堂观察证据"},
            {"message_id": "msg-assistant-2", "role": "assistant", "content": "课堂前10分钟举手响应较少，说明学生进入状态偏慢。"},
        ],
    )

    evidence = patch["conversation_memory"]["evidence_points"][0]

    assert evidence["content"] == "课堂前10分钟举手响应较少"
    assert evidence["source_message_ids"] == ["msg-assistant-1", "msg-assistant-2"]
    assert evidence["confidence"] == "medium"
