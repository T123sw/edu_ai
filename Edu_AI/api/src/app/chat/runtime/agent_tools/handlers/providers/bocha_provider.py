"""Bocha image search provider.

Uses Bocha Web Search and normalizes image-like response fields into the
raw dict shape consumed by image_search.py.
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx


class BochaImageSearchProvider:
    name = "bocha"

    def __init__(self, *, api_key: str, base_url: str, timeout: float = 8.0):
        self._api_key = api_key.strip()
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def search(
        self,
        *,
        query: str,
        count: int,
        style: str,
        safe: bool,  # noqa: ARG002 - reserved for Bocha options when available.
        license_: str,  # noqa: ARG002 - Bocha web search has no license filter.
        owner: str | None,  # noqa: ARG002 - reserved for future per-tenant quotas.
    ) -> list[dict]:
        recall_count = int(os.getenv("BOCHA_IMAGE_SEARCH_RECALL_COUNT", "50") or "50")
        payload = {
            "query": _build_query(query, style),
            "count": max(1, min(max(count * 3, recall_count), 50)),
            "summary": True,
            "includeImages": True,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(f"{self._base}/v1/web-search", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        if str(data.get("code", "200")) not in {"200", "0"}:
            message = data.get("message") or data.get("msg") or "bocha_image_search_failed"
            raise RuntimeError(str(message))

        return _extract_images(data, count=max(count * 3, recall_count))


def _build_query(query: str, style: str) -> str:
    suffix = {
        "diagram": " diagram OR flowchart OR architecture",
        "chart": " chart OR graph OR plot",
        "real": " photo OR photograph",
        "any": "",
    }.get(style, "")
    return query + suffix


def _extract_images(data: dict, *, count: int) -> list[dict]:
    root = data.get("data") if isinstance(data.get("data"), dict) else {}
    items: list[dict] = []

    images = _as_list(root.get("images"))
    if isinstance(root.get("images"), dict):
        images.extend(_as_list(root.get("images", {}).get("value")))
    for item in images:
        img = _normalize_image_item(item, fallback_page={})
        if img:
            items.append(img)

    pages = root.get("webPages") or {}
    for page in _as_list(pages.get("value") if isinstance(pages, dict) else pages):
        page_images = []
        page_images.extend(_as_list(page.get("images")))
        page_images.extend(_as_list(page.get("image")))
        for key in ("thumbnail", "thumbnailUrl", "siteIcon"):
            if page.get(key):
                page_images.append({key: page.get(key)})
        for item in page_images:
            img = _normalize_image_item(item, fallback_page=page)
            if img:
                items.append(img)

    out: list[dict] = []
    seen: set[str] = set()
    for img in items:
        url = img.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(img)
        if len(out) >= count:
            break
    return out


def _normalize_image_item(item: Any, *, fallback_page: dict) -> dict | None:
    if isinstance(item, str):
        item = {"url": item}
    if not isinstance(item, dict):
        return None

    url = _first_str(
        item,
        "contentUrl",
        "imageUrl",
        "imgUrl",
        "url",
        "thumbnailUrl",
        "thumbnail",
    )
    if not url:
        return None

    source_page = _first_str(
        item,
        "hostPageUrl",
        "sourcePage",
        "sourceUrl",
        "webpageUrl",
        "pageUrl",
    ) or str(fallback_page.get("url") or "")
    title = _first_str(item, "name", "title", "caption") or str(
        fallback_page.get("name") or fallback_page.get("title") or ""
    )
    width, height = _dimensions(item)
    return {
        "url": url,
        "source_page": source_page,
        "title": title.strip(),
        "width": width,
        "height": height,
        "thumbnail": _first_str(item, "thumbnailUrl", "thumbnail") or url,
        "license": None,
        "_provider": "bocha",
    }


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _first_str(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _dimensions(item: dict) -> tuple[int, int]:
    width = _safe_int(item.get("width"))
    height = _safe_int(item.get("height"))
    if width and height:
        return width, height

    resolution = str(item.get("resolution") or item.get("size") or "")
    match = re.search(r"(\d{2,5})\s*[x×]\s*(\d{2,5})", resolution)
    if match:
        return _safe_int(match.group(1)), _safe_int(match.group(2))
    return width, height


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
