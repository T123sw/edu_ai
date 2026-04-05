from app.chat.application.response_builder_v2 import (
    build_v2_error_response,
    build_v2_success_response,
)


def test_build_v2_success_response_returns_stable_shape():
    payload = build_v2_success_response(
        message="ok",
        conversation_id="conv-1",
        action_name="chat.reply",
        trace_path="fast",
    )

    assert payload["message"]["content"] == "ok"
    assert payload["conversation"]["conversation_id"] == "conv-1"
    assert payload["action"]["name"] == "chat.reply"
    assert payload["trace"]["path"] == "fast"


def test_build_v2_success_response_supports_status_card():
    payload = build_v2_success_response(
        message="ok",
        conversation_id="conv-1",
        action_name="chat.reply",
        trace_path="fast",
        status_card={"mode": "chat", "status_label": "普通对话", "source_labels": ["当前会话"]},
    )

    assert payload["status_card"]["mode"] == "chat"
    assert payload["status_card"]["status_label"] == "普通对话"


def test_build_v2_error_response_returns_error_shape():
    payload = build_v2_error_response(
        code="capability_denied",
        message="forbidden",
        conversation_id="conv-1",
        trace_path="workflow",
        retryable=False,
    )

    assert payload["error"]["code"] == "capability_denied"
    assert payload["error"]["retryable"] is False
    assert payload["trace"]["path"] == "workflow"
