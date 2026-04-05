from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.status_card_builder import StatusCardBuilder


def test_status_card_builder_exposes_rich_evidence_details():
    snapshot = ConversationSnapshot(
        conversation_id="conv-evidence-card",
        conversation_memory={
            "evidence_points": [
                {
                    "type": "observation",
                    "content": "课堂前10分钟举手响应较少",
                    "source_type": "assistant_message",
                    "source_message_ids": ["msg-1", "msg-2"],
                    "confidence": "medium",
                }
            ]
        },
        capability=CapabilityPolicy(),
    )

    card = StatusCardBuilder().build(snapshot=snapshot, workflow=None, capability=snapshot.capability)

    assert card.evidence_details[0].content == "课堂前10分钟举手响应较少"
    assert card.evidence_details[0].source_type == "assistant_message"
    assert card.evidence_details[0].confidence == "medium"
    assert card.evidence_details[0].source_message_count == 2


def test_status_card_builder_keeps_evidence_details_empty_for_low_state_chat():
    snapshot = ConversationSnapshot(
        conversation_id="conv-evidence-empty",
        conversation_memory={},
        capability=CapabilityPolicy(),
    )

    card = StatusCardBuilder().build(snapshot=snapshot, workflow=None, capability=snapshot.capability)

    assert card.evidence_details == []
