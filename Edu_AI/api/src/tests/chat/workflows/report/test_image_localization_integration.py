"""Phase 6-A.2 integration: image_downloader ↔ image_injector ↔ generate_report.

These tests verify the async parallel-download flow: localization is fired
before LLM generation and joined after, with localized URLs replacing the
external ones in the final Markdown.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.chat.workflows.report.image_downloader import (
    DownloadFailure,
    LocalizedAsset,
    resolve_async_localization,
    start_async_localization,
)
from app.chat.workflows.report.image_injector import inject_images_into_report


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def _png_response(_req):
    return httpx.Response(
        200, content=PNG_BYTES,
        headers={"content-type": "image/png", "content-length": str(len(PNG_BYTES))},
    )


def _patch_httpx(handler):
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def _mock_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=transport, **kwargs)

    return patch("app.chat.workflows.report.image_downloader.httpx.Client", side_effect=_mock_client)


# ---------------------------------------------------------------------------
# T1: full path — start → resolve → inject produces local URLs
# ---------------------------------------------------------------------------

def test_async_localization_round_trip_replaces_external_urls_in_markdown(tmp_path):
    assets = [
        {"url": "https://example.com/a.png", "title": "RAG arch", "source_page": "https://p1"},
        {"url": "https://example.com/b.png", "title": "Vector DB", "source_page": "https://p2"},
    ]
    markdown = (
        "# Report\n"
        "## 一、原理\n"
        "RAG = retrieval + generation.\n"
        "## 二、流程\n"
        "Query → retrieve → generate.\n"
    )

    with _patch_httpx(_png_response):
        future = start_async_localization(
            assets, owner="alice", course_id="c-rag", storage_root=tmp_path,
        )
        injectable = resolve_async_localization(future, assets, extra_timeout_s=10.0)

    # Every asset got localized
    for item in injectable:
        assert item["url"].startswith("/api/images/searched/")
        assert item["url"].endswith(".png")

    final_md = inject_images_into_report(markdown, injectable, max_images=2)
    assert "/api/images/searched/" in final_md
    assert "https://example.com/a.png" not in final_md  # external URL replaced
    assert "https://example.com/b.png" not in final_md
    assert "![RAG arch]" in final_md
    assert "![Vector DB]" in final_md


# ---------------------------------------------------------------------------
# T2: partial failure — failed asset falls back to external URL
# ---------------------------------------------------------------------------

def test_async_localization_falls_back_to_external_url_for_failed_downloads(tmp_path):
    assets = [
        {"url": "https://example.com/ok.png", "title": "ok", "source_page": "https://p1"},
        {"url": "https://example.com/bad.png", "title": "bad", "source_page": "https://p2"},
    ]

    def _mixed(req):
        if "/bad.png" in str(req.url):
            return httpx.Response(404, content=b"")
        return _png_response(req)

    with _patch_httpx(_mixed):
        future = start_async_localization(assets, owner="alice", storage_root=tmp_path)
        injectable = resolve_async_localization(future, assets, extra_timeout_s=10.0)

    assert injectable[0]["url"].startswith("/api/images/searched/")
    assert injectable[1]["url"] == "https://example.com/bad.png"  # fallback

    markdown = "# Report\n## 一\n\n## 二\n"
    final = inject_images_into_report(markdown, injectable, max_images=2)
    assert "/api/images/searched/" in final
    assert "https://example.com/bad.png" in final


# ---------------------------------------------------------------------------
# T3: timeout join — future not done within extra_timeout_s → all fall back
# ---------------------------------------------------------------------------

def test_resolve_falls_back_when_future_times_out():
    import concurrent.futures
    import time
    import threading

    assets = [{"url": "https://example.com/x.png", "title": "x"}]

    # Build a Future that never completes (simulate hung download)
    pending = concurrent.futures.Future()

    injectable = resolve_async_localization(pending, assets, extra_timeout_s=0.05)
    assert len(injectable) == 1
    assert injectable[0]["url"] == "https://example.com/x.png"


# ---------------------------------------------------------------------------
# T4: empty input — no future blocks
# ---------------------------------------------------------------------------

def test_start_async_localization_returns_completed_future_for_empty_input(tmp_path):
    future = start_async_localization([], storage_root=tmp_path)
    assert future.done()
    assert future.result() == []

    result = resolve_async_localization(future, [], extra_timeout_s=1.0)
    assert result == []


# ---------------------------------------------------------------------------
# T5: image_injector preserves order and alt text after localization
# ---------------------------------------------------------------------------

def test_injection_after_localization_uses_original_alt_text(tmp_path):
    assets = [
        {"url": "https://example.com/img.png", "title": "本节示意图", "alt": "RAG flow"},
    ]
    with _patch_httpx(_png_response):
        future = start_async_localization(assets, owner="alice", storage_root=tmp_path)
        injectable = resolve_async_localization(future, assets, extra_timeout_s=10.0)

    md = "# R\n## 一、流程\n"
    out = inject_images_into_report(md, injectable, max_images=1)
    assert "![RAG flow](/api/images/searched/" in out


# ---------------------------------------------------------------------------
# T6: sidecar accumulates owner across multiple users for same URL
# ---------------------------------------------------------------------------

def test_sidecar_accumulates_attribution_across_users(tmp_path):
    import json
    asset = {"url": "https://example.com/shared.png", "title": "shared"}

    with _patch_httpx(_png_response):
        # alice downloads it for course-1
        future1 = start_async_localization(
            [asset], owner="alice", course_id="c-1", storage_root=tmp_path,
        )
        results1 = resolve_async_localization(future1, [asset], extra_timeout_s=10.0)
        assert results1[0]["url"].startswith("/api/images/searched/")

        # bob hits the cached file from course-2
        future2 = start_async_localization(
            [asset], owner="bob", course_id="c-2", storage_root=tmp_path,
        )
        results2 = resolve_async_localization(future2, [asset], extra_timeout_s=10.0)
        assert results2[0]["url"] == results1[0]["url"]  # same local URL

    # Sidecar should list both owners and both courses
    image_filename = results1[0]["url"].rsplit("/", 1)[-1]  # "abc.png"
    hash_ = image_filename.rsplit(".", 1)[0]
    sidecar_paths = list(tmp_path.rglob(f"{hash_}.json"))
    assert len(sidecar_paths) == 1
    rec = json.loads(sidecar_paths[0].read_text(encoding="utf-8"))
    assert sorted(rec["accessed_by"]) == ["alice", "bob"]
    assert sorted(rec["course_ids"]) == ["c-1", "c-2"]
