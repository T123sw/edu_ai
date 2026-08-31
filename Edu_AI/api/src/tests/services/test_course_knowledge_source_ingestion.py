from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.services.course_knowledge_source_ingestion import (
    SourceIngestionError,
    fetch_source,
    parse_html_source,
    parse_pdf_source,
    validate_public_source_url,
)


PUBLIC_IP = ["93.184.216.34"]


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_fetch_source_accepts_octet_stream_only_when_payload_is_a_real_pdf():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/octet-stream"},
            content=b"%PDF-1.7\nfixture",
            request=request,
        )

    with _client(handler) as client:
        fetched = fetch_source(
            client,
            {"url": "https://example.edu/book", "title": "课程教材"},
            resolve_host=lambda _host: PUBLIC_IP,
        )

    assert fetched.content_format == "pdf"
    assert fetched.final_url == "https://example.edu/book"
    assert fetched.payload.startswith(b"%PDF-")
    assert len(fetched.content_hash) == 64


def test_fetch_source_rejects_html_disguised_as_pdf():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=b"<html><body>not a pdf</body></html>",
            request=request,
        )

    with _client(handler) as client, pytest.raises(SourceIngestionError) as error:
        fetch_source(
            client,
            {"url": "https://example.edu/fake.pdf", "title": "伪 PDF"},
            resolve_host=lambda _host: PUBLIC_IP,
        )

    assert error.value.code == "PDF_SIGNATURE_INVALID"


def test_public_url_policy_rejects_private_addresses_and_pdf_size_limit():
    with pytest.raises(SourceIngestionError) as unsafe:
        validate_public_source_url(
            "https://internal.example/book.pdf",
            resolve_host=lambda _host: ["127.0.0.1"],
        )
    assert unsafe.value.code == "UNSAFE_SOURCE_URL"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=b"%PDF-" + b"x" * 32,
            request=request,
        )

    with _client(handler) as client, pytest.raises(SourceIngestionError) as oversized:
        fetch_source(
            client,
            {"url": "https://example.edu/large.pdf", "title": "大文件"},
            resolve_host=lambda _host: PUBLIC_IP,
            max_pdf_bytes=16,
        )
    assert oversized.value.code == "DOWNLOAD_TOO_LARGE"


def test_parse_pdf_source_calls_parser_once_and_builds_outline_chunks():
    calls = []

    class Parser:
        def parse(self, payload: bytes, *, filename: str):
            calls.append((payload, filename))
            return SimpleNamespace(
                text="# 第一章 向量空间\n\n定义与例题\n\n# 第二章 线性映射\n\n矩阵表示",
                metadata={"parser": "mineru-cloud", "pageCount": 12, "taskId": "task-1"},
            )

    fetched = SimpleNamespace(
        title="线性代数教材",
        final_url="https://example.edu/linear-algebra.pdf",
        content_hash="a" * 64,
        payload=b"%PDF-fixture",
    )

    parsed = parse_pdf_source(fetched, pdf_parser=Parser())

    assert calls == [(b"%PDF-fixture", "linear-algebra.pdf")]
    assert parsed["parser"] == "mineru-cloud"
    assert parsed["chapter_count"] == 2
    assert parsed["chunk_count"] == 2
    assert parsed["parser_metadata"]["taskId"] == "task-1"


def test_parse_html_textbook_preserves_heading_order_and_builds_chunks():
    fetched = SimpleNamespace(
        title="数据结构开放教材",
        final_url="https://example.edu/data-structures",
        content_hash="b" * 64,
        payload=(
            "<html><body><main>"
            "<h1>数据结构</h1><p>课程导论</p>"
            "<h2>线性表</h2><p>顺序表与链表的定义、算法和例题。</p>"
            "<h2>树</h2><p>二叉树、遍历算法和应用。</p>"
            "</main></body></html>"
        ).encode("utf-8"),
    )

    parsed = parse_html_source(fetched)

    assert parsed["parser"] == "structured-html"
    assert [item["title"] for item in parsed["outline"]] == ["数据结构", "线性表", "树"]
    assert parsed["chunk_count"] == 3
    assert parsed["chunks"][1]["chapter_title"] == "线性表"


def test_parse_pdf_reports_stable_error_when_mineru_is_not_configured(monkeypatch):
    from app.integrations import pdf

    monkeypatch.setattr(
        pdf,
        "get_pdf_parser",
        lambda: (_ for _ in ()).throw(RuntimeError("MinerU API key is not configured")),
    )
    fetched = SimpleNamespace(
        title="教材",
        final_url="https://example.edu/book.pdf",
        content_hash="c" * 64,
        payload=b"%PDF-fixture",
    )

    with pytest.raises(SourceIngestionError) as error:
        parse_pdf_source(fetched)

    assert error.value.code == "MINERU_NOT_CONFIGURED"
