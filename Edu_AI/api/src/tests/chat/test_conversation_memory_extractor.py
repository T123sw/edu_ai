from types import SimpleNamespace

from app.chat.orchestrator.conversation_memory_extractor import ConversationMemoryExtractor


def test_memory_extractor_builds_summary_topics_and_goal_for_general_chat():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=SimpleNamespace(
            question="请分析关羽水淹七军为什么能赢",
            course_id=None,
            capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
        ),
        result={
            "message": {
                "content": "关羽取胜的关键在于汉中大战后的战略窗口、荆州水军优势，以及对禁援军被洪水打散后的快速歼灭。"
            },
            "action": {"name": "chat.reply"},
        },
        existing_state={},
        recent_messages=[],
    )

    assert "关羽水淹七军为什么能赢" in patch["conversation_memory"]["current_topics"][0]
    assert patch["conversation_memory"]["user_goals"][0] == "分析问题"
    assert "关羽水淹七军为什么能赢" in patch["conversation_summary"]["summary_text"]
    assert patch["conversation_memory"]["confirmed_facts"]


def test_memory_extractor_extracts_teaching_issue_and_constraints():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=SimpleNamespace(
            question="请帮我分析高一物理课堂学生参与度低的问题，面向教研组，正式一些，控制在800字左右",
            course_id="course-1",
            capability=SimpleNamespace(selected_doc_ids=["doc-1"], allow_rag=True, allow_web=False),
        ),
        result={
            "message": {
                "content": "这节课的主要问题是学生参与度低，开场吸引不足，互动提问没有形成持续推进。"
            },
            "action": {"name": "chat.reply"},
        },
        existing_state={},
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert memory["user_goals"][0] == "分析问题"
    assert memory["constraints"]["audience"] == "教研组"
    assert memory["constraints"]["tone"] == "正式"
    assert memory["constraints"]["length"] == "800字"
    assert memory["constraints"]["grade_level"] == "高一"
    assert memory["constraints"]["subject"] == "物理"
    assert any("参与度低" in item for item in memory["teaching_issues"])
    assert memory["current_topics"]
