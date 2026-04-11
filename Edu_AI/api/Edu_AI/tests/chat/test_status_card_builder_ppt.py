from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.status_card_builder import StatusCardBuilder


def test_status_card_builder_supports_ppt_waiting_confirmation_copy():
    snapshot = ConversationSnapshot(
        conversation_id="conv-ppt",
        summary="",
        conversation_memory={"current_topics": ["TCP 三次握手"], "user_goals": ["生成PPT"]},
        active_context={},
        capability=CapabilityPolicy(),
    )

    card = StatusCardBuilder().build(
        snapshot=snapshot,
        workflow={"type": "ppt", "status": "awaiting_confirm", "phase": "awaiting_outline_confirmation"},
        capability=snapshot.capability,
    )

    assert card.mode == "workflow"
    assert card.status_label == "等待你确认 PPT 大纲"
    assert card.waiting_label == "等待你确认 PPT 大纲"
    assert card.suggested_actions == ["确认并生成", "调整要求"]
