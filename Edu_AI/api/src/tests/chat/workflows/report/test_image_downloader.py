"""Phase 6-A.2 — unit tests for image_downloader.

All HTTP calls mocked via httpx.MockTransport. No real network / disk pollution
outside tmp_path.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.chat.workflows.report.image_downloader import (
    DownloadFailure,
    LocalizedAsset,
    batch_localize,
    localize_image,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200  # 208 bytes — enough to exceed 200 minimum threshold


def _png_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        content=PNG_BYTES,
        headers={"content-type": "image/png", "content-length": str(len(PNG_BYTES))},
    )


def _404_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404, content=b"not found")


def _500_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, content=b"server error")


def _patch_httpx_with(handler):
    """Patch httpx.HTTPTransport.handle_request via MockTransport injection."""
    transport = httpx.MockTransport(handler)
    # We replace the Client constructor used in image_downloader to inject our transport.
    real_client = httpx.Client

    def _mock_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=transport, **kwargs)

    return patch("app.chat.workflows.report.image_downloader.httpx.Client", side_effect=_mock_client)


# ---------------------------------------------------------------------------
# T1: missing URL
# ---------------------------------------------------------------------------

def test_localize_returns_missing_url_for_empty_url(tmp_path):
    result = localize_image({"url": ""}, storage_root=tmp_path)
    assert isinstance(result, DownloadFailure)
    assert result.reason == "missing_url"
    assert result.attempts == 0


# ---------------------------------------------------------------------------
# T2: first successful download writes file + sidecar
# ---------------------------------------------------------------------------

def test_localize_downloads_and_writes_sidecar(tmp_path):
    asset = {
        "url": "https://example.com/diagram.png",
        "source_page": "https://example.com/article",
        "title": "RAG architecture",
        "provenance": {"provider": "searxng"},
    }
    with _patch_httpx_with(_png_response):
        result = localize_image(asset, owner="alice", course_id="c-rag", storage_root=tmp_path)

    assert isinstance(result, LocalizedAsset)
    assert result.local_path.exists()
    assert result.local_path.read_bytes() == PNG_BYTES
    assert result.local_url.startswith("/api/images/searched/")
    assert result.local_url.endswith(".png")
    assert result.content_type == "image/png"
    assert result.size_bytes == len(PNG_BYTES)

    sidecar = json.loads(result.local_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["hash"] == result.hash
    assert sidecar["source_url"] == asset["url"]
    assert sidecar["source_page"] == asset["source_page"]
    assert sidecar["title"] == asset["title"]
    assert sidecar["downloaded"] is True
    assert sidecar["accessed_by"] == ["alice"]
    assert sidecar["course_ids"] == ["c-rag"]
    assert sidecar["provider"] == "searxng"


# ---------------------------------------------------------------------------
# T3: cache hit — second call doesn't re-download
# ---------------------------------------------------------------------------

def test_localize_uses_cached_file_on_second_call(tmp_path):
    asset = {"url": "https://example.com/cached.png", "title": "cached"}
    with _patch_httpx_with(_png_response):
        first = localize_image(asset, owner="alice", storage_root=tmp_path)
    assert isinstance(first, LocalizedAsset)

    # Second call with a transport that would fail if invoked
    def _explode(_req):
        raise AssertionError("provider should not be re-invoked on cache hit")

    with _patch_httpx_with(_explode):
        second = localize_image(asset, owner="bob", course_id="c-bob", storage_root=tmp_path)

    assert isinstance(second, LocalizedAsset)
    assert second.local_path == first.local_path

    sidecar = json.loads(second.local_path.with_suffix(".json").read_text(encoding="utf-8"))
    # accessed_by / course_ids should now reflect both users
    assert sorted(sidecar["accessed_by"]) == ["alice", "bob"]
    assert sidecar["course_ids"] == ["c-bob"]
    assert sidecar["fetched_at"] is not None
    assert sidecar.get("last_accessed_at") is not None


# ---------------------------------------------------------------------------
# T4: HTTP 404 — non-retryable failure
# ---------------------------------------------------------------------------

def test_localize_returns_http_4xx_failure_without_retry(tmp_path):
    call_count = {"n": 0}

    def _404(req):
        call_count["n"] += 1
        return _404_response(req)

    with _patch_httpx_with(_404):
        result = localize_image(
            {"url": "https://example.com/missing.png"},
            owner="alice", course_id="c-x", storage_root=tmp_path,
        )

    assert isinstance(result, DownloadFailure)
    assert result.reason == "http_404"
    assert result.attempts == 1
    assert call_count["n"] == 1  # no retry on 4xx

    # Sidecar still recorded (for audit)
    sidecars = list(tmp_path.rglob("*.json"))
    assert len(sidecars) == 1
    rec = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert rec["downloaded"] is False
    assert rec["failure_reason"] == "http_404"
    assert rec["accessed_by"] == ["alice"]


# ---------------------------------------------------------------------------
# T5: HTTP 500 — retries once, then fails
# ---------------------------------------------------------------------------

def test_localize_retries_on_5xx_then_fails(tmp_path):
    call_count = {"n": 0}

    def _500(req):
        call_count["n"] += 1
        return _500_response(req)

    with _patch_httpx_with(_500), patch(
        "app.chat.workflows.report.image_downloader.time.sleep", return_value=None
    ):
        result = localize_image({"url": "https://example.com/down.png"}, storage_root=tmp_path)

    assert isinstance(result, DownloadFailure)
    assert result.reason == "http_500"
    assert result.attempts == 2
    assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# T6: Content-Length header > max → too_large (no download body)
# ---------------------------------------------------------------------------

def test_localize_rejects_oversize_content_length(tmp_path):
    def _huge(req):
        return httpx.Response(
            200,
            content=b"x",  # content body irrelevant — we check header
            headers={"content-type": "image/png", "content-length": str(50 * 1024 * 1024)},
        )

    with _patch_httpx_with(_huge):
        result = localize_image(
            {"url": "https://example.com/huge.png"},
            storage_root=tmp_path,
            max_bytes=10 * 1024 * 1024,
        )
    assert isinstance(result, DownloadFailure)
    assert result.reason == "too_large"


# ---------------------------------------------------------------------------
# T7: Content-Type non-image → invalid_content_type
# ---------------------------------------------------------------------------

def test_localize_rejects_non_image_content_type(tmp_path):
    def _html(req):
        return httpx.Response(
            200,
            content=b"<html>nope</html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )

    with _patch_httpx_with(_html):
        result = localize_image({"url": "https://example.com/page.png"}, storage_root=tmp_path)
    assert isinstance(result, DownloadFailure)
    assert result.reason == "invalid_content_type"


# ---------------------------------------------------------------------------
# T8: Timeout → retries once, then fails
# ---------------------------------------------------------------------------

def test_localize_returns_timeout_failure_after_retry(tmp_path):
    call_count = {"n": 0}

    def _slow(req):
        call_count["n"] += 1
        raise httpx.TimeoutException("simulated", request=req)

    with _patch_httpx_with(_slow), patch(
        "app.chat.workflows.report.image_downloader.time.sleep", return_value=None
    ):
        result = localize_image({"url": "https://example.com/slow.png"}, storage_root=tmp_path)

    assert isinstance(result, DownloadFailure)
    assert result.reason == "timeout"
    assert result.attempts == 2
    assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# T9: batch_localize preserves order
# ---------------------------------------------------------------------------

def test_batch_localize_preserves_input_order(tmp_path):
    assets = [
        {"url": f"https://example.com/img-{i}.png", "title": f"img-{i}"}
        for i in range(5)
    ]
    with _patch_httpx_with(_png_response):
        results = batch_localize(assets, owner="alice", course_id="c1", storage_root=tmp_path)

    assert len(results) == 5
    for asset, result in zip(assets, results):
        assert isinstance(result, LocalizedAsset)
        assert result.source_url == asset["url"]


# ---------------------------------------------------------------------------
# T10: cache hit with missing sidecar regenerates attribution gracefully
# ---------------------------------------------------------------------------

def test_localize_recovers_when_sidecar_missing_but_file_exists(tmp_path):
    asset = {"url": "https://example.com/orphan.png", "title": "orphan"}
    with _patch_httpx_with(_png_response):
        first = localize_image(asset, owner="alice", storage_root=tmp_path)
    assert isinstance(first, LocalizedAsset)

    # Delete sidecar to simulate corruption
    sidecar = first.local_path.with_suffix(".json")
    sidecar.unlink()
    assert not sidecar.exists()

    # Second call should not crash + should regenerate sidecar
    def _explode(_req):
        raise AssertionError("must not re-download")

    with _patch_httpx_with(_explode):
        second = localize_image(asset, owner="bob", course_id="c-bob", storage_root=tmp_path)

    assert isinstance(second, LocalizedAsset)
    assert sidecar.exists()
    rec = json.loads(sidecar.read_text(encoding="utf-8"))
    assert "bob" in rec.get("accessed_by", [])


# ---------------------------------------------------------------------------
# T11: empty asset list → empty batch result
# ---------------------------------------------------------------------------

def test_batch_localize_returns_empty_for_empty_input(tmp_path):
    assert batch_localize([], storage_root=tmp_path) == []
