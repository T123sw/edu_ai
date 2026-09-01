from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.workflows.report.runtime import ReportWorkflowRuntime


def test_report_runtime_passes_snapshot_and_capability_context_to_engine():
    seen = {}

    class InspectingEngine:
        def invoke(self, state):
            seen.update(state)
            return {"reply": "ok", "status": "running"}

    runtime = ReportWorkflowRuntime(engine=InspectingEngine())
    snapshot = ConversationSnapshot(
        conversation_id="conv-ctx",
        recent_messages=[{"role": "user", "content": "prior context"}],
        summary="summary-text",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_goals": ["生成报告"],
            "confirmed_facts": ["前10分钟学生分心明显"],
            "constraints": {"audience": "教研组", "style_notes": []},
            "teaching_issues": ["开场吸引力不足"],
            "student_signals": ["前10分钟注意力分散"],
            "evidence_points": [{"type": "observation", "content": "前10分钟学生分心明显"}],
        },
        active_context={
            "current_course_id": "course-1",
            "active_artifact_id": "artifact-2",
            "active_artifact_type": "report_outline",
            "pinned_doc_ids": ["doc-1"],
        },
        referenced_artifact_ids=["artifact-1"],
    )

    runtime.run(
        request=ChatRequestV2(
            question="generate report",
            conversation_id="conv-ctx",
            owner="teacher-a",
            capability={
                "allow_rag": True,
                "allow_web": False,
                "allow_tools": True,
                "selected_doc_ids": ["doc-1"],
            },
        ),
        snapshot=snapshot,
        decision=None,
    )

    assert seen["conversation_id"] == "conv-ctx"
    assert seen["owner"] == "teacher-a"
    assert seen["allow_rag"] is True
    assert seen["allow_web"] is False
    assert seen["selected_doc_ids"] == ["doc-1"]
    assert seen["gathered_context"]["summary"] == "summary-text"
    assert seen["gathered_context"]["recent_messages"][-1]["content"] == "prior context"
    assert seen["gathered_context"]["confirmed_facts"] == ["前10分钟学生分心明显"]
    assert seen["gathered_context"]["teaching_issues"] == ["开场吸引力不足"]
    assert seen["gathered_context"]["source_scope"]["from_memory"] is True
