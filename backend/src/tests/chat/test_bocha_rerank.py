from __future__ import annotations

import httpx

from app.integrations.websearch.bocha_rerank import rerank_bocha


def test_rerank_bocha_posts_documents_and_parses_scores(monkeypatch):
    payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(request.read().decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "model": "gte-rerank",
                    "results": [
                        {"index": 2, "relevance_score": 0.91},
                        {"index": 0, "relevance_score": 0.52},
                    ],
                },
            },
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    monkeypatch.setattr(
        "app.integrations.websearch.bocha_rerank.httpx.Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    ranked = rerank_bocha(
        "rag",
        ["doc a", "doc b", "doc c"],
        top_n=2,
        api_key="bocha-test",
        base_url="https://api.bocha.cn",
    )

    compact = payloads[0].replace(" ", "")
    assert '"model":"gte-rerank"' in compact
    assert '"query":"rag"' in compact
    assert '"documents":["doca","docb","docc"]' in compact
    assert '"top_n":2' in compact
    assert [(item.index, item.score) for item in ranked] == [(2, 0.91), (0, 0.52)]
