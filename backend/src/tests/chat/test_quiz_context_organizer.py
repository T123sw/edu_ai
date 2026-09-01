from app.chat.domain.generation_context import GenerationContext
from app.chat.domain.quiz_preparation import QuizContextSummary, QuizPreparationResult
from app.chat.orchestrator.quiz_context_organizer import QuizContextOrganizer


class StubStructuredLlm:
    def __init__(self, result: QuizPreparationResult):
        self.result = result
        self.prompts: list[str] = []

    def with_structured_output(self, schema, method="function_calling"):
        assert schema is QuizPreparationResult
        assert method == "function_calling"
        return self

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return self.result


def test_quiz_context_organizer_summarizes_context_with_llm_before_readiness_judgement():
    context = GenerationContext(
        conversation_id="conv-quiz-llm-1",
        resource_type="quiz",
        summary_text="当前围绕关羽生平、重要战役和人物形象展开讨论，希望整理成阅读理解和基础历史练习。",
        current_topics=["关羽生平"],
        user_goals=["生成习题"],
        confirmed_facts=["关羽，字云长", "曾参与重要战役", "人物形象忠义"],
        constraints={},
        teaching_issues=[],
        student_signals=["适合小学高年级阅读理解"],
        evidence_points=[],
        recent_relevant_messages=[
            {"role": "assistant", "content": "我们刚刚整理了关羽的生平、身份、字和主要事迹。"},
            {"role": "user", "content": "根据以上内容生成习题"},
        ],
        source_scope={"from_summary": True, "from_recent_messages": True},
    )
    llm = StubStructuredLlm(
        QuizPreparationResult(
            quiz_intent="generate_quiz",
            topic="关羽生平",
            question_count=None,
            question_types=[],
            include_answers=True,
            include_explanations=True,
            quiz_context_summary=QuizContextSummary(
                topic_summary="关羽生平与人物形象",
                settings_summary="适合小学高年级阅读理解练习",
                weak_points=["人物信息提取"],
                knowledge_points=["关羽身份", "关羽的字", "重要事迹"],
                constraints={},
                source_scope=["conversation_summary", "recent_messages"],
            ),
            constraints={},
            source_scope=["conversation_summary", "recent_messages"],
            knowledge_points=["关羽身份", "关羽的字", "重要事迹"],
            weak_points=["人物信息提取"],
            missing_critical_fields=[],
            confidence="high",
            soft_confirm_message="我可以基于关羽生平直接生成一组习题。如果可以，我就开始生成。",
        )
    )

    result = QuizContextOrganizer(llm=llm).organize(
        context=context,
        request_question="根据以上内容生成习题",
    )

    assert llm.prompts
    prompt = llm.prompts[0]
    assert "recent_relevant_messages" in prompt
    assert "summary=" in prompt
    assert result.topic == "关羽生平"
    assert result.knowledge_points == ["关羽身份", "关羽的字", "重要事迹"]
    assert result.weak_points == ["人物信息提取"]
    assert result.missing_critical_fields == []


def test_quiz_context_organizer_extracts_topic_count_and_type_from_freeform_slot_answer():
    context = GenerationContext(
        conversation_id="conv-quiz-freeform-1",
        resource_type="quiz",
        summary_text="",
        current_topics=[],
        user_goals=["生成习题"],
        confirmed_facts=["关羽，字云长", "曾参与重要战役"],
        constraints={},
        teaching_issues=[],
        student_signals=[],
        evidence_points=[],
        recent_relevant_messages=[
            {"role": "assistant", "content": "你希望我基于什么内容来生成习题？可以直接告诉我主题、题量或题型。"},
            {"role": "user", "content": "关羽的生平，10，选择题"},
        ],
        source_scope={"from_recent_messages": True},
    )

    result = QuizContextOrganizer().organize(
        context=context,
        request_question="关羽的生平，10，选择题",
        stored_slots={},
    )

    assert result.topic == "关羽的生平"
    assert result.question_count == 10
    assert result.question_types == ["choice"]
    assert result.missing_critical_fields == []


