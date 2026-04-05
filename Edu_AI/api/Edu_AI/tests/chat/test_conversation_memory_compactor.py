from types import SimpleNamespace

from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor


def _request(question: str):
    return SimpleNamespace(
        question=question,
        course_id="course-1",
        capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
    )


def test_compactor_runs_on_fourth_turn_and_cleans_workflow_residue():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("继续分析水淹七军的战术过程"),
        result={
            "message": {"content": "关羽提前准备水军并利用洪水时机。"},
            "action": {"name": "chat.reply"},
        },
        existing_state={
            "conversation_summary": {"summary_text": "当前围绕水淹七军继续对话"},
            "conversation_memory": {
                "current_topics": ["请基于当前内容生成一份报告", "确认并继续", "介绍下水淹七军"],
                "user_goals": ["生成报告", "继续对话"],
            },
            "conversation_memory_meta": {
                "turn_count": 3,
                "last_compacted_turn": 0,
                "compaction_count": 0,
            },
        },
        recent_messages=[],
    )

    assert patch["conversation_memory_meta"]["turn_count"] == 4
    assert patch["conversation_memory_meta"]["compaction_count"] == 1
    assert patch["conversation_memory_meta"]["last_compacted_turn"] == 4
    assert "请基于当前内容生成一份报告" not in patch["conversation_memory"]["current_topics"]
    assert "确认并继续" not in patch["conversation_memory"]["current_topics"]


def test_compactor_drops_stale_continue_chat_goal_on_report_turn():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("请基于当前内容生成一份报告"),
        result={
            "message": {"content": "我将基于当前内容先生成一版报告。"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "soft_confirm"},
        },
        existing_state={
            "conversation_memory": {
                "current_topics": ["介绍下水淹七军"],
                "user_goals": ["继续对话"],
            },
            "conversation_memory_meta": {
                "turn_count": 1,
                "last_compacted_turn": 0,
                "compaction_count": 0,
            },
        },
        recent_messages=[],
    )

    assert patch["conversation_memory_meta"]["compaction_count"] == 1
    assert patch["conversation_memory"]["user_goals"][0] == "生成报告"
    assert "继续对话" not in patch["conversation_memory"]["user_goals"]
