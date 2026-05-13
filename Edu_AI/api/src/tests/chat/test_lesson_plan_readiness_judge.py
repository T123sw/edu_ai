from app.chat.domain.lesson_plan_preparation import LessonPlanPreparationResult
from app.chat.orchestrator.lesson_plan_readiness_judge import LessonPlanReadinessJudge


def test_lesson_plan_readiness_judge_asks_critical_gap_when_topic_is_missing():
    result = LessonPlanPreparationResult(
        objective="Compare fractions",
        key_points=["Use visuals", "Use examples"],
    )

    decision = LessonPlanReadinessJudge().judge(result, entry_mode="reply")

    assert decision["action"] == "ask_critical_gap"
    assert decision["missing_critical_fields"] == ["topic"]


def test_lesson_plan_readiness_judge_returns_strong_soft_confirm_when_outline_basis_is_sufficient():
    result = LessonPlanPreparationResult(
        topic="Fractions",
        audience="Grade 5",
        objective="Compare fractions",
        key_points=["Use visuals", "Use examples"],
        knowledge_points=["Equivalent fractions", "Common denominators"],
    )

    decision = LessonPlanReadinessJudge().judge(result, entry_mode="reply")

    assert decision["action"] == "strong_soft_confirm"


def test_lesson_plan_readiness_judge_returns_weak_soft_confirm_for_button_entry():
    result = LessonPlanPreparationResult(
        topic="Fractions",
        audience="Grade 5",
        objective="Compare fractions",
        key_points=["Use visuals", "Use examples"],
        knowledge_points=["Equivalent fractions", "Common denominators"],
    )

    decision = LessonPlanReadinessJudge().judge(result, entry_mode="button")

    assert decision["action"] == "weak_soft_confirm"


def test_lesson_plan_readiness_judge_returns_strong_soft_confirm_for_objective_only():
    result = LessonPlanPreparationResult(
        topic="Fractions",
        objective="Compare fractions",
    )

    decision = LessonPlanReadinessJudge().judge(result, entry_mode="reply")

    assert decision["action"] == "strong_soft_confirm"


def test_lesson_plan_readiness_judge_asks_for_objective_or_outline_basis_when_outline_is_thin():
    result = LessonPlanPreparationResult(
        topic="Fractions",
        audience="Grade 5",
    )

    decision = LessonPlanReadinessJudge().judge(result, entry_mode="reply")

    assert decision["action"] == "ask_objective_or_outline_basis"
    assert decision["missing_critical_fields"] == ["objective_or_outline_basis"]