def test_quiz_context_organizer_extracts_difficulty_from_freeform_slot_answer():
    context = GenerationContext(
        conversation_id="conv-quiz-freeform-2",
        resource_type="quiz",
        summary_text="",
        current_topics=[],
        user_goals=["生成习题"],
        confirmed_facts=["关羽，字云长"],
        constraints={},
        teaching_issues=[],
        student_signals=[],
        evidence_points=[],
        recent_relevant_messages=[],
        source_scope={"from_recent_messages": True},
    )

    result = QuizContextOrganizer().organize(
        context=context,
        request_question="关羽的生平，10道选择题，基础难度",
        stored_slots={},
    )

    assert result.topic == "关羽的生平"
    assert result.question_count == 10
    assert result.question_types == ["choice"]
    assert result.difficulty == "easy"


def test_quiz_context_organizer_derives_topic_from_history_when_request_is_generic():
    context = GenerationContext(
        conversation_id="conv-quiz-history-1",
        resource_type="quiz",
        summary_text="",
        current_topics=[],
        user_goals=["生成习题"],
        confirmed_facts=[
            "关羽在襄樊之战中取得胜利",
            "关羽北伐时需要留重兵守后方",
            "可对比张飞、赵云等武将的军事风格",
        ],
        constraints={},
        teaching_issues=[],
        student_signals=["防守意识薄弱"],
        evidence_points=[],
        recent_relevant_messages=[
            {
                "role": "assistant",
                "content": "建议围绕关羽的襄樊之战、水淹七军、后方防守和将领对比继续分析。",
            },
            {"role": "user", "content": "根据以上内容，生成习题"},
        ],
        source_scope={"from_memory": True, "from_recent_messages": True},
    )

    result = QuizContextOrganizer().organize(
        context=context,
        request_question="根据以上内容，生成习题",
        stored_slots={},
    )

    assert "关羽" in (result.topic or "")
    assert result.quiz_intent == "generate_quiz"
    assert result.missing_critical_fields == []
    assert result.knowledge_points


def test_quiz_context_organizer_corrects_unclear_llm_intent_when_slots_are_ready():
    context = GenerationContext(
        conversation_id="conv-quiz-llm-intent-1",
        resource_type="quiz",
        summary_text="当前围绕关羽的历史战绩与文学形象辨析继续讨论",
        current_topics=["介绍他的战绩", "介绍下关羽"],
        user_goals=["继续对话"],
        confirmed_facts=[],
        constraints={},
        teaching_issues=["原因分析：并非单纯因为武力不足"],
        student_signals=[],
        evidence_points=[],
        recent_relevant_messages=[
            {"role": "user", "content": "介绍下关羽"},
            {"role": "user", "content": "介绍他的战绩"},
            {"role": "user", "content": "根据以上内容生成习题"},
        ],
        source_scope={"from_summary": True, "from_memory": True, "from_recent_messages": True},
    )
    llm = StubStructuredLlm(
        QuizPreparationResult(
            quiz_intent="unclear",
            topic="关羽的历史战绩与文学形象辨析",
            question_count=5,
            question_types=["choice", "judge", "short"],
            difficulty="medium",
            knowledge_points=["关羽的真实历史战绩", "三国志与三国演义的区别"],
            weak_points=["混淆历史事实与小说情节"],
            missing_critical_fields=[],
            confidence="low",
        )
    )

    result = QuizContextOrganizer(llm=llm).organize(
        context=context,
        request_question="根据以上内容生成习题",
        stored_slots={},
    )

    assert result.topic == "关羽的历史战绩与文学形象辨析"
    assert result.question_count == 5
    assert result.question_types == ["choice", "judge", "short"]
    assert result.quiz_intent == "generate_quiz"
