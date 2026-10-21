"""Bounded non-thinking structured generation inside the Harness tools."""
from app.chat.model_gateway import ChatModelGateway
from app.chat.runtime.model_registry import build_agent_gateway


class ContentGateway(ChatModelGateway):
    def chat_json(self, messages, temperature=0.2, max_tokens=12000):
        """Request a JSON object at the provider boundary, not only in prose."""
        return super().chat(messages, temperature=temperature, max_tokens=max_tokens,
                            response_format={'type': 'json_object'})

    @staticmethod
    def _thinking_params(model_name):
        if str(model_name).lower().startswith('deepseek-v4'):
            return {'thinking': {'type': 'disabled'}}
        return ChatModelGateway._thinking_params(model_name)


def build_content_gateway():
    configured = build_agent_gateway()
    primary, *fallbacks = configured.candidates
    return ContentGateway(**primary, fallbacks=fallbacks)
