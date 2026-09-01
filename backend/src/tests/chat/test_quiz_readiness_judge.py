from app.chat.domain.quiz_preparation import QuizPreparationResult
from app.chat.orchestrator.quiz_readiness_judge import QuizFollowupPlan, QuizReadinessJudge


class StubFollowupLlm:
    def __init__(self, plan: QuizFollowupPlan):
        self.plan = plan
        self.prompts: list[str] = []

    def with_structured_output(self, schema, method="function_calling"):
        assert schema is QuizFollowupPlan
        assert method == "function_calling"
        return self

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return self.plan


def test_quiz_readiness_judge_uses_llm_for_minimal_followup():
    llm = StubFollowupLlm(
        QuizFollowupPlan(
            ask_needed=True,
            question="我可以直接出题，再告诉我题量和题型就行。",
            asked_fields=["question_count", "question_types", "difficulty"],
        )
    )
    result = QuizPreparationResult(
        quiz_intent="generate_quiz",
        topic="关羽的生平",
        question_count=None,
        question_types=[],
        difficulty=None,
        knowledge_points=[],
        weak_points=[],
    )

    decision = QuizReadinessJudge(llm=llm).judge(result, entry_mode="reply")

    assert llm.prompts
    assert decision["action"] == "ask_generation_basis"
    assert decision["question"] == "我可以直接出题，再告诉我题量和题型就行。"
    assert decision["asked_fields"] == ["question_count", "question_types"]


def test_quiz_readiness_judge_only_asks_topic_when_topic_missing():
    llm = StubFollowupLlm(
        QuizFollowupPlan(
            ask_needed=True,
            question="你想围绕哪个主题生成习题？",
            asked_fields=["topic", "question_count"],
        )
    )
    result = QuizPreparationResult(
        quiz_intent="generate_quiz",
        topic=None,
        question_count=None,
        question_types=[],
        difficulty=None,
    )

    decision = QuizReadinessJudge(llm=llm).judge(result, entry_mode="reply")

    assert decision["action"] == "ask_critical_gap"
    assert decision["question"] == "你想围绕哪个主题生成习题？"
    assert decision["asked_fields"][0] == "topic"
    assert decision["missing_critical_fields"] == ["topic"]
