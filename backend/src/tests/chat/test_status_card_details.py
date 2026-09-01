from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.status_card_builder import StatusCardBuilder


def test_status_card_builder_exposes_detail_lists_when_memory_has_rich_state():
    snapshot = ConversationSnapshot(
        conversation_id="conv-detail",
        summary="当前围绕课堂参与度进行分析",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_goals": ["生成报告"],
            "confirmed_facts": ["课堂前10分钟举手响应较少"],
            "teaching_issues": ["互动推进不足"],
            "student_signals": ["后排学生多次走神", "前10分钟注意力不稳"],
            "evidence_points": [
                {"type": "observation", "content": "课堂前10分钟举手响应较少"},
                {"type": "observation", "content": "教师提问后等待时间偏短"},
            ],
            "constraints": {
                "audience": "教研组",
                "extra_constraints": ["提纲形式输出", "加入可执行建议"],
            },
        },
        capability=CapabilityPolicy(allow_rag=True, allow_web=False),
    )

    card = StatusCardBuilder().build(snapshot=snapshot, workflow=None, capability=snapshot.capability)

    assert card.student_signals == ["后排学生多次走神", "前10分钟注意力不稳"]
    assert card.evidence_points == ["课堂前10分钟举手响应较少", "教师提问后等待时间偏短"]
    assert card.extra_constraints == ["提纲形式输出", "加入可执行建议"]


def test_status_card_builder_keeps_detail_lists_empty_for_low_state_chat():
    snapshot = ConversationSnapshot(
        conversation_id="conv-empty-detail",
        summary="",
        conversation_memory={},
        active_context={},
        capability=CapabilityPolicy(),
    )

    card = StatusCardBuilder().build(snapshot=snapshot, workflow=None, capability=snapshot.capability)

    assert card.student_signals == []
    assert card.evidence_points == []
    assert card.extra_constraints == []
