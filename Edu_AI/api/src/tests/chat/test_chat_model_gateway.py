import requests

from app.chat.model_gateway import ChatModelGateway


class _FakeResponse:
    def __init__(self, payload, status_code=200, text="OK"):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


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
