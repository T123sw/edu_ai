from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.workflows.report.runtime import ReportWorkflowRuntime


def _ready_snapshot():
    return ConversationSnapshot(
        conversation_id="conv-ready",
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


class DummyEngine:
    def invoke(self, state):
        return {
            "reply": "这是报告草稿",
            "status": "awaiting_confirm",
            "artifacts": [{"artifact_id": "report-1", "artifact_type": "report"}],
            "sources": [],
        }


def test_report_runtime_wraps_engine_result():
    runtime = ReportWorkflowRuntime(engine=DummyEngine())

    result = runtime.run(
        request=ChatRequestV2(question="生成报告", action_hint="generate.report"),
        snapshot=_ready_snapshot(),
        decision=None,
    )

    assert result["workflow"]["type"] == "report"
    assert result["workflow"]["status"] == "awaiting_confirm"
    assert result["action"]["name"] == "generate.report"


class DummyStateEngine:
    def invoke(self, state):
        return {
            "final_response": "请确认这个报告大纲",
            "status": "awaiting_human",
            "phase": "confirming",
            "report_outline": [{"title": "一、背景"}],
            "report_content": "",
            "report_slots": {"core_topic": "课堂管理"},
        }


def test_report_runtime_adapts_universal_engine_state_shape():
    runtime = ReportWorkflowRuntime(engine=DummyStateEngine())

    result = runtime.run(
        request=ChatRequestV2(question="生成报告", action_hint="generate.report"),
        snapshot=_ready_snapshot(),
        decision=None,
    )

    assert result["message"]["content"] == "请确认这个报告大纲"
    assert result["workflow"]["status"] == "awaiting_confirm"
    assert result["workflow"]["phase"] == "confirming"
    assert result["artifacts"]


def test_report_runtime_can_resolve_engine_per_request():
    seen = {}

    class DynamicEngine:
        def invoke(self, state):
            return {"reply": "dynamic", "status": "running"}

    def resolver(*, request, snapshot, decision):
        seen["question"] = request.question
        return DynamicEngine()

    runtime = ReportWorkflowRuntime(engine_resolver=resolver)

    result = runtime.run(
        request=ChatRequestV2(question="生成报告", action_hint="generate.report"),
        snapshot=_ready_snapshot(),
        decision=None,
    )

    assert seen["question"] == "生成报告"
    assert result["message"]["content"] == "dynamic"
