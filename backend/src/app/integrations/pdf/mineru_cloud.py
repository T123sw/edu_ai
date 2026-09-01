"""MinerU Cloud API (v4) 解析 provider —— Python 端直连实现。

移植自 OpenMAIC ``lib/pdf/mineru-cloud.ts``（MIT），流程完全一致：

    POST {base}/file-urls/batch          → batch_id + 预签名上传 URL
    PUT  预签名URL 上传 PDF               （★ 不带 Content-Type，OSS 签名敏感）
    GET  {base}/extract-results/batch/{batch_id}   每 2.5s 轮询，最长 15min
      → state=done & full_zip_url
    下载 ZIP → full.md + content_list.json + images/ → 归一为 ParsedPdf

不依赖 OpenMAIC sidecar，自包含，用 .env 里的 key 即可测。
env：``PDF_MINERU_CLOUD_API_KEY`` / ``PDF_MINERU_CLOUD_BASE_URL``。
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import time
import zipfile
from typing import Any, Dict, List, Optional

import httpx

from .base import ParsedPdf, PdfParseError, PdfParseProvider

MINERU_CLOUD_DEFAULT_BASE = "https://mineru.net/api/v4"

# 各阶段超时（秒），对齐 TS 版
_TIMEOUT_BATCH = 60.0
_TIMEOUT_UPLOAD = 180.0
_TIMEOUT_POLL = 30.0
_TIMEOUT_ZIP = 180.0

_POLL_INTERVAL_S = 2.5
_POLL_MAX_S = 15 * 60  # 15 分钟
_RETRYABLE = ("fetch failed", "econnreset", "etimedout", "timeout", "aborted", "connection")

_MIME_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}


def _ext_to_mime(ext: str) -> str:
    return _MIME_MAP.get(ext.lower(), "application/octet-stream")


def _sanitize_filename(name: Optional[str]) -> str:
    fallback = "document.pdf"
    raw = (name or fallback).replace("\\", "/").split("/")[-1].strip() or fallback
    trimmed = raw[:240]
    if not trimmed.lower().endswith(".pdf"):
        return fallback
    if ".." in trimmed:
        return fallback
    return trimmed or fallback


def _is_retryable(err: Exception) -> bool:
    if isinstance(err, (httpx.TransportError, httpx.TimeoutException)):
        return True
    msg = str(err).lower()
    return any(s in msg for s in _RETRYABLE)


def _retry(fn, context: str, attempts: int = 4):
    """带退避的重试（仅对瞬时错误），对齐 TS fetchWithRetry。"""
    last: Optional[Exception] = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as err:  # noqa: BLE001 — 由 _is_retryable 判定是否重试
            last = err
            if not _is_retryable(err) or i == attempts:
                break
            time.sleep(0.4 * i)
    raise PdfParseError(f"MinerU Cloud {context} failed: {last}")


def _read_envelope(resp: httpx.Response, context: str) -> Any:
    """解析 MinerU 统一信封 {code, msg, data}，非 0 或 HTTP 错误抛异常。"""
    text = resp.text
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PdfParseError(
            f"MinerU Cloud {context}: invalid JSON (HTTP {resp.status_code}): {text[:500]}"
        ) from exc
    if resp.status_code >= 400:
        raise PdfParseError(
            f"MinerU Cloud {context}: HTTP {resp.status_code} — {payload.get('msg') or text[:300]}"
        )
    if payload.get("code") != 0:
        raise PdfParseError(
            f"MinerU Cloud {context}: {payload.get('msg') or 'unknown error'} (code {payload.get('code')})"
        )
    return payload.get("data")


class MinerUCloudProvider(PdfParseProvider):
    """MinerU Cloud v4 解析实现。"""

    provider_id = "mineru-cloud"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        *,
        language: str = "ch",
        enable_formula: bool = True,
        enable_table: bool = True,
        model_version: str = "vlm",
    ) -> None:
        self.api_key = api_key or os.getenv("PDF_MINERU_CLOUD_API_KEY", "")
        self.base_url = (base_url or os.getenv("PDF_MINERU_CLOUD_BASE_URL") or MINERU_CLOUD_DEFAULT_BASE).rstrip("/")
        self.language = language
        self.enable_formula = enable_formula
        self.enable_table = enable_table
        self.model_version = model_version

    def is_configured(self) -> bool:
        return bool(self.api_key)

    # ── 主入口 ──────────────────────────────────────────────────────────────
    def parse(self, pdf: bytes, *, filename: str = "document.pdf") -> ParsedPdf:
        if not self.api_key:
            raise PdfParseError("MinerU Cloud API key is required (PDF_MINERU_CLOUD_API_KEY)")

        upload_name = _sanitize_filename(filename)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        started = time.time()

        with httpx.Client(trust_env=False) as client:
            # Step 1: 建 batch，拿预签名上传 URL
            def _create_batch():
                resp = client.post(
                    f"{self.base_url}/file-urls/batch",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "files": [{"name": upload_name}],
                        "enable_formula": self.enable_formula,
                        "enable_table": self.enable_table,
                        "model_version": self.model_version,
                        "language": self.language,
                    },
                    timeout=_TIMEOUT_BATCH,
                )
                return _read_envelope(resp, "file-urls/batch")

            batch = _retry(_create_batch, "create batch")
            batch_id = batch.get("batch_id")
            upload_urls = batch.get("file_urls") or batch.get("files")
            if not batch_id or not upload_urls:
                raise PdfParseError("MinerU Cloud batch response missing batch_id or upload URLs")

            # Step 2: PUT 上传到预签名 URL（★ 绝不带 Content-Type）
            def _upload():
                return client.put(upload_urls[0], content=pdf, timeout=_TIMEOUT_UPLOAD)

            put_resp = _retry(_upload, "presigned upload", attempts=5)
            if put_resp.status_code >= 400:
                raise PdfParseError(
                    f"MinerU Cloud upload failed ({put_resp.status_code}): {put_resp.text[:400]}"
                )

            time.sleep(1.5)  # 给后端一点注册时间

            # Step 3: 轮询
            deadline = time.time() + _POLL_MAX_S
            last_state = ""
            while time.time() < deadline:
                def _poll():
                    resp = client.get(
                        f"{self.base_url}/extract-results/batch/{batch_id}",
                        headers={**headers, "Accept": "application/json"},
                        timeout=_TIMEOUT_POLL,
                    )
                    return _read_envelope(resp, "extract-results/batch")

                status = _retry(_poll, "poll batch", attempts=3)
                rows = status.get("extract_result")
                rows_list: List[Dict[str, Any]] = (
                    rows if isinstance(rows, list) else [rows] if rows else []
                )
                row = (
                    next((r for r in rows_list if r.get("file_name") == upload_name), None)
                    or next(
                        (r for r in rows_list if str(r.get("file_name", "")).lower() == upload_name.lower()),
                        None,
                    )
                    or (rows_list[0] if rows_list else None)
                )

                state = (row or {}).get("state")
                if not state:
                    time.sleep(_POLL_INTERVAL_S)
                    continue
                if state != last_state:
                    last_state = state
                if state == "failed":
                    raise PdfParseError(
                        f"MinerU Cloud parsing failed: {(row or {}).get('err_msg') or 'unknown error'}"
                    )
                if state == "done" and row.get("full_zip_url"):
                    result = self._parse_zip(client, row["full_zip_url"])
                    result.metadata.update(
                        {
                            "parser": self.provider_id,
                            "taskId": batch_id,
                            "processingTime": round(time.time() - started, 2),
                            "fileName": upload_name,
                        }
                    )
                    return result
                time.sleep(_POLL_INTERVAL_S)

            raise PdfParseError(
                f"MinerU Cloud timed out after {_POLL_MAX_S}s (batch: {batch_id})"
            )

    # ── ZIP 解包与归一 ──────────────────────────────────────────────────────
    def _parse_zip(self, client: httpx.Client, zip_url: str) -> ParsedPdf:
        def _download():
            return client.get(zip_url, timeout=_TIMEOUT_ZIP, follow_redirects=True)

        resp = _retry(_download, "ZIP download")
        if resp.status_code >= 400:
            raise PdfParseError(
                f"MinerU Cloud ZIP download failed ({resp.status_code}): {resp.text[:300]}"
            )

        try:
            zf = zipfile.ZipFile(io.BytesIO(resp.content))
        except zipfile.BadZipFile as exc:
            raise PdfParseError(f"MinerU Cloud ZIP parse failed: {exc}") from exc

        names = [n for n in zf.namelist() if not n.endswith("/")]
        full_md_path = next((n for n in names if re.search(r"(^|/)full\.md$", n, re.I)), None)
        content_list_path = next(
            (n for n in names if n.endswith("_content_list.json") or re.search(r"(^|/)content_list\.json$", n, re.I)),
            None,
        )
        if not full_md_path:
            raise PdfParseError(
                f"MinerU Cloud ZIP: full.md not found. Files: {', '.join(names[:10])}"
            )

        markdown = zf.read(full_md_path).decode("utf-8", errors="ignore")
        dir_prefix = full_md_path[: full_md_path.rfind("/") + 1] if "/" in full_md_path else ""

        content_list: Any = None
        if content_list_path:
            try:
                content_list = json.loads(zf.read(content_list_path).decode("utf-8", errors="ignore"))
            except json.JSONDecodeError:
                content_list = None

        name_set = set(names)

        def _read_image(rel_path: str) -> Optional[str]:
            normalized = re.sub(r"^\.?/", "", rel_path)
            for candidate in (dir_prefix + normalized, normalized):
                if candidate in name_set:
                    buf = zf.read(candidate)
                    ext = candidate.split(".")[-1] if "." in candidate else "png"
                    return f"data:{_ext_to_mime(ext)};base64,{base64.b64encode(buf).decode()}"
            return None

        # content_list 里引用的图片
        image_mapping: Dict[str, str] = {}
        formulas: List[Dict[str, Any]] = []
        tables: List[Dict[str, Any]] = []
        if isinstance(content_list, list):
            for item in content_list:
                if not isinstance(item, dict):
                    continue
                itype = item.get("type")
                if itype == "image" and isinstance(item.get("img_path"), str):
                    b64 = _read_image(item["img_path"])
                    if b64:
                        basename = item["img_path"].split("/")[-1]
                        image_mapping[basename] = b64
                elif itype in ("equation", "formula") and item.get("text"):
                    formulas.append({"latex": item.get("text"), "page": item.get("page_idx")})
                elif itype == "table":
                    tables.append(
                        {"page": item.get("page_idx"), "caption": item.get("table_caption")}
                    )

        # 兜底：扫描 zip 里未被 content_list 引用的图片
        for n in names:
            if re.search(r"\.(png|jpe?g|webp|gif)$", n, re.I):
                basename = n.split("/")[-1]
                if basename not in image_mapping:
                    b64 = _read_image(n)
                    if b64:
                        image_mapping[basename] = b64

        page_count = 0
        if isinstance(content_list, list):
            pages = [it.get("page_idx") for it in content_list if isinstance(it, dict) and it.get("page_idx") is not None]
            if pages:
                page_count = max(pages) + 1

        return ParsedPdf(
            text=markdown,
            images=list(image_mapping.values()),
            tables=tables,
            formulas=formulas,
            metadata={
                "pageCount": page_count,
                "imageMapping": image_mapping,
            },
        )
