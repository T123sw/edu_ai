from app.chat.schemas import ChatRequest, ChatResponseV2


def test_chat_request_supports_allow_rag_and_allow_web():
    payload = ChatRequest(question="你好")

    assert payload.allow_rag is False
    assert payload.allow_web is False
    assert payload.selected_doc_ids == []


def test_chat_response_v2_supports_new_top_level_shape():
    payload = ChatResponseV2(
        message={"role": "assistant", "content": "测试回复"},
        conversation={"conversation_id": "conv-1"},
        action={"name": "chat.reply"},
        artifacts=[],
        workflow=None,
        sources=[],
        trace={"path": "fast"},
    )

    assert payload.message["content"] == "测试回复"
    assert payload.trace["path"] == "fast"
