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
                    raw=item,
                )
            )
    return all_results


def _chunks(values: list[str], size: int):
    for i in range(0, len(values), size):
        yield values[i : i + size]
