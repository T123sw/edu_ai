from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from .models import WebSearchError, WebSearchHit


def search_tavily(
    query: str,
    *,
    count: int,
    api_key: str,
    base_url: str,
    timeout: float = 20.0,
    search_depth: str = "basic",
) -> list[WebSearchHit]:
    """Search Tavily using its HTTP API and normalize results for DeepSearch."""
    if not api_key:
        raise WebSearchError("missing_api_key", "TAVILY_API_KEY is not configured")

    payload = {
        "query": str(query or "").strip(),
        "topic": "general",
        "search_depth": search_depth if search_depth in {"basic", "advanced"} else "basic",
        "max_results": max(1, min(int(count or 5), 20)),
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{base_url.rstrip('/')}/search",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    hits: list[WebSearchHit] = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        hostname = (urlsplit(url).hostname or "").strip()
        hits.append(
            WebSearchHit(
                url=url,
                title=str(item.get("title") or url).strip(),
                content=str(item.get("content") or "").strip(),
                date=str(item.get("published_date") or "").strip() or None,
                site=hostname or None,
                raw=item,
            )
        )
    return hits

