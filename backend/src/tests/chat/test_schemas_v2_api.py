from pydantic import ValidationError

from app.chat.api.schemas_v2 import (
    ChatErrorResponseV2,
    ChatReplyRequestV2,
    ChatReportRequestV2,
    ChatResponseV2,
)


def test_reply_request_v2_defaults_disable_capabilities():
    payload = ChatReplyRequestV2(question="hello")

    assert payload.allow_rag is False
    assert payload.allow_web is False
    assert payload.selected_doc_ids == []


def test_report_request_v2_allows_nullable_report_config():
    payload = ChatReportRequestV2(question="generate report", report_config=None)

    assert payload.report_config is None


def test_chat_response_v2_requires_message_action_and_trace():
    payload = ChatResponseV2(
        message={"role": "assistant", "content": "ok"},
        conversation={"conversation_id": "conv-1"},
        action={"name": "chat.reply"},
        artifacts=[],
        sources=[],
        trace={"path": "fast"},
        status_card={"mode": "chat", "status_label": "普通对话", "source_labels": ["当前会话"]},
    )

    assert payload.trace.path == "fast"
    assert payload.status_card.mode == "chat"


def test_chat_error_response_v2_requires_error_code_and_message():
    payload = ChatErrorResponseV2(
        error={"code": "invalid_request", "message": "bad", "retryable": False},
        conversation={"conversation_id": "conv-1"},
        trace={"path": "fast"},
    )

    assert payload.error["code"] == "invalid_request"
    assert payload.trace.path == "fast"


def test_chat_response_v2_rejects_unknown_trace_path():
    try:
        ChatResponseV2(
            message={"role": "assistant", "content": "ok"},
            conversation={"conversation_id": "conv-1"},
            action={"name": "chat.reply"},
            artifacts=[],
            sources=[],
            trace={"path": "unknown"},
        )
    except ValidationError as exc:
        assert "trace" in str(exc)
    else:
        raise AssertionError("expected ValidationError")
