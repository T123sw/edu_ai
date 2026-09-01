from __future__ import annotations

from typing import Any

import httpx

from .models import WebSearchError, WebSearchHit


def search_bocha(
    query: str,
    *,
    count: int,
    freshness: str,
    api_key: str,
    base_url: str,
    timeout: float = 15.0,
) -> list[WebSearchHit]:
    if not api_key:
        raise WebSearchError("missing_api_key", "BOCHA_API_KEY is not configured")
    payload = {
        "query": query,
        "freshness": freshness,
        "summary": True,
        "count": max(1, min(int(count or 10), 50)),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{base_url.rstrip('/')}/v1/web-search", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    code = str(data.get("code", "200"))
    if code not in {"200", "0"}:
        raise WebSearchError(code, str(data.get("message") or data.get("msg") or "bocha_search_failed"), data.get("log_id"))

    pages = (((data.get("data") or {}).get("webPages") or {}).get("value") or [])
    hits: list[WebSearchHit] = []
    for item in pages:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        hits.append(
            WebSearchHit(
                url=url,
                title=str(item.get("name") or item.get("title") or url).strip(),
                content=str(item.get("summary") or item.get("snippet") or "").strip(),
                date=item.get("datePublished") or item.get("dateLastCrawled"),
                site=item.get("siteName"),
                images=_extract_images(item),
                raw=item,
            )
        )
    return hits


def _extract_images(item: dict[str, Any]) -> list[str]:
    images = item.get("images") or []
    if isinstance(images, dict):
        images = images.get("value") or []
    if isinstance(images, str):
        return [images]
    out: list[str] = []
    for img in images if isinstance(images, list) else []:
        if isinstance(img, str):
            out.append(img)
        elif isinstance(img, dict):
            url = img.get("contentUrl") or img.get("imageUrl") or img.get("url") or img.get("thumbnailUrl")
            if url:
                out.append(str(url))
    return out
