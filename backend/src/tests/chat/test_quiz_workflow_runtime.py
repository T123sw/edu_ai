from types import SimpleNamespace

from app.chat.domain.generation_context import GenerationContext
from app.chat.domain.quiz_preparation import QuizPreparationResult
from app.chat.domain.workflow_state import WorkflowState
from app.chat.orchestrator.quiz_context_organizer import QuizContextOrganizer
from app.chat.orchestrator.quiz_readiness_judge import QuizReadinessJudge
from app.chat.workflows.quiz.runtime import QuizWorkflowRuntime
from core.config import Config


def test_quiz_workflow_runtime_turns_freeform_slot_answer_into_soft_confirm():
    context = GenerationContext(
        conversation_id="conv-quiz-runtime-1",
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
    runtime = QuizWorkflowRuntime(
        generation_context_builder=SimpleNamespace(build_for_resource=lambda **kwargs: context),
        quiz_context_organizer=QuizContextOrganizer(),
        quiz_readiness_judge=QuizReadinessJudge(),
        quiz_generator=SimpleNamespace(generate=lambda **kwargs: {"artifact_id": "unused"}),
    )
    snapshot = SimpleNamespace(
        workflow_state=WorkflowState(
            workflow_id="conv-quiz-runtime-1",
            workflow_type="quiz",
            status="awaiting_confirm",
            stage="critical_gap",
            required_slots=["topic"],
            filled_slots={},
            artifacts=[],
        )
    )
    request = SimpleNamespace(
        question="关羽的生平，10，选择题",
        conversation_id="conv-quiz-runtime-1",
        action_hint=None,
        owner="u1",
        capability=SimpleNamespace(allow_rag=False, selected_doc_ids=[]),
    )

    result = runtime.run(
        request=request,
        snapshot=snapshot,
        decision=SimpleNamespace(path="workflow", action="generate.quiz", workflow_name="quiz"),
    )

    assert result["workflow"]["type"] == "quiz"
    assert result["workflow"]["stage"] == "soft_confirm"
    assert result["workflow"]["filled_slots"]["topic"] == "关羽的生平"
    assert result["workflow"]["filled_slots"]["question_count"] == "10"
    assert result["workflow"]["filled_slots"]["question_types"] == "choice"


def test_quiz_workflow_runtime_traces_context_preparation_and_slots(capsys, monkeypatch):
    monkeypatch.setattr(Config, "QUIZ_WORKFLOW_TRACE", "1")
    context = GenerationContext(
        conversation_id="conv-quiz-trace-1",
        resource_type="quiz",
        summary_text="",
        current_topics=[],
        user_goals=["生成习题"],
        confirmed_facts=["关羽在襄樊之战中水淹七军", "关羽北伐时需要留重兵守后方"],
        constraints={},
        teaching_issues=[],
        student_signals=["防守意识薄弱"],
        evidence_points=[],
        recent_relevant_messages=[
            {"role": "assistant", "content": "围绕关羽的襄樊之战、水淹七军和后方防守展开。"},
            {"role": "user", "content": "根据以上内容，生成习题"},
        ],
        source_scope={"from_memory": True, "from_recent_messages": True},
    )
    runtime = QuizWorkflowRuntime(
        generation_context_builder=SimpleNamespace(build_for_resource=lambda **kwargs: context),
        quiz_context_organizer=QuizContextOrganizer(),
        quiz_readiness_judge=QuizReadinessJudge(),
        quiz_generator=SimpleNamespace(generate=lambda **kwargs: {"artifact_id": "unused"}),
    )
    request = SimpleNamespace(
        question="根据以上内容，生成习题",
        conversation_id="conv-quiz-trace-1",
        action_hint="generate.quiz",
        owner="u1",
        capability=SimpleNamespace(allow_rag=False, selected_doc_ids=[]),
    )

    runtime.run(
        request=request,
        snapshot=SimpleNamespace(workflow_state=None, active_context={}, active_artifact=None),
        decision=SimpleNamespace(path="workflow", action="generate.quiz", workflow_name="quiz"),
    )

    output = capsys.readouterr().out

    assert "workflow_start" in output
    assert "generation_context" in output
    assert "quiz_preparation_result" in output
    assert "readiness_decision" in output
    assert "workflow_response" in output
    assert "filled_slots" in output
    assert "关羽" in output


def test_quiz_workflow_runtime_generates_after_soft_confirm_even_if_confirm_turn_intent_is_unclear():
    context = GenerationContext(
        conversation_id="conv-quiz-confirm-1",
        resource_type="quiz",
        summary_text="当前围绕关羽的历史事迹与文化形象继续讨论",
        current_topics=["关羽的历史事迹与文化形象"],
        user_goals=["生成练习"],
        confirmed_facts=[],
        constraints={},
        teaching_issues=[],
        student_signals=[],
        evidence_points=[],
        recent_relevant_messages=[],
        source_scope={"from_memory": True},
    )

    class ConfirmTurnOrganizer:
        def organize(self, **kwargs):
            return QuizPreparationResult(
                quiz_intent="unclear",
                topic="可以",
                question_count=5,
                question_types=["choice", "judge", "short"],
                difficulty="medium",
                knowledge_points=["关羽核心战绩"],
                weak_points=[],
            )

    class CapturingGenerator:
        def __init__(self):
            self.calls = []

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "artifact_id": "quiz-confirm-1",
                "artifact_type": "quiz",
                "content": {"questions": []},
            }

    generator = CapturingGenerator()
    runtime = QuizWorkflowRuntime(
        generation_context_builder=SimpleNamespace(build_for_resource=lambda **kwargs: context),
        quiz_context_organizer=ConfirmTurnOrganizer(),
        quiz_readiness_judge=QuizReadinessJudge(),
        quiz_generator=generator,
    )
    snapshot = SimpleNamespace(
        workflow_state=WorkflowState(
            workflow_id="conv-quiz-confirm-1",
            workflow_type="quiz",
            status="awaiting_confirm",
            stage="soft_confirm",
            required_slots=[],
            filled_slots={
                "topic": "关羽的历史事迹与文化形象",
                "question_count": "5",
                "question_types": "choice|judge|short",
                "difficulty": "medium",
                "include_answers": "true",
                "include_explanations": "true",
            },
            artifacts=[],
        ),
        active_context={"active_workflow_type": "quiz", "active_workflow_status": "awaiting_confirm"},
    )
    request = SimpleNamespace(
        question="可以",
        conversation_id="conv-quiz-confirm-1",
        action_hint=None,
        owner="u1",
        capability=SimpleNamespace(allow_rag=False, selected_doc_ids=[]),
    )

    result = runtime.run(
        request=request,
        snapshot=snapshot,
        decision=SimpleNamespace(path="workflow", action="quiz", workflow_name="quiz", reason="resume_workflow"),
    )

    assert result["workflow"]["status"] == "completed"
    assert result["artifacts"][0]["artifact_type"] == "quiz"
    assert result["workflow"]["filled_slots"]["topic"] == "关羽的历史事迹与文化形象"
    assert generator.calls[0]["preparation"]["topic"] == "关羽的历史事迹与文化形象"
