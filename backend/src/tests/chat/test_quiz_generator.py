from types import SimpleNamespace

from app.chat.workflows.quiz.generator import QuizGenerator


class FakeLlm:
    def __init__(self, content: str):
        self.content = content

    def invoke(self, prompt: str):
        return SimpleNamespace(content=self.content)


def test_quiz_generator_accepts_common_model_question_field_names():
    generator = QuizGenerator(
        llm=FakeLlm(
            """
            {
              "questions": [
                {
                  "question": "以下哪一项属于关羽的正史核心战绩？",
                  "question_type": "选择题",
                  "choices": ["温酒斩华雄", "白马之战斩颜良", "过五关斩六将", "单刀赴会"],
                  "correct_answer": "B",
                  "analysis": "白马之战斩颜良见于正史记载。"
                },
                {
                  "题干": "《三国演义》中温酒斩华雄属于文学演绎。",
                  "题型": "判断题",
                  "答案": "正确",
                  "解析": "这一情节并非正史中的关羽核心战绩。"
                }
              ]
            }
            """
        )
    )

    artifact = generator.generate(
        preparation={
            "topic": "关羽的历史与文学形象辨析",
            "question_count": 2,
            "question_types": ["choice", "judge"],
            "difficulty": "medium",
        },
        context_summary="对比正史与小说中的关羽形象。",
        conversation_id="conv-quiz-generator-1",
        owner="u1",
        allow_rag=False,
        selected_doc_ids=[],
    )

    questions = artifact["content"]["questions"]
    assert len(questions) == 2
    assert questions[0]["stem"] == "以下哪一项属于关羽的正史核心战绩？"
    assert questions[0]["type"] == "choice"
    assert questions[0]["options"] == ["温酒斩华雄", "白马之战斩颜良", "过五关斩六将", "单刀赴会"]
    assert questions[0]["answer"] == "B"
    assert questions[1]["type"] == "judge"
    assert questions[1]["explanation"] == "这一情节并非正史中的关羽核心战绩。"


def test_quiz_generator_does_not_return_empty_artifact_when_model_questions_are_empty():
    generator = QuizGenerator(
        llm=FakeLlm('{"questions": []}'),
    )

    artifact = generator.generate(
        preparation={
            "topic": "关羽的历史与文学形象辨析",
            "question_count": 3,
            "question_types": ["choice"],
            "difficulty": "medium",
            "knowledge_points": ["白马之战斩颜良", "水淹七军", "正史与小说的区别"],
        },
        context_summary="围绕关羽战绩展开讨论。",
        conversation_id="conv-quiz-generator-empty",
        owner="u1",
        allow_rag=False,
        selected_doc_ids=[],
    )

    questions = artifact["content"]["questions"]
    assert len(questions) == 3
    assert questions[0]["stem"]
    assert questions[0]["options"]
    assert questions[0]["answer"]
    assert artifact["generation_state"]["fallback_used"] is True


def test_quiz_generator_fallback_explanation_explains_why_answer_is_correct():
    generator = QuizGenerator(
        llm=FakeLlm('{"questions": []}'),
    )

    artifact = generator.generate(
        preparation={
            "topic": "随机过程基础：概率论核心与随机过程基本概念",
            "question_count": 1,
            "question_types": ["choice"],
            "difficulty": "medium",
            "knowledge_points": ["随机过程的双重性质理解（固定时刻随机变量与固定样本点样本函数）"],
        },
        context_summary="围绕随机过程双重性、样本函数与随机变量的关系展开讨论。",
        conversation_id="conv-quiz-generator-explanation",
        owner="u1",
        allow_rag=False,
        selected_doc_ids=[],
    )

    explanation = artifact["content"]["questions"][0]["explanation"]
    assert "正确答案" in explanation
    assert "本题考查" not in explanation
