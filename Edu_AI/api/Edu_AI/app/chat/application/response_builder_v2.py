from __future__ import annotations


def build_v2_success_response(
    *,
    message: str,
    conversation_id: str,
    action_name: str,
    trace_path: str,
    workflow=None,
    artifacts=None,
    sources=None,
    trace=None,
    status_card=None,
):
    merged_trace = {"path": trace_path, **(trace or {})}
    return {
        "message": {"role": "assistant", "content": message},
        "conversation": {"conversation_id": conversation_id},
        "action": {"name": action_name},
        "workflow": workflow,
        "artifacts": artifacts or [],
        "sources": sources or [],
        "trace": merged_trace,
        "status_card": status_card,
    }


def build_v2_error_response(
    *,
    code: str,
    message: str,
    conversation_id: str,
    trace_path: str,
    retryable: bool,
):
    return {
        "error": {"code": code, "message": message, "retryable": retryable},
        "conversation": {"conversation_id": conversation_id},
        "trace": {"path": trace_path},
    }
