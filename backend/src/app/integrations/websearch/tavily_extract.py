from __future__ import annotations

import httpx

from .models import ExtractResult


def extract_tavily(
    urls: list[str],
    *,
    depth: str,
    timeout: int,
    api_key: str,
    base_url: str,
    max_urls: int = 20,
) -> list[ExtractResult]:
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    all_results: list[ExtractResult] = []
    for chunk in _chunks([u for u in urls if u], max(1, min(int(max_urls or 20), 20))):
        payload = {
            "urls": chunk,
            "extract_depth": depth,
            "format": "markdown",
            "timeout": timeout,
            "include_images": True,
            "include_favicon": True,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{base_url.rstrip('/')}/extract", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        for item in data.get("results") or []:
            all_results.append(
                ExtractResult(
                    url=str(item.get("url") or ""),
                    content=str(item.get("raw_content") or item.get("content") or ""),
                    status="success",
                    images=_extract_images(item),
                    favicon=str(item.get("favicon") or "").strip() or None,
                    raw=item,
                )
            )
        for item in data.get("failed_results") or []:
            all_results.append(
                ExtractResult(
                    url=str(item.get("url") or ""),
                    content="",
                    status="failed",
                    error=str(item.get("error") or "extract_failed"),
                    images=_extract_images(item),
                    favicon=str(item.get("favicon") or "").strip() or None,
                    raw=item,
                )
            )
    return all_results


def _chunks(values: list[str], size: int):
    for i in range(0, len(values), size):
        yield values[i : i + size]


def _extract_images(item: dict) -> list[str]:
    values = item.get("images") or []
    if isinstance(values, str):
        values = [values]
    out: list[str] = []
    for image in values if isinstance(values, list) else []:
        if isinstance(image, str):
            url = image
        elif isinstance(image, dict):
            url = image.get("url") or image.get("src") or image.get("contentUrl") or image.get("image_url")
        else:
            url = ""
        url = str(url or "").strip()
        if url and url not in out:
            out.append(url)
    return out
