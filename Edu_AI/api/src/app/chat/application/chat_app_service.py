from __future__ import annotations


class ChatAppService:
    def __init__(self, *, normalizer, orchestrator, response_builder):
        self.normalizer = normalizer
        self.orchestrator = orchestrator
        self.response_builder = response_builder

    def chat(self, payload):
        request = self.normalizer(payload)
        result = self.orchestrator.dispatch(request)
        return self.response_builder.build_http_response(result)

