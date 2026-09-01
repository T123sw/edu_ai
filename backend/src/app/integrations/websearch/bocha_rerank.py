from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class RerankResult:
    index: int
    score: float


def rerank_bocha(
    query: str,
    documents: list[str],
    *,
    top_n: int,
    api_key: str,
    base_url: str,
    model: str = "gte-rerank",
    timeout: float = 15.0,
) -> list[RerankResult]:
    if not api_key:
        raise RuntimeError("BOCHA_API_KEY is not configured")
    clean_docs = [str(doc or "").strip() for doc in documents]
    if not clean_docs:
        return []
    payload = {
        "model": model,
        "query": query,
        "documents": clean_docs,
        "top_n": max(1, min(int(top_n or len(clean_docs)), len(clean_docs))),
        "return_documents": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{base_url.rstrip('/')}/v1/rerank", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    body = data.get("data") if isinstance(data.get("data"), dict) else data
    results = body.get("results") if isinstance(body, dict) else []
    results = results or []
    out: list[RerankResult] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        score_value = item.get("relevance_score", item.get("score", 0.0))
        try:
            score = float(score_value)
        except (TypeError, ValueError):
            score = 0.0
        if 0 <= index < len(clean_docs):
            out.append(RerankResult(index=index, score=score))
    return out
