from __future__ import annotations

from core.config import Config

from app.chat.model_gateway import ChatModelGateway


def _to_gateway_candidate(model: dict) -> dict:
    return {
        "api_base": model.get("api_base") or Config.REMOTE_MODEL_API_BASE,
        "api_key": model.get("api_key") or Config.REMOTE_MODEL_API_KEY,
        "model_name": model.get("model_name") or model.get("id") or Config.LLM_MODEL,
    }


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
    )
