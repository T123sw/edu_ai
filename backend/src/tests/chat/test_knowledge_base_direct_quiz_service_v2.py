from types import SimpleNamespace

from app.chat.application.knowledge_base_direct_quiz_service_v2 import KnowledgeBaseDirectQuizServiceV2


class StubContentProvider:
    def get_selected_document_contents(self, *, selected_doc_ids, owner):
        return {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "关羽历史形象分析",
                    "summary": "围绕关羽的正史战绩、文学形象与失荆州原因展开。",
                    "content": "关羽在正史中的代表战绩包括白马坡斩颜良和襄樊之战水淹七军。",
                }
            ],
            "truncated": False,
        }


class StubLlm:
    def __init__(self, responses):
        self.responses = list(responses)
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        return SimpleNamespace(content=self.responses.pop(0))


class NoSourceContentProvider:
    def get_selected_document_contents(self, **_kwargs):
        raise AssertionError("none source mode must not read the knowledge base")


def test_direct_quiz_service_prefill_extracts_topic_and_hard_points():
    service = KnowledgeBaseDirectQuizServiceV2(
        content_provider=StubContentProvider(),
        llm=StubLlm(
            [
                '{"topic":"关羽的历史形象与军事能力","hard_points":["区分正史与演义情节","分析失荆州的多重原因"]}',
            ]
        ),
        course_storage_manager=None,
    )

    result = service.prefill(
        SimpleNamespace(
            selected_doc_ids=["doc-1"],
            course_id="course-1",
            owner="u1",
        )
    )

    assert result["entry_mode"] == "knowledge_base_quiz"
    assert result["topic"] == "关羽的历史形象与军事能力"
    assert result["hard_points"] == ["区分正史与演义情节", "分析失荆州的多重原因"]


def test_direct_quiz_service_generate_returns_quiz_artifact():
    service = KnowledgeBaseDirectQuizServiceV2(
        content_provider=StubContentProvider(),
        llm=StubLlm(
            [
                """
                {
                  "questions": [
                    {
                      "question": "以下哪一项属于关羽的正史核心战绩？",
                      "question_type": "选择题",
                      "choices": ["温酒斩华雄", "白马坡斩颜良", "过五关斩六将", "单刀赴会"],
                      "correct_answer": "B",
                      "analysis": "白马坡斩颜良是正史明确记载的战绩。"
                    }
                  ]
                }
                """,
            ]
        ),
        course_storage_manager=None,
    )

    result = service.generate(
        SimpleNamespace(
            selected_doc_ids=["doc-1"],
            course_id="course-1",
            owner="u1",
            prompt_draft="请基于文档生成习题。",
            final_user_prompt="生成 1 道中等难度选择题。",
            quiz_config={
                "topic": "关羽的历史形象与军事能力",
                "hard_points": ["区分正史与演义情节"],
                "difficulty": "medium",
                "question_count": 1,
                "question_types": ["choice"],
                "include_answers": True,
                "include_explanations": True,
            },
        )
    )

    assert result["action"]["name"] == "generate.quiz.direct"
    assert result["trace"]["path"] == "direct"
    assert result["artifacts"][0]["artifact_type"] == "quiz"
    assert result["artifacts"][0]["content"]["questions"][0]["stem"] == "以下哪一项属于关羽的正史核心战绩？"


def test_direct_quiz_service_generates_from_topic_without_documents():
    llm = StubLlm(
        [
            '{"questions":[{"question":"What is an agent?","type":"short","correct_answer":"An autonomous system.","analysis":"Core definition."}]}'
        ]
    )
    service = KnowledgeBaseDirectQuizServiceV2(
        content_provider=NoSourceContentProvider(),
        llm=llm,
        course_storage_manager=None,
    )

    result = service.generate(
        SimpleNamespace(
            selected_doc_ids=[],
            source_mode="none",
            course_id="course-1",
            owner="u1",
            prompt_draft="",
            final_user_prompt="",
            quiz_config={
                "topic": "Agent principles",
                "difficulty": "medium",
                "question_count": 1,
                "question_types": ["short"],
                "include_answers": True,
                "include_explanations": True,
            },
        )
    )

    assert result["artifacts"][0]["artifact_type"] == "quiz"
    assert result["trace"]["selected_doc_count"] == 0
    assert "Agent principles" in str(llm.messages[0])


def test_course_context_is_included_in_quiz_model_messages():
    llm = StubLlm(['{"questions":[{"question":"变量是什么？","question_type":"选择题","choices":["名字绑定","固定数字"],"correct_answer":"A","analysis":"课程中变量是名字到对象的绑定。"}]}'])
    service = KnowledgeBaseDirectQuizServiceV2(content_provider=NoSourceContentProvider(), llm=llm, course_storage_manager=None)
    service.generate(SimpleNamespace(selected_doc_ids=[], course_id='course-context-test', owner='alice', quiz_config={'topic':'变量','question_count':1}, research_context='Python 课程原文：名字到对象的绑定。'))
    assert '名字到对象的绑定' in str(llm.messages[0])


def test_audience_and_output_switches_reach_saved_quiz():
    class Storage:
        def save_generated_material(self, **kwargs):
            self.saved = kwargs
            return True
    for answers in (True, False):
        for explanations in (True, False):
            llm = StubLlm(['{"questions":[{"question":"变量是什么？","type":"short","correct_answer":"命名存储。"}]}'])
            storage = Storage()
            service = KnowledgeBaseDirectQuizServiceV2(content_provider=NoSourceContentProvider(), llm=llm, course_storage_manager=storage)
            result = service.generate(SimpleNamespace(owner='u1', course_id='course-1', selected_doc_ids=[],
                quiz_config={'topic': '变量', 'audience': '没有编程基础的成年人', 'question_count': 1,
                    'question_types': ['short'], 'include_answers': answers, 'include_explanations': explanations}))
            assert '适用对象：没有编程基础的成年人' in str(llm.messages)
            question = result['artifacts'][0]['content']['questions'][0]
            assert bool(question['answer']) is answers
            assert bool(question['explanation']) is explanations
            assert storage.saved['material_data']['content']['questions'][0] == question
