"""Safe HTML/PDF acquisition and parsing for course knowledge sources."""

from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Callable, Literal, Mapping, Sequence
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.services.course_knowledge_source_discovery import canonical_source_url


class SourceIngestionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FetchedSource:
    title: str
    original_url: str
    final_url: str
    content_format: Literal["pdf", "html"]
    content_hash: str
    payload: bytes
    content_type: str
    retrieved_at: str


HostResolver = Callable[[str], Sequence[str]]


def _default_resolver(hostname: str) -> list[str]:
    return list(
        dict.fromkeys(
            item[4][0]
            for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        )
    )


def validate_public_source_url(
    value: str,
    *,
    resolve_host: HostResolver | None = None,
) -> str:
    parsed = urlsplit(str(value or "").strip())
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SourceIngestionError("UNSAFE_SOURCE_URL", "来源必须是无凭据的 HTTPS 公网 URL")
    try:
        addresses = list((resolve_host or _default_resolver)(parsed.hostname))
    except (OSError, ValueError) as exc:
        raise SourceIngestionError("UNSAFE_SOURCE_URL", f"来源域名解析失败：{exc}") from exc
    if not addresses:
        raise SourceIngestionError("UNSAFE_SOURCE_URL", "来源域名没有可用地址")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise SourceIngestionError("UNSAFE_SOURCE_URL", "来源域名返回了非法地址") from exc
        if not ip.is_global:
            raise SourceIngestionError("UNSAFE_SOURCE_URL", "来源解析到非公网地址")
    normalized = canonical_source_url(value)
    if not normalized:
        raise SourceIngestionError("UNSAFE_SOURCE_URL", "来源 URL 无法规范化")
    return normalized


def fetch_source(
    client: httpx.Client,
    candidate: Mapping[str, Any],
    *,
    resolve_host: HostResolver | None = None,
    robots_allowed: Callable[[str], bool] | None = None,
    max_pdf_bytes: int = 50 * 1024 * 1024,
    max_html_bytes: int = 5 * 1024 * 1024,
    max_redirects: int = 5,
) -> FetchedSource:
    original_url = str(candidate.get("url") or "").strip()
    current_url = original_url
    response: httpx.Response | None = None
    payload = b""
    content_type = ""
    for redirect_index in range(max_redirects + 1):
        current_url = validate_public_source_url(current_url, resolve_host=resolve_host)
        if robots_allowed is not None and not robots_allowed(current_url):
            raise SourceIngestionError("ROBOTS_DENIED", "来源 robots.txt 不允许抓取")
        try:
            request = client.build_request("GET", current_url)
            response = client.send(request, stream=True)
        except httpx.TimeoutException as exc:
            raise SourceIngestionError("DOWNLOAD_TIMEOUT", "来源下载超时") from exc
        except httpx.HTTPError as exc:
            raise SourceIngestionError("DOWNLOAD_FAILED", f"来源下载失败：{exc}") from exc
        try:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise SourceIngestionError("DOWNLOAD_FAILED", "重定向响应缺少 Location")
                if redirect_index >= max_redirects:
                    raise SourceIngestionError("DOWNLOAD_FAILED", "来源重定向次数过多")
                current_url = urljoin(current_url, location)
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise SourceIngestionError("DOWNLOAD_FAILED", f"来源返回 HTTP {response.status_code}") from exc
            content_type = str(response.headers.get("content-type") or "").split(";", 1)[0].casefold()
            hinted_pdf = (
                "pdf" in content_type
                or urlsplit(current_url).path.casefold().endswith(".pdf")
                or str((candidate.get("metadata") or {}).get("content_format_hint") or "") == "pdf"
            )
            limit = max_pdf_bytes if hinted_pdf else max_html_bytes
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > limit:
                    raise SourceIngestionError("DOWNLOAD_TOO_LARGE", "来源文件超过允许大小")
                chunks.append(chunk)
            payload = b"".join(chunks)
            break
        finally:
            response.close()
    if response is None:
        raise SourceIngestionError("DOWNLOAD_FAILED", "来源没有返回响应")

    is_pdf = payload.startswith(b"%PDF-")
    claims_pdf = (
        "pdf" in content_type
        or urlsplit(current_url).path.casefold().endswith(".pdf")
        or str((candidate.get("metadata") or {}).get("content_format_hint") or "") == "pdf"
    )
    if claims_pdf and not is_pdf:
        raise SourceIngestionError("PDF_SIGNATURE_INVALID", "PDF 文件签名无效")
    if is_pdf:
        if len(payload) > max_pdf_bytes:
            raise SourceIngestionError("DOWNLOAD_TOO_LARGE", "PDF 文件超过允许大小")
        content_format: Literal["pdf", "html"] = "pdf"
    else:
        if len(payload) > max_html_bytes:
            raise SourceIngestionError("DOWNLOAD_TOO_LARGE", "HTML 文件超过允许大小")
        lowered = payload[:512].lstrip().casefold()
        if "html" not in content_type and not lowered.startswith((b"<!doctype html", b"<html")):
            raise SourceIngestionError("CONTENT_TYPE_MISMATCH", "来源不是可解析的 HTML 或 PDF")
        content_format = "html"
    final_url = canonical_source_url(current_url)
    if not final_url:
        raise SourceIngestionError("UNSAFE_SOURCE_URL", "最终来源 URL 不是 HTTPS")
    return FetchedSource(
        title=str(candidate.get("title") or final_url).strip(),
        original_url=original_url,
        final_url=final_url,
        content_format=content_format,
        content_hash=hashlib.sha256(payload).hexdigest(),
        payload=payload,
        content_type=content_type,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )


