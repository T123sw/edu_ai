from types import SimpleNamespace

from app.chat.domain.contracts import ChatRequestV2
from app.chat.orchestrator.route_rules import decide_route


def test_quiz_command_uses_workflow_path():
    request = ChatRequestV2(question="generate a quiz", action_hint="generate.quiz")

    decision = decide_route(request=request, snapshot=None, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "quiz"
    assert decision.action == "generate.quiz"


def test_quiz_followup_from_active_context_uses_workflow():
    snapshot = SimpleNamespace(
        active_artifact=None,
        active_context={
            "active_workflow_type": "quiz",
            "active_workflow_status": "awaiting_confirm",
            "active_artifact_type": "quiz",
        },
        conversation_memory={
            "user_goals": ["generate quiz"],
            "derived_workflow_goal": "quiz",
        },
    )
    request = ChatRequestV2(question="continue")

    decision = decide_route(request=request, snapshot=snapshot, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "quiz"
    assert decision.reason == "resume_active_quiz_context"


def test_quiz_freeform_slot_answer_from_active_context_uses_workflow():
    snapshot = SimpleNamespace(
        active_artifact=None,
        active_context={
            "active_workflow_type": "quiz",
            "active_workflow_status": "awaiting_confirm",
            "active_artifact_type": "quiz",
        },
        conversation_memory={
            "user_goals": ["生成习题"],
            "derived_workflow_goal": "quiz",
        },
    )
    request = ChatRequestV2(question="关羽的生平，10，选择题")

    decision = decide_route(request=request, snapshot=snapshot, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "quiz"
    assert decision.reason == "resume_active_quiz_context"
