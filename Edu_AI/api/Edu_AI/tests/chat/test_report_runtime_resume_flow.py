from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.workflows.report.runtime import ReportWorkflowRuntime


def test_runtime_resumes_generation_after_soft_confirm_reply():
    called = {"engine": False, "state": None}

    class DummyEngine:
        def invoke(self, state):
            called["engine"] = True
            called["state"] = state
            return {"reply": "报告大纲已生成", "status": "running", "phase": "outlining"}

    runtime = ReportWorkflowRuntime(engine=DummyEngine())

    snapshot = ConversationSnapshot(
        conversation_id="conv-3",
        workflow_state={
            "workflow_id": "conv-3",
            "workflow_type": "report",
            "status": "awaiting_confirm",
            "stage": "soft_confirm",
            "required_slots": [],
            "filled_slots": {
                "core_topic": "Skills 怎么使用",
                "focus_area": "与 MCP 的差异和使用方式",
                "__preparation_source": "llm_structured_output",
            },
            "artifacts": [],
        },
    )

    result = runtime.run(
        request=ChatRequestV2(question="可以", conversation_id="conv-3"),
        snapshot=snapshot,
        decision=None,
    )

    assert called["engine"] is True
    assert called["state"]["generation_ready"] is True
    assert called["state"]["soft_confirmed"] is True
    assert called["state"]["report_slots"]["core_topic"] == "Skills 怎么使用"
    assert called["state"]["report_slots"]["focus_area"] == "与 MCP 的差异和使用方式"
    assert called["state"]["report_preparation_result"]["preparation_source"] == "llm_structured_output"
    assert result["message"]["content"] == "报告大纲已生成"


def test_runtime_resumes_generation_after_critical_gap_confirmation_when_slots_exist():
    called = {"engine": False, "state": None}

    class DummyEngine:
        def invoke(self, state):
            called["engine"] = True
            called["state"] = state
            return {"reply": "报告大纲已生成", "status": "running", "phase": "outlining"}

    runtime = ReportWorkflowRuntime(engine=DummyEngine())

    snapshot = ConversationSnapshot(
        conversation_id="conv-4",
        workflow_state={
            "workflow_id": "conv-4",
            "workflow_type": "report",
            "status": "awaiting_confirm",
            "stage": "critical_gap",
            "required_slots": [],
            "filled_slots": {
                "core_topic": "关羽水淹七军战役",
                "focus_area": "战役全过程与关键战略转折",
                "__preparation_source": "llm_structured_output",
            },
            "artifacts": [],
        },
    )

    result = runtime.run(
        request=ChatRequestV2(question="确认并继续", conversation_id="conv-4"),
        snapshot=snapshot,
        decision=None,
    )

    assert called["engine"] is True
    assert called["state"]["generation_ready"] is True
    assert called["state"]["report_slots"]["core_topic"] == "关羽水淹七军战役"
    assert called["state"]["report_slots"]["focus_area"] == "战役全过程与关键战略转折"
    assert result["message"]["content"] == "报告大纲已生成"
