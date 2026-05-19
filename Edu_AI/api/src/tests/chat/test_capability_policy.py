from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.route_decision import RouteDecision


def test_capability_policy_defaults_disable_rag_and_web():
    policy = CapabilityPolicy()

    assert policy.allow_rag is False
    assert policy.allow_web is False
    assert policy.allow_tools is False


def test_route_decision_for_fast_chat():
    decision = RouteDecision.fast(action="chat.reply", reason="default_chat")

    assert decision.path == "fast"
    assert decision.action == "chat.reply"
    assert decision.workflow_name is None


def test_route_decision_for_agent_path():
    decision = RouteDecision.agent(reason="react_agent_enabled")

    assert decision.path == "agent"
    assert decision.action == "agent.plan"
    assert decision.workflow_name is None
    assert decision.reason == "react_agent_enabled"
