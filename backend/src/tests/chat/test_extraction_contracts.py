from app.chat.domain.extraction_candidate import ExtractionCandidate
from app.chat.domain.extraction_trigger import ExtractionTrigger


def test_extraction_candidate_supports_structured_payload_and_defaults():
    candidate = ExtractionCandidate(
        field="evidence_points",
        value=[
            {
                "type": "observation",
                "content": "前10分钟举手响应较少",
                "source_type": "assistant_message",
                "source_message_ids": ["msg-1"],
                "confidence": "medium",
            }
        ],
        source="llm",
    )

    assert candidate.field == "evidence_points"
    assert candidate.operation == "merge"
    assert candidate.confidence == "medium"
    assert candidate.value[0]["source_message_ids"] == ["msg-1"]


def test_extraction_trigger_carries_event_and_request_context():
    trigger = ExtractionTrigger(
        event="reply.completed",
        conversation_id="conv-1",
        question="请根据上面的课堂分析整理一份报告",
        action_name="chat.reply",
        workflow_type="report",
    )

    assert trigger.event == "reply.completed"
    assert trigger.conversation_id == "conv-1"
    assert trigger.workflow_type == "report"
    assert "课堂分析" in trigger.question
