from __future__ import annotations

import json


def build_http_response(result: dict) -> dict:
    return result


def build_sse_events(result: dict):
    yield {"event": "trace.meta", "data": {"path": result["trace"]["path"]}}
    if result.get("workflow"):
        yield {"event": "workflow.status", "data": result["workflow"]}
    yield {"event": "message.delta", "data": {"delta": result["message"]["content"]}}
    yield {"event": "done", "data": "[DONE]"}


def build_legacy_sse_frames(meta: dict, stream, *, include_v2: bool = False):
    yield f"event: meta\ndata: {json.dumps(meta, ensure_ascii=False)}\n\n"

    delta_count = 0
    for event in stream:
        event_type = event.get("type")
        if event_type == "status":
            payload = {"stage": event.get("stage"), "node": event.get("node")}
            yield f"event: status\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if include_v2:
                yield f"event: workflow.status\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        elif event_type == "meta":
            payload = event.get("payload") or {}
            yield f"event: meta\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if include_v2:
                yield f"event: trace.meta\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        elif event_type == "delta":
            delta = event.get("delta", "")
            delta_count += 1
            payload = json.dumps({"delta": delta}, ensure_ascii=False)
            yield f"event: delta\ndata: {payload}\n\n"
            if include_v2:
                yield f"event: message.delta\ndata: {payload}\n\n"
        elif event_type == "done":
            yield "event: done\ndata: [DONE]\n\n"

    if delta_count == 0:
        yield "event: done\ndata: [DONE]\n\n"