def parse_pdf_source(
    fetched: FetchedSource | Any,
    *,
    pdf_parser: Any | None = None,
) -> dict[str, Any]:
    if not bytes(fetched.payload).startswith(b"%PDF-"):
        raise SourceIngestionError("PDF_SIGNATURE_INVALID", "PDF 文件签名无效")
    filename = PurePosixPath(urlsplit(str(fetched.final_url)).path).name or "document.pdf"
    if not filename.casefold().endswith(".pdf"):
        filename = f"{re.sub(r'[^a-zA-Z0-9._-]+', '-', filename).strip('-') or 'document'}.pdf"
    try:
        if pdf_parser is None:
            from app.integrations.pdf import get_pdf_parser

            pdf_parser = get_pdf_parser()
        parsed = pdf_parser.parse(bytes(fetched.payload), filename=filename)
    except Exception as exc:
        code = "MINERU_NOT_CONFIGURED" if "api key" in str(exc).casefold() else "MINERU_PARSE_FAILED"
        raise SourceIngestionError(code, f"MinerU PDF 解析失败：{exc}") from exc
    markdown = str(getattr(parsed, "text", "") or "").strip()
    if not markdown:
        raise SourceIngestionError("MINERU_PARSE_FAILED", "MinerU 没有从 PDF 提取到正文")
    from app.services.course_knowledge_textbook_inputs import _extract_outline_and_chunks

    textbook_id = f"online-{str(fetched.content_hash)[:20]}"
    outline, chunks, warnings = _extract_outline_and_chunks(markdown, textbook_id=textbook_id)
    metadata = dict(getattr(parsed, "metadata", {}) or {})
    plain = re.sub(r"^#{1,6}\s+", "", markdown, flags=re.MULTILINE)
    plain = re.sub(r"\s+", " ", plain).strip()
    return {
        "parser": str(metadata.get("parser") or "mineru"),
        "parser_metadata": metadata,
        "summary": plain[:4000],
        "outline": outline,
        "chunks": chunks,
        "char_count": len(markdown),
        "chapter_count": len(outline),
        "chunk_count": len(chunks),
        "warnings": warnings,
        "parsed_at": datetime.now(timezone.utc).isoformat(),
    }


def parse_html_source(fetched: FetchedSource | Any) -> dict[str, Any]:
    """Parse a structured, long-form HTML source into ordered textbook chunks."""
    try:
        html = bytes(fetched.payload).decode("utf-8")
    except UnicodeDecodeError:
        html = bytes(fetched.payload).decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.select("script, style, nav, header, footer, aside, form, noscript"):
        element.decompose()
    main = soup.select_one("main, article, [role='main'], .md-content, #content") or soup.body
    if main is None:
        raise SourceIngestionError("HTML_BODY_TOO_SHORT", "来源页面没有可识别的正文")
    headings = list(main.find_all(["h1", "h2", "h3", "h4"]))
    if len(headings) < 2:
        raise SourceIngestionError("TEXTBOOK_TOC_NOT_FOUND", "HTML 教材没有可信的章节结构")

    textbook_id = f"online-{str(fetched.content_hash)[:20]}"
    outline: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    for index, heading in enumerate(headings, start=1):
        title = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip()
        if not title:
            continue
        content_parts: list[str] = []
        for sibling in heading.next_siblings:
            name = getattr(sibling, "name", None)
            if name in {"h1", "h2", "h3", "h4"}:
                break
            text = re.sub(r"\s+", " ", sibling.get_text(" ", strip=True)).strip() if hasattr(sibling, "get_text") else re.sub(r"\s+", " ", str(sibling)).strip()
            if text:
                content_parts.append(text)
        content = "\n\n".join(content_parts).strip()
        chapter_id = f"{textbook_id}-html-{index}"
        outline.append(
            {
                "id": chapter_id,
                "title": title,
                "level": int(heading.name[1]),
                "order": index,
            }
        )
        chunks.append(
            {
                "chunk_id": chapter_id,
                "chapter_id": chapter_id,
                "chapter_title": title,
                "content": content,
                "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "order": index,
            }
        )
    if len(chunks) < 2:
        raise SourceIngestionError("TEXTBOOK_TOC_NOT_FOUND", "HTML 教材没有足够的有效章节")
    combined = "\n\n".join(
        f"{item['chapter_title']}\n{item['content']}" for item in chunks
    )
    return {
        "parser": "structured-html",
        "parser_metadata": {"source_url": str(fetched.final_url)},
        "summary": re.sub(r"\s+", " ", combined).strip()[:4000],
        "outline": outline,
        "chunks": chunks,
        "char_count": len(combined),
        "chapter_count": len(outline),
        "chunk_count": len(chunks),
        "warnings": [],
        "parsed_at": datetime.now(timezone.utc).isoformat(),
    }
