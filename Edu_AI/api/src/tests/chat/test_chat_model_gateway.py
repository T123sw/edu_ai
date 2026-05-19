import requests

from app.chat.model_gateway import ChatModelGateway


class _FakeResponse:
    def __init__(self, payload, status_code=200, text="OK"):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


class _FakeStreamResponse:
    def __init__(self, lines, status_code=200, text="OK"):
        self._lines = lines
        self.status_code = status_code
        self.text = text

    def iter_lines(self, decode_unicode=False):
        return iter(self._lines)


def test_chat_gateway_falls_back_to_next_provider_on_request_error(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None, stream=False):
        calls.append({"url": url, "model": json["model"], "stream": stream})
        if len(calls) == 1:
            raise requests.exceptions.SSLError("ssl eof")
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "fallback answer",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.chat.model_gateway.requests.post", fake_post)

    gateway = ChatModelGateway(
        api_base="https://primary.example.com",
        api_key="primary-key",
        model_name="primary-model",
        fallbacks=[
            {
                "api_base": "https://backup.example.com",
                "api_key": "backup-key",
                "model_name": "backup-model",
            }
        ],
    )

    result = gateway.chat([{"role": "user", "content": "hello"}])

    assert result == "fallback answer"
    assert [call["model"] for call in calls] == ["primary-model", "backup-model"]
    assert calls[0]["url"].endswith("/v1/chat/completions")
    assert calls[1]["url"].endswith("/v1/chat/completions")


def test_stream_chat_with_tools_yields_text_and_accumulated_tool_call(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None, stream=False):
        assert stream is True
        assert json["tools"][0]["function"]["name"] == "generate_quiz"
        return _FakeStreamResponse(
            [
                b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":null}]}',
                b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"generate_quiz","arguments":"{\\"subject\\""}}]},"finish_reason":null}]}',
                b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":": \\"Python\\"}"}}]},"finish_reason":"tool_calls"}]}',
                b"data: [DONE]",
            ]
        )

    monkeypatch.setattr("app.chat.model_gateway.requests.post", fake_post)

    gateway = ChatModelGateway(
        api_base="https://primary.example.com",
        api_key="primary-key",
        model_name="primary-model",
    )

    events = list(
        gateway.stream_chat_with_tools(
            [{"role": "user", "content": "出题"}],
            [{"type": "function", "function": {"name": "generate_quiz", "parameters": {"type": "object"}}}],
        )
    )

    assert events == [
        {"type": "text_delta", "content": "ok"},
        {"type": "tool_calls", "calls": [{"id": "call_1", "name": "generate_quiz", "args": {"subject": "Python"}}]},
        {"type": "done"},
    ]
