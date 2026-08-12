from __future__ import annotations

from app.integrations.websearch.tavily_search import search_tavily


def test_search_tavily_uses_bearer_auth_and_normalizes_results(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "url": "https://docs.python.org/3/tutorial/controlflow.html",
                        "title": "More Control Flow Tools",
                        "content": "Python if, for, break and continue documentation.",
                        "score": 0.91,
                        "published_date": "2026-01-01",
                    }
                ]
            }

    class Client:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, *, json, headers):
            captured.update(url=url, payload=json, headers=headers)
            return Response()

    monkeypatch.setattr("app.integrations.websearch.tavily_search.httpx.Client", Client)

    hits = search_tavily(
        "Python control flow",
        count=4,
        api_key="tvly-test",
        base_url="https://api.tavily.com/",
        timeout=7,
    )

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["headers"]["Authorization"] == "Bearer tvly-test"
    assert captured["payload"]["max_results"] == 4
    assert captured["payload"]["include_raw_content"] is False
    assert hits[0].site == "docs.python.org"
    assert hits[0].raw["score"] == 0.91

