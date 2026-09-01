from app.chat.application.response_builder import (
    build_http_response,
    build_legacy_sse_frames,
    build_sse_events,
)


def test_build_http_response_returns_v2_shape():
    result = {
        "message": {"role": "assistant", "content": "测试回复"},
        "conversation": {"conversation_id": "conv-1"},
        "action": {"name": "chat.reply"},
        "artifacts": [],
        "workflow": None,
        "sources": [],
        "trace": {"path": "fast"},
    }

    response = build_http_response(result)

    assert response["message"]["content"] == "测试回复"
    assert response["trace"]["path"] == "fast"


def test_build_sse_events_emits_trace_message_and_done():
    result = {
        "message": {"role": "assistant", "content": "测试回复"},
        "conversation": {"conversation_id": "conv-1"},
        "action": {"name": "chat.reply"},
        "artifacts": [],
        "workflow": None,
        "sources": [],
        "trace": {"path": "fast"},
    }

    events = list(build_sse_events(result))

    assert events[0]["event"] == "trace.meta"
    assert events[1]["event"] == "message.delta"
    assert events[-1]["event"] == "done"


def test_build_legacy_sse_frames_serializes_meta_status_delta_and_done():
    meta = {"conversation_id": "conv-1"}
    stream = [
        {"type": "meta", "payload": {"path": "fast"}},
        {"type": "status", "stage": "chat", "node": "fast_runtime"},
        {"type": "delta", "delta": "你好"},
        {"type": "done"},
    ]

    frames = list(build_legacy_sse_frames(meta, stream))

    assert frames[0].startswith("event: meta")
    assert any("event: status" in frame for frame in frames)
    assert any("event: delta" in frame for frame in frames)
    assert frames[-1] == "event: done\ndata: [DONE]\n\n"


def test_build_legacy_sse_frames_can_emit_v2_events_in_parallel():
    meta = {"conversation_id": "conv-1"}
    stream = [
        {"type": "meta", "payload": {"path": "fast"}},
        {"type": "status", "stage": "confirming", "node": "report_runtime"},
        {"type": "delta", "delta": "你好"},
        {"type": "done"},
    ]

    frames = list(build_legacy_sse_frames(meta, stream, include_v2=True))

    assert any("event: meta" in frame for frame in frames)
    assert any("event: trace.meta" in frame for frame in frames)
    assert any("event: status" in frame for frame in frames)
    assert any("event: workflow.status" in frame for frame in frames)
    assert any("event: delta" in frame for frame in frames)
    assert any("event: message.delta" in frame for frame in frames)
