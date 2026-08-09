from __future__ import annotations

from core.config import Config

from app.chat.model_gateway import ChatModelGateway


def _to_gateway_candidate(model: dict) -> dict:
    return {
        "api_base": model.get("api_base") or Config.REMOTE_MODEL_API_BASE,
        "api_key": model.get("api_key") or Config.REMOTE_MODEL_API_KEY,
        "model_name": model.get("model_name") or model.get("id") or Config.LLM_MODEL,
    }


def _tool_capable_fallbacks() -> list[dict]:
    """Return configured providers that can continue Agent tool calling.

    Planner/executor gateways used to have no fallbacks, so a configured but
    unavailable primary provider silently pushed resource requests onto the
    direct-answer path.  Keep the configured planner model first, followed by
    the independent DeepSeek-compatible channel.
    """
    candidates = [_to_gateway_candidate(Config.get_planner_model())]
    if str(Config.REMOTE_MODEL_API_KEY or "").strip():
        candidates.append(
            {
                "api_base": Config.REMOTE_MODEL_API_BASE,
                "api_key": Config.REMOTE_MODEL_API_KEY,
                "model_name": "deepseek-chat",
            }
        )
    return candidates


def build_default_gateway(model_id: str | None = None) -> ChatModelGateway:
    model = Config.get_llm_model(model_id) if model_id else Config.get_deep_model()
    fallbacks = []
    if model_id is None:
        for fallback_model in (
            Config.get_vision_model(),
            Config.get_planner_model(),
        ):
            fallbacks.append(_to_gateway_candidate(fallback_model))

    candidate = _to_gateway_candidate(model)
    return ChatModelGateway(
        api_base=candidate["api_base"],
        api_key=candidate["api_key"],
        model_name=candidate["model_name"],
        fallbacks=fallbacks,
    )


def build_agent_gateway() -> ChatModelGateway:
    candidate = _to_gateway_candidate(Config.get_agent_model())
    return ChatModelGateway(
        api_base=candidate["api_base"],
        api_key=candidate["api_key"],
        model_name=candidate["model_name"],
        fallbacks=_tool_capable_fallbacks(),
    )


def build_planner_gateway() -> ChatModelGateway:
    """规划专用网关：使用 Qwen (阿里百炼)，响应快、成本低。"""
    return ChatModelGateway(
        api_base=Config.QWEN_BASE_URL,
        api_key=Config.QWEN_API_KEY,
        model_name=Config.VISION_MODEL_ID,
        fallbacks=_tool_capable_fallbacks(),
    )


def build_vision_gateway() -> ChatModelGateway:
    """视觉反思网关：使用多模态模型检查图片质量。"""
    candidate = _to_gateway_candidate(Config.get_vision_model())
    return ChatModelGateway(
        api_base=candidate["api_base"],
        api_key=candidate["api_key"],
        model_name=candidate["model_name"],
    )
