from types import SimpleNamespace

from app.chat.domain.contracts import ChatRequestV2
from app.chat.orchestrator.route_rules import decide_route


def test_generate_ppt_action_hint_routes_to_ppt_workflow():
    request = ChatRequestV2(question="生成一个 PPT", action_hint="generate.ppt")

    decision = decide_route(request=request, snapshot=None, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "ppt"


def test_ppt_followup_from_active_context_routes_to_ppt_workflow():
    snapshot = SimpleNamespace(
        active_artifact=None,
        active_context={
            "active_workflow_type": "ppt",
            "active_workflow_status": "awaiting_confirm",
            "active_artifact_type": "ppt_outline",
        },
        conversation_memory={
            "user_goals": ["生成PPT"],
            "derived_workflow_goal": "生成PPT",
        },
    )
    request = ChatRequestV2(question="确认并生成")

    decision = decide_route(request=request, snapshot=snapshot, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "ppt"
