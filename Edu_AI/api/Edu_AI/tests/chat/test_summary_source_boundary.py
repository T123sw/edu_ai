from types import SimpleNamespace

from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor


def _request(question: str):
    return SimpleNamespace(
        question=question,
        course_id="course-1",
        capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
    )


def test_control_turn_does_not_backfill_facts_from_existing_summary():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("确认并继续"),
        result={
            "message": {"content": "我将基于当前内容继续生成报告。"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "soft_confirm"},
        },
        existing_state={
            "conversation_summary": {"summary_text": "前10分钟学生多次走神，后排回应也比较少"},
            "conversation_memory": {},
        },
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert memory["user_stated_facts"] == []
    assert memory["confirmed_facts"] == []
    assert patch["conversation_summary"]["summary_text"] == "前10分钟学生多次走神，后排回应也比较少"
