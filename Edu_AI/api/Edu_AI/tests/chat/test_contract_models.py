from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.contracts import (
    ArtifactPayload,
    ChatRequestV2,
    MessagePayload,
    SseEvent,
    WorkflowPayload,
)


def test_chat_request_v2_uses_capability_defaults():
    request = ChatRequestV2(question="你好")

    assert request.question == "你好"
    assert isinstance(request.capability, CapabilityPolicy)
    assert request.capability.allow_rag is False
    assert request.capability.allow_web is False


def test_payload_models_capture_structured_output():
    message = MessagePayload(role="assistant", content="测试回复")
    workflow = WorkflowPayload(type="report", status="running", stage="collecting")
    artifact = ArtifactPayload(
        artifact_id="artifact-1",
        artifact_type="report",
        title="报告标题",
        content="正文",
    )
    event = SseEvent(event="message.delta", data={"delta": "片段"})

    assert message.content == "测试回复"
    assert workflow.stage == "collecting"
    assert artifact.artifact_type == "report"
    assert event.event == "message.delta"
