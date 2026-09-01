from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MediaAsset:
    url: str
    alt: str = ""
    caption: str = ""


def extract_image_assets(sources: list[dict[str, Any]]) -> list[MediaAsset]:
    """Convert RAG source dicts with modality=='image' to MediaAsset objects.

    Accepts either raw RAG sources (image_url in metadata) or pre-normalised
    dicts produced by _scrub_response_sources (image_url at top level or in
    metadata).  Deduplicates by URL.
    """
    assets: list[MediaAsset] = []
    seen: set[str] = set()
    for src in list(sources or []):
        source = dict(src or {})
        metadata = dict(source.get("metadata") or {})
        modality = str(
            source.get("modality") or metadata.get("modality") or ""
        ).strip().lower()
        if modality != "image":
            continue
        url = str(
            source.get("image_url") or metadata.get("image_url") or ""
        ).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        content = str(source.get("content") or "").strip()
        assets.append(MediaAsset(url=url, alt=content or "图片", caption=content or ""))
    return assets
