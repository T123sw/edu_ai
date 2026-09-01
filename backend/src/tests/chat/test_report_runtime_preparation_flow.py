from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.domain.report_preparation import ReportPreparationResult
from app.chat.workflows.report.runtime import ReportWorkflowRuntime


def test_runtime_returns_soft_confirm_without_calling_engine_when_context_is_ready():
    called = {"engine": False}

    class DummyEngine:
        def invoke(self, state):
            called["engine"] = True
            return {"reply": "should-not-run", "status": "running"}

    class DummyOrganizer:
        def organize(self, *, context, request_question):
            return ReportPreparationResult(
                report_intent="generate_report",
                report_subject="关羽北伐失败原因",
                report_focus="军资供应如何引发内部失和",
                key_points=["a", "b"],
                soft_confirm_message="我将基于关羽北伐失败原因生成报告，可以开始吗？",
            )

    class DummyJudge:
        def judge(self, result, *, entry_mode):
            return {"action": "strong_soft_confirm", "missing_critical_fields": []}

    runtime = ReportWorkflowRuntime(
        engine=DummyEngine(),
        report_context_organizer=DummyOrganizer(),
        generation_readiness_judge=DummyJudge(),
    )

    result = runtime.run(
        request=ChatRequestV2(question="请基于当前内容生成一份报告", conversation_id="conv-1"),
        snapshot=ConversationSnapshot(conversation_id="conv-1"),
        decision=None,
    )

    assert called["engine"] is False
    assert result["workflow"]["status"] == "awaiting_confirm"
    assert result["workflow"]["phase"] == "soft_confirm"
    assert "关羽北伐失败原因" in result["message"]["content"]


def test_runtime_asks_only_critical_gap_without_calling_engine():
    called = {"engine": False}

    class DummyEngine:
        def invoke(self, state):
            called["engine"] = True
            return {"reply": "should-not-run", "status": "running"}

    class DummyOrganizer:
        def organize(self, *, context, request_question):
            return ReportPreparationResult(
                report_intent="generate_report",
                report_subject=None,
                followup_candidates=["你希望这份报告围绕哪个主题来写？"],
                missing_critical_fields=["report_subject"],
            )

    class DummyJudge:
        def judge(self, result, *, entry_mode):
            return {"action": "ask_critical_gap", "missing_critical_fields": ["report_subject"]}

    runtime = ReportWorkflowRuntime(
        engine=DummyEngine(),
        report_context_organizer=DummyOrganizer(),
        generation_readiness_judge=DummyJudge(),
    )

    result = runtime.run(
        request=ChatRequestV2(question="帮我生成一份报告", conversation_id="conv-2"),
        snapshot=ConversationSnapshot(conversation_id="conv-2"),
        decision=None,
    )

    assert called["engine"] is False
    assert result["workflow"]["status"] == "awaiting_confirm"
    assert result["workflow"]["phase"] == "critical_gap"
    assert "哪个主题" in result["message"]["content"]


def test_runtime_builds_fallback_soft_confirm_message_when_preparation_message_is_empty():
    called = {"engine": False}

    class DummyEngine:
        def invoke(self, state):
            called["engine"] = True
            return {"reply": "should-not-run", "status": "running"}

    class DummyOrganizer:
        def organize(self, *, context, request_question):
            return ReportPreparationResult(
                report_intent="generate_report",
                report_subject="关羽水淹七军战役",
                report_focus="战役全过程与关键战略转折",
                key_points=["战前部署", "洪水爆发"],
                soft_confirm_message="",
            )

    class DummyJudge:
        def judge(self, result, *, entry_mode):
            return {"action": "strong_soft_confirm", "missing_critical_fields": []}

    runtime = ReportWorkflowRuntime(
        engine=DummyEngine(),
        report_context_organizer=DummyOrganizer(),
        generation_readiness_judge=DummyJudge(),
    )

    result = runtime.run(
        request=ChatRequestV2(question="请基于当前内容生成一份报告", conversation_id="conv-soft-fallback"),
        snapshot=ConversationSnapshot(conversation_id="conv-soft-fallback"),
        decision=None,
    )

    assert called["engine"] is False
    assert result["workflow"]["phase"] == "soft_confirm"
    assert "关羽水淹七军战役" in result["message"]["content"]
    assert "战役全过程与关键战略转折" in result["message"]["content"]
