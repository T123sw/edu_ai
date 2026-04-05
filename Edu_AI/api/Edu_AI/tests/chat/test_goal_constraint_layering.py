from types import SimpleNamespace

from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor


def _request(question: str):
    return SimpleNamespace(
        question=question,
        course_id="course-1",
        capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
    )


def test_extractor_separates_explicit_user_goal_from_derived_workflow_goal():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("帮我分析一下这节课为什么前10分钟学生总是走神"),
        result={
            "message": {"content": "前10分钟走神通常和开场吸引力不足有关。"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "running"},
        },
        existing_state={"conversation_memory": {"explicit_user_goals": ["继续对话"]}},
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert memory["explicit_user_goals"][0] == "分析问题"
    assert memory["derived_workflow_goal"] == "生成报告"
    assert memory["user_goals"][0] == "生成报告"
    assert "分析问题" in memory["user_goals"]


def test_extractor_separates_explicit_constraints_from_derived_constraints():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("请面向教研组，用正式一点的语气，控制在800字，按提纲形式输出"),
        result={
            "message": {"content": "我先按你的要求整理约束。"},
            "action": {"name": "chat.reply"},
        },
        existing_state={},
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert memory["explicit_user_constraints"]["audience"] == "教研组"
    assert memory["explicit_user_constraints"]["tone"] == "正式"
    assert memory["explicit_user_constraints"]["length"] == "800字"
    assert "提纲形式输出" in memory["explicit_user_constraints"]["extra_constraints"]
    assert memory["derived_workflow_constraints"]["course_id"] == "course-1"
    assert memory["constraints"]["course_id"] == "course-1"
    assert memory["constraints"]["audience"] == "教研组"
