from __future__ import annotations

import httpx

from app.integrations.websearch.tavily_extract import extract_tavily


def test_extract_tavily_requests_images_and_parses_image_urls(monkeypatch):
    calls = []
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read().decode("utf-8")
        calls.append(payload)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.com/a",
                        "raw_content": "full markdown",
                        "images": [
                            "https://example.com/a.png",
                            {"url": "https://example.com/b.png"},
                        ],
                        "favicon": "https://example.com/favicon.ico",
                    }
                ],
                "failed_results": [],
            },
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "app.integrations.websearch.tavily_extract.httpx.Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    results = extract_tavily(
        ["https://example.com/a"],
        depth="advanced",
        timeout=10,
        api_key="tvly-test",
        base_url="https://api.tavily.com",
    )

    assert '"include_images":true' in calls[0].replace(" ", "")
    assert '"include_favicon":true' in calls[0].replace(" ", "")
    assert '"extract_depth":"advanced"' in calls[0].replace(" ", "")
    assert results[0].images == ["https://example.com/a.png", "https://example.com/b.png"]
    assert results[0].favicon == "https://example.com/favicon.ico"
