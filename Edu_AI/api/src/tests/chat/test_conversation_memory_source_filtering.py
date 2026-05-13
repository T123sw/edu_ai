from types import SimpleNamespace

from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor


def _request(question: str):
    return SimpleNamespace(
        question=question,
        course_id="course-1",
        capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
    )


def test_report_control_turn_does_not_pollute_topics_summary_or_facts():
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
            "conversation_summary": {"summary_text": "当前围绕介绍下水淹七军、介绍下关羽的战绩继续对话"},
            "conversation_memory": {
                "current_topics": ["介绍下水淹七军", "介绍下关羽的战绩"],
                "confirmed_facts": ["水淹七军是关羽军事生涯的巅峰战役"],
                "teaching_issues": ["于禁七军陷入混乱"],
                "student_signals": [],
                "evidence_points": [{"type": "observation", "content": "关羽提前准备水军"}],
                "constraints": {"course_id": "course-1", "extra_constraints": []},
                "user_goals": ["继续对话"],
            },
        },
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert memory["current_topics"][:2] == ["介绍下水淹七军", "介绍下关羽的战绩"]
    assert "请基于当前内容生成一份报告" not in memory["current_topics"]
    assert patch["conversation_summary"]["summary_text"] == "当前围绕介绍下水淹七军、介绍下关羽的战绩继续对话"
    assert all("生成一版报告" not in item for item in memory["confirmed_facts"])


def test_outline_control_turn_does_not_generate_new_facts_or_evidence():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("根据已确认的大纲开始生成报告"),
        result={
            "message": {"content": "大纲已生成，请确认或指出要修改的地方：\n- 战役背景\n- 战役过程\n- 战役影响"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "outlining"},
        },
        existing_state={
            "conversation_summary": {"summary_text": "当前围绕介绍下水淹七军继续对话"},
            "conversation_memory": {
                "current_topics": ["介绍下水淹七军"],
                "confirmed_facts": ["关羽利用洪水击败于禁七军"],
                "teaching_issues": [],
                "student_signals": [],
                "evidence_points": [{"type": "observation", "content": "汉水暴涨数丈"}],
                "constraints": {"course_id": "course-1", "extra_constraints": []},
                "user_goals": ["生成报告"],
            },
        },
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert memory["confirmed_facts"] == ["关羽利用洪水击败于禁七军"]
    assert [item["content"] for item in memory["evidence_points"]] == ["汉水暴涨数丈"]


def test_assistant_meta_openers_do_not_enter_fact_or_issue_memory():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("skills怎么使用"),
        result={
            "message": {
                "content": "这是一个非常好的问题。使用 AI 的 Skills，本质上就是通过特定的方式与 AI 模型交互，以激发和利用其内置的能力。"
            },
            "action": {"name": "chat.reply"},
        },
        existing_state={},
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert all("这是一个非常好的问题" not in item for item in memory["confirmed_facts"])
    assert all("这是一个非常好的问题" not in item for item in memory["teaching_issues"])
