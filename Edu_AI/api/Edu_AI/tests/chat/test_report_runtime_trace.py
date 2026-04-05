from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.workflows.report import runtime as runtime_module
from app.chat.workflows.report.runtime import ReportWorkflowRuntime


def test_report_runtime_traces_injected_context_when_trace_enabled(capsys, monkeypatch):
    class InspectingEngine:
        def invoke(self, state):
            return {"reply": "ok", "status": "running"}

    monkeypatch.setattr(runtime_module, "_TRACE_ENABLED", True)

    runtime = ReportWorkflowRuntime(engine=InspectingEngine())
    snapshot = ConversationSnapshot(
        conversation_id="conv-trace",
        recent_messages=[
            {"role": "user", "content": "我想分析关羽北伐失败中军资供应问题如何引发内部失和。"},
            {"role": "assistant", "content": "我先帮你梳理军资问题与内部失和的关系。"},
        ],
        summary="当前围绕关羽北伐失败中军资问题与内部失和展开分析。",
        conversation_memory={
            "current_topics": ["关羽北伐失败中的军资问题"],
            "user_goals": ["生成报告"],
            "confirmed_facts": ["军资问题与内部失和相互影响"],
            "constraints": {"audience": "教研组", "length": "800字左右"},
            "teaching_issues": ["军资供应问题如何引发内部失和"],
            "student_signals": ["学生容易把军资问题和战略失误混为一谈"],
            "evidence_points": [{"type": "observation", "content": "学生常把军资问题简单归因于粮草不足"}],
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
            question="请基于当前内容生成一份报告",
            conversation_id="conv-trace",
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

    output = capsys.readouterr().out

    assert "[报告工作流] report_context_injection" in output
    assert '"slot_hints"' in output
    assert '"constraints"' in output
    assert '"current_topics"' in output
    assert '"recent_message_preview"' in output
    assert "关羽北伐失败中的军资问题" in output
