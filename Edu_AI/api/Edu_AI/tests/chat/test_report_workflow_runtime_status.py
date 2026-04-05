from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.workflows.report.runtime import ReportWorkflowRuntime


def _ready_snapshot():
    return ConversationSnapshot(
        conversation_id="conv-status",
        recent_messages=[{"role": "user", "content": "请基于课堂参与度问题生成报告"}],
        summary="当前围绕课堂参与度问题展开分析。",
        conversation_memory={
            "current_topics": ["课堂参与度问题"],
            "user_goals": ["生成报告"],
            "confirmed_facts": ["前10分钟学生注意力分散"],
            "constraints": {"audience": "教研组"},
            "teaching_issues": ["开场吸引力不足"],
            "student_signals": ["前10分钟注意力分散"],
            "evidence_points": [{"type": "observation", "content": "前10分钟学生注意力分散"}],
        },
        active_context={},
        referenced_artifact_ids=[],
    )


def test_report_runtime_normalizes_awaiting_human_to_awaiting_confirm():
    class AwaitingHumanEngine:
        def invoke(self, state):
            return {"final_response": "please confirm", "status": "awaiting_human"}

    runtime = ReportWorkflowRuntime(engine=AwaitingHumanEngine())

    result = runtime.run(
        request=ChatRequestV2(question="generate report", action_hint="generate.report"),
        snapshot=_ready_snapshot(),
        decision=None,
    )

    assert result["workflow"]["status"] == "awaiting_confirm"


def test_report_runtime_normalizes_finished_to_completed():
    class FinishedEngine:
        def invoke(self, state):
            return {"report_content": "done", "status": "finished"}

    runtime = ReportWorkflowRuntime(engine=FinishedEngine())

    result = runtime.run(
        request=ChatRequestV2(question="generate report", action_hint="generate.report"),
        snapshot=_ready_snapshot(),
        decision=None,
    )

    assert result["workflow"]["status"] == "completed"
