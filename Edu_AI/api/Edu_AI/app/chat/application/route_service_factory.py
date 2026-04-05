from __future__ import annotations

from app.chat.application.route_feature_flags import load_route_feature_flags


def build_default_route_chat_service():
    from app.chat.application.route_chat_service import RouteChatService
    from app.chat.legacy.legacy_chat_runtime import LegacyChatRuntime
    from app.chat.orchestrator.llm_enhancement_provider import LLMEnhancementProvider
    from app.chat.orchestrator.llm_enhancement_router import LLMEnhancementRouter
    from app.chat.runtime.model_registry import build_default_gateway

    flags = load_route_feature_flags()
    legacy_service = LegacyChatRuntime()
    enhancement_router = None
    if flags.enable_llm_enhancement:
        enhancement_router = LLMEnhancementRouter(
            enabled=True,
            enhancer=LLMEnhancementProvider(model_gateway=build_default_gateway()),
        )
    return RouteChatService(
        legacy_service=legacy_service,
        enable_new_chat=flags.enable_new_chat,
        enable_fast_runtime=flags.enable_fast_runtime,
        enable_report_workflow=flags.enable_report_workflow,
        enforce_capability_policy=flags.enforce_capability_policy,
        enhancement_router=enhancement_router,
        enhancement_trace_enabled=flags.trace_llm_enhancement,
    )
