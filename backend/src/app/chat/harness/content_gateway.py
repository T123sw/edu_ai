"""Bounded non-thinking structured generation inside the Harness tools."""
from app.chat.model_gateway import ChatModelGateway
from app.chat.runtime.model_registry import build_agent_gateway


class ContentGateway(ChatModelGateway):
    @staticmethod
    def _thinking_params(model_name):
        if str(model_name).lower().startswith('deepseek-v4'):
            return {'thinking': {'type': 'disabled'}}
        return ChatModelGateway._thinking_params(model_name)


def build_content_gateway():
    configured = build_agent_gateway()
    primary, *fallbacks = configured.candidates
    return ContentGateway(**primary, fallbacks=fallbacks)
