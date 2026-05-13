from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.status_card_builder import StatusCardBuilder


def test_status_card_builder_hides_retracted_claims():
    snapshot = ConversationSnapshot(
        conversation_id="conv-fact-lifecycle",
        summary="",
        conversation_memory={
            "user_claims": [
                {"content": "前10分钟学生多次走神", "status": "retracted"},
                {"content": "后10分钟学生多次走神", "status": "stated"},
            ],
            "confirmed_facts": ["前10分钟学生多次走神", "后10分钟学生多次走神"],
        },
        active_context={},
        capability=CapabilityPolicy(),
    )

    card = StatusCardBuilder().build(
        snapshot=snapshot,
        workflow=None,
        capability=snapshot.capability,
    )

    assert card.confirmed_facts == ["后10分钟学生多次走神"]
