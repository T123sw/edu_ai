from pathlib import Path
from types import SimpleNamespace
import uuid

from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from core.conversation_storage import ConversationStorage


def test_pipeline_does_not_persist_report_control_phrase_as_topic():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-source-filter", "介绍下水淹七军")
    storage.update_state(
        "conv-source-filter",
        {
            "conversation_summary": {"summary_text": "当前围绕介绍下水淹七军继续对话"},
            "conversation_memory": {
                "current_topics": ["介绍下水淹七军"],
                "user_goals": ["继续对话"],
                "constraints": {"course_id": "course-1", "extra_constraints": []},
                "confirmed_facts": ["关羽利用洪水击败于禁七军"],
                "teaching_issues": [],
                "student_signals": [],
                "evidence_points": [],
            },
        },
    )
    adapter = ConversationStoreAdapter(storage=storage)

    request = SimpleNamespace(
        question="请基于当前内容生成一份报告",
        course_id="course-1",
        owner="teacher-a",
        capability=SimpleNamespace(allow_rag=False, allow_web=False, selected_doc_ids=[]),
    )

    adapter.write_v2_result(
        "conv-source-filter",
        request,
        {
            "message": {
                "role": "assistant",
                "content": "我将基于“关羽水淹七军战役”，重点围绕“战役全过程分析”，结合当前对话内容先生成一版报告。可以直接开始吗？",
            },
            "conversation": {"conversation_id": "conv-source-filter"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "soft_confirm"},
            "artifacts": [],
            "sources": [],
            "trace": {},
        },
    )

    state = storage.get_state("conv-source-filter")
    memory = state["conversation_memory"]

    assert memory["user_goals"][0] == "生成报告"
    assert "请基于当前内容生成一份报告" not in memory["current_topics"]
    assert state["conversation_summary"]["summary_text"] == "当前围绕介绍下水淹七军继续对话"
