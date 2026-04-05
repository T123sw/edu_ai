from app.chat.domain.report_preparation import ReportPreparationResult
from app.chat.orchestrator.generation_readiness_judge import GenerationReadinessJudge


def test_generation_readiness_judge_returns_strong_soft_confirm_when_subject_and_focus_exist():
    result = ReportPreparationResult(
        report_intent="generate_report",
        report_subject="关羽北伐失败原因",
        report_focus="军资供应如何引发内部失和",
        key_points=["军资短缺导致内部失和", "军心受挫"],
    )

    decision = GenerationReadinessJudge().judge(result, entry_mode="reply")

    assert decision["action"] == "strong_soft_confirm"


def test_generation_readiness_judge_returns_weak_soft_confirm_for_button_entry():
    result = ReportPreparationResult(
        report_intent="generate_report",
        report_subject="Skills 与 MCP 的差异",
        report_focus=None,
        key_points=["Skills 更偏内置能力", "MCP 更偏开放协议"],
    )

    decision = GenerationReadinessJudge().judge(result, entry_mode="button")

    assert decision["action"] == "weak_soft_confirm"


def test_generation_readiness_judge_returns_ask_critical_gap_when_subject_missing():
    result = ReportPreparationResult(report_intent="generate_report")

    decision = GenerationReadinessJudge().judge(result, entry_mode="reply")

    assert decision["action"] == "ask_critical_gap"
    assert decision["missing_critical_fields"] == ["report_subject"]


def test_generation_readiness_judge_allows_ready_report_when_intent_is_analysis():
    result = ReportPreparationResult(
        report_intent="analysis",
        report_subject="关羽水淹七军战役",
        report_focus="战役全过程与关键战略转折",
        key_points=["战前部署", "洪水爆发", "战后影响"],
    )

    decision = GenerationReadinessJudge().judge(result, entry_mode="reply")

    assert decision["action"] == "strong_soft_confirm"
