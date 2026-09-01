"""Image search provider abstraction (Phase 6-A).

Providers normalize external image search APIs into a uniform raw-dict shape.
The handler (image_search.py) applies heuristic filtering and normalization on top.

Provider raw-dict shape (best-effort fields, all optional except url):
    {
        "url":          str,     # direct image URL
        "source_page":  str,     # URL of page hosting the image
        "title":        str,
        "width":        int,
        "height":       int,
        "thumbnail":    str,
        "license":      str | None,
        "_provider":    str,     # provider name, set by provider implementation
    }
"""
from __future__ import annotations

import os
from typing import Protocol


class ImageSearchProvider(Protocol):
    name: str

    def search(
        self,
        *,
        query: str,
        count: int,
        style: str,
        safe: bool,
        license_: str,
        owner: str | None,
    ) -> list[dict]:
        """Return up to ~3x count raw image dicts. Handler trims and filters."""
        ...


def build_default_image_search_provider() -> ImageSearchProvider | None:
    """Construct provider per env. Returns None when not configured.

    A None provider does not fail application startup — it surfaces as a
    provider_not_configured error only when a tool call is actually attempted.
    """
    name = (os.getenv("IMAGE_SEARCH_PROVIDER") or "").strip().lower()
    if not name:
        return None
    if name == "bocha":
        from app.chat.runtime.agent_tools.handlers.providers.bocha_provider import (
            BochaImageSearchProvider,
        )

        api_key = (os.getenv("BOCHA_API_KEY") or "").strip()
        base = (os.getenv("BOCHA_BASE_URL") or "https://api.bocha.cn").rstrip("/")
        if not api_key or not base:
            return None
        try:
            timeout = float(os.getenv("IMAGE_SEARCH_TIMEOUT_S", "8") or "8")
        except ValueError:
            timeout = 8.0
        return BochaImageSearchProvider(api_key=api_key, base_url=base, timeout=timeout)
    return None
