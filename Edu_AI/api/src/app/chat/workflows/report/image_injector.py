"""Report image injection — P3-B.

Injects RAG-retrieved images into report Markdown as ![alt](url) references.
Mirrors rag_image_bridge.py from the PPT pipeline.
"""
from __future__ import annotations

import re
from typing import Any


def inject_images_into_report(
    report_markdown: str,
    image_assets: list,
    max_images: int = 3,
) -> str:
    """Insert Markdown image references after selected section headings.

    Prefers ### headings (section level); falls back to ## (chapter level).
    Images are distributed evenly across eligible headings.
    """
    if not image_assets or not report_markdown or max_images <= 0:
        return report_markdown

    assets = list(image_assets[:max_images])

    # Try ### headings first, fall back to ##
    heading_pattern = r"^### .+$"
    positions = [m.start() for m in re.finditer(heading_pattern, report_markdown, re.MULTILINE)]
    if not positions:
        heading_pattern = r"^## .+$"
        positions = [m.start() for m in re.finditer(heading_pattern, report_markdown, re.MULTILINE)]

    if not positions:
        return report_markdown

    n_inject = min(len(assets), len(positions))
    if n_inject >= len(positions):
        targets = positions[:n_inject]
    else:
        step = len(positions) / n_inject
        targets = [positions[int(i * step)] for i in range(n_inject)]

    result = report_markdown
    offset = 0
    for i, pos in enumerate(targets):
        actual_pos = pos + offset
        newline_pos = result.find("\n", actual_pos)
        insert_at = (newline_pos + 1) if newline_pos != -1 else len(result)

        asset = assets[i]
        alt = str(asset.alt or "图片").strip() or "图片"
        img_block = f"\n![{alt}]({asset.url})\n\n"

        result = result[:insert_at] + img_block + result[insert_at:]
        offset += len(img_block)

    return result


def fetch_report_image_assets(
    *,
    allow_rag: bool,
    selected_doc_ids: list[str],
    owner: str | None,
    query_text: str,
    top_k: int = 10,
) -> list:
    """Query RAG for image-type chunks. Returns list[MediaAsset], empty on any error."""
    if not allow_rag or not selected_doc_ids or not query_text:
        return []
    try:
        from app.chat.application.knowledge_base_summary_provider import KnowledgeBaseSummaryProvider
        from app.chat.workflows.ppt.rag_image_bridge import extract_image_assets

        provider = KnowledgeBaseSummaryProvider()
        image_sources = provider.get_document_image_sources(
            selected_doc_ids=list(selected_doc_ids),
            owner=owner,
            query_text=str(query_text or "图片"),
            top_k=top_k,
        )
        return extract_image_assets(list(image_sources or []))
    except Exception:
        return []


def inject_report_images_from_rag(
    report_content: str,
    *,
    allow_rag: bool,
    selected_doc_ids: list[str],
    owner: str | None,
    query_text: str,
    max_images: int = 3,
) -> str:
    """Convenience wrapper: fetch assets then inject. Always returns valid markdown."""
    if not report_content:
        return report_content
    try:
        assets = fetch_report_image_assets(
            allow_rag=allow_rag,
            selected_doc_ids=selected_doc_ids,
            owner=owner,
            query_text=query_text,
        )
        if not assets:
            return report_content
        return inject_images_into_report(report_content, assets, max_images=max_images)
    except Exception:
        return report_content
