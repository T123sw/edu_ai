from app.chat.domain.generation_context import GenerationContext
from app.chat.domain.quiz_preparation import QuizPreparationResult
from app.chat.orchestrator.quiz_context_organizer import QuizContextOrganizer
from app.chat.orchestrator.quiz_readiness_judge import QuizReadinessJudge


class StubQwenJsonQuizLlm:
    model = "qwen3.5-plus"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(self, payload: str):
        self.payload = payload
        self.structured_calls = 0

    def with_structured_output(self, *_args, **_kwargs):
        self.structured_calls += 1
        raise AssertionError("qwen-compatible llm should not use function_calling structured output")

    def invoke(self, _prompt: str):
        return self.payload


def test_quiz_context_organizer_uses_raw_json_directly_for_qwen_compatible_models():
    context = GenerationContext(
        conversation_id="conv-quiz-qwen-1",
        resource_type="quiz",
        summary_text="围绕 Python 变量定义生成习题。",
        current_topics=["Python 变量定义"],
        user_goals=["生成习题"],
        confirmed_facts=["变量通过赋值定义", "变量名不能以数字开头"],
        constraints={},
        teaching_issues=[],
        student_signals=["学生容易把赋值和比较混淆"],
        evidence_points=[],
        recent_relevant_messages=[{"role": "user", "content": "根据以上内容生成 5 道选择题"}],
        source_scope={"from_summary": True, "from_recent_messages": True},
    )
    llm = StubQwenJsonQuizLlm(
        """```json
{
  "quiz_intent": "generate_quiz",
  "topic": "Python 变量定义",
  "question_count": 5,
  "question_types": ["choice"],
  "difficulty": "easy",
  "include_answers": true,
  "include_explanations": true,
  "quiz_context_summary": {
    "topic_summary": "围绕 Python 变量定义生成习题。",
    "settings_summary": "count=5",
    "weak_points": ["学生容易把赋值和比较混淆"],
    "knowledge_points": ["变量通过赋值定义", "变量名不能以数字开头"],
    "constraints": {},
    "source_scope": ["conversation_summary", "recent_messages"]
  },
  "constraints": {},
  "source_scope": ["conversation_summary", "recent_messages"],
  "knowledge_points": ["变量通过赋值定义", "变量名不能以数字开头"],
  "weak_points": ["学生容易把赋值和比较混淆"],
  "missing_critical_fields": [],
  "confidence": "high"
}
```"""
    )

    result = QuizContextOrganizer(llm=llm).organize(
        context=context,
        request_question="根据以上内容生成 5 道选择题",
        stored_slots={},
    )

    assert llm.structured_calls == 0
    assert result.topic == "Python 变量定义"
    assert result.question_count == 5
    assert result.question_types == ["choice"]
    assert result.quiz_intent == "generate_quiz"


def test_quiz_readiness_judge_uses_raw_json_directly_for_qwen_compatible_models():
    llm = StubQwenJsonQuizLlm(
        """```json
{
  "ask_needed": true,
  "question": "你希望出几道题、采用什么题型？",
  "asked_fields": ["question_count", "question_types"]
}
```"""
    )
    result = QuizPreparationResult(
        quiz_intent="generate_quiz",
        topic="Python 变量定义",
        question_count=None,
        question_types=[],
        difficulty=None,
    )

    decision = QuizReadinessJudge(llm=llm).judge(result, entry_mode="reply")

    assert llm.structured_calls == 0
    assert decision["action"] == "ask_generation_basis"
    assert decision["question"] == "你希望出几道题、采用什么题型？"
    assert decision["asked_fields"] == ["question_count", "question_types"]
