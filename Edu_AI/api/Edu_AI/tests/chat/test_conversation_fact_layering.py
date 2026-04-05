from types import SimpleNamespace

from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor


def _request(question: str):
    return SimpleNamespace(
        question=question,
        course_id="course-1",
        capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
    )


def test_extractor_separates_user_stated_facts_from_assistant_fact_candidates():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("这节课前10分钟学生多次走神，后排回应也比较少"),
        result={
            "message": {
                "content": "这说明前10分钟课堂启动较慢，开场吸引力不足，导致后排学生参与偏低。"
            },
            "action": {"name": "chat.reply"},
        },
        existing_state={},
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert memory["user_stated_facts"] == ["这节课前10分钟学生多次走神", "后排回应也比较少"]
    assert memory["assistant_fact_candidates"]
    assert memory["assistant_fact_candidates"] != memory["confirmed_facts"]
    assert memory["confirmed_facts"] == ["这节课前10分钟学生多次走神", "后排回应也比较少"]


def test_report_control_turn_does_not_add_assistant_fact_candidates_to_confirmed_facts():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("请基于当前内容生成一份报告"),
        result={
            "message": {
                "content": "我将基于“关羽水淹七军战役”，重点围绕“战役全过程分析”，结合当前对话内容先生成一版报告。可以直接开始吗？"
            },
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "soft_confirm"},
        },
        existing_state={
            "conversation_memory": {
                "confirmed_facts": ["水淹七军是关羽军事生涯的巅峰战役"],
            }
        },
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert memory["assistant_fact_candidates"] == []
    assert memory["confirmed_facts"] == ["水淹七军是关羽军事生涯的巅峰战役"]
