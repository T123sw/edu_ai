from __future__ import annotations

import os
from dataclasses import dataclass


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class RouteFeatureFlags:
    enable_new_chat: bool
    enable_fast_runtime: bool
    enable_report_workflow: bool
    enforce_capability_policy: bool
    enable_sse_v2_events: bool
    enable_llm_enhancement: bool
    trace_llm_enhancement: bool


def load_route_feature_flags() -> RouteFeatureFlags:
    return RouteFeatureFlags(
        enable_new_chat=_flag("CHAT_USE_NEW_ORCHESTRATOR", "1"),
        enable_fast_runtime=_flag("CHAT_USE_FAST_RUNTIME", "1"),
        enable_report_workflow=_flag("CHAT_USE_REPORT_WORKFLOW_V2", "0"),
        enforce_capability_policy=_flag("CHAT_CAPABILITY_POLICY_ENFORCED", "0"),
        enable_sse_v2_events=_flag("CHAT_SSE_V2_EVENTS", "0"),
        enable_llm_enhancement=_flag("CHAT_USE_LLM_ENHANCEMENT", "0"),
        trace_llm_enhancement=_flag("CHAT_TRACE_LLM_ENHANCEMENT", "0"),
    )
