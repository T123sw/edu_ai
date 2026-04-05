from types import SimpleNamespace

from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor


def test_memory_extractor_extracts_student_signals_and_evidence_points():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=SimpleNamespace(
            question="请分析高一物理课堂前10分钟参与度低、后排学生容易分心的问题，面向教研组，正式一点，并突出课堂观察证据",
            course_id="course-1",
            capability=SimpleNamespace(selected_doc_ids=["doc-1"], allow_rag=True, allow_web=False),
        ),
        result={
            "message": {
                "content": "课堂前10分钟举手响应较少，后排学生多次走神，说明注意力维持不足。教师提问后的等待时间偏短，互动没有形成持续推进。"
            },
            "action": {"name": "chat.reply"},
        },
        existing_state={},
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert any("前10分钟" in item for item in memory["student_signals"])
    assert any("后排学生" in item for item in memory["student_signals"])
    assert memory["evidence_points"]
    assert any("举手响应较少" in item["content"] for item in memory["evidence_points"])
    assert all(item["type"] == "observation" for item in memory["evidence_points"])


def test_memory_extractor_merges_new_goal_and_extra_constraints_without_losing_existing_state():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=SimpleNamespace(
            question="请帮我生成报告，按提纲形式输出，并加入可执行建议",
            course_id=None,
            capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
        ),
        result={
            "message": {
                "content": "我会先整理一版报告提纲，再补充可执行建议。"
            },
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "running"},
        },
        existing_state={
            "conversation_summary": {"summary_text": "之前在分析课堂问题"},
            "conversation_memory": {
                "current_topics": ["课堂参与度"],
                "user_goals": ["分析问题", "继续对话"],
                "constraints": {
                    "audience": "教研组",
                    "extra_constraints": ["保留案例"],
                },
                "student_signals": ["学生回应偏少"],
                "evidence_points": [{"type": "observation", "content": "学生回应偏少"}],
            },
        },
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert memory["user_goals"][0] == "生成报告"
    assert "分析问题" in memory["user_goals"]
    assert "保留案例" in memory["constraints"]["extra_constraints"]
    assert "提纲形式输出" in memory["constraints"]["extra_constraints"]
    assert "加入可执行建议" in memory["constraints"]["extra_constraints"]
