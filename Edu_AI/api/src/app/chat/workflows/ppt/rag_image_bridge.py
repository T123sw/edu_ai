from __future__ import annotations

import re
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


def _is_content_slide(slide: str) -> bool:
    return bool(re.search(r"^\s*-\s*Role:\s*content\s*$", slide, re.MULTILINE))


def _has_media_block(slide: str) -> bool:
    return bool(re.search(r"^\s*-\s*Media:\s*$", slide, re.MULTILINE))


def _inject_media_into_slide(slide: str, asset: MediaAsset) -> str:
    """Append a Media block to a slide's Blocks section, before Notes if present."""
    lines = [
        "- Media:",
        "  - Kind: image",
        f"  - URL: {asset.url}",
        f"  - Alt: {asset.alt or '图片'}",
    ]
    if asset.caption:
        lines.append(f"  - Caption: {asset.caption}")
    media_text = "\n".join(lines)

    match = re.search(r"\n(### Notes\b)", slide)
    if match:
        return slide[: match.start()] + f"\n{media_text}\n" + slide[match.start() :]

    return slide.rstrip() + f"\n{media_text}\n"


def inject_media_blocks(
    content_markdown: str,
    image_assets: list[MediaAsset],
    max_images: int = 3,
) -> str:
    """Inject Media blocks into content slides, distributing images evenly.

    Skips slides with non-content roles (cover, toc, section, thanks) and slides
    that already contain a Media block.  At most max_images images are injected.
    """
    if not image_assets or not content_markdown or max_images <= 0:
        return content_markdown

    assets = list(image_assets[:max_images])
    slides = re.split(r"\n---\n", content_markdown)

    eligible = [
        i
        for i, slide in enumerate(slides)
        if _is_content_slide(slide) and not _has_media_block(slide)
    ]

    if not eligible:
        return content_markdown

    n_inject = min(len(assets), len(eligible))
    if n_inject >= len(eligible):
        targets = eligible[:n_inject]
    else:
        step = len(eligible) / n_inject
        targets = [eligible[int(i * step)] for i in range(n_inject)]

    target_map = {idx: assets[pos] for pos, idx in enumerate(targets)}

    for slide_idx, asset in target_map.items():
        slides[slide_idx] = _inject_media_into_slide(slides[slide_idx], asset)

    return "\n---\n".join(slides)
