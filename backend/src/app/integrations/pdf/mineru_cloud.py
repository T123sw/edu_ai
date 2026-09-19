"""MinerU Cloud API (v4) 解析 provider —— Python 端直连实现。

移植自 OpenMAIC ``lib/pdf/mineru-cloud.ts``（MIT），流程完全一致：

    POST {base}/file-urls/batch          → batch_id + 预签名上传 URL
    PUT  预签名URL 上传文档               （★ 不带 Content-Type，OSS 签名敏感）
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
from pathlib import Path

from .formats import MINERU_SUPPORTED_SUFFIXES

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
    suffix = Path(raw).suffix.lower()
    if suffix not in MINERU_SUPPORTED_SUFFIXES:
        raise PdfParseError(f"MinerU Cloud unsupported file type: {suffix or '(none)'}")
    stem = raw[:-len(suffix)]
    stem = re.sub(r'[\x00-\x1f\x7f]', '_', stem).replace('..', '_')
    return (stem[:240-len(suffix)] or 'document') + suffix


def _is_retryable(err: Exception) -> bool:
    if isinstance(err, (httpx.TransportError, httpx.TimeoutException)):
        return True
    msg = str(err).lower()
    return any(s in msg for s in _RETRYABLE)


class ParseStopped(PdfParseError):
    def __init__(self, code, remote_task=None):
        self.code, self.remote_task = code, remote_task
        super().__init__(code)


class ParseControl:
    """Process-local monotonic deadline and live cancellation; never serialized."""
    def __init__(self, *, deadline=None, canceled=None, clock=time.monotonic,
                 sleep=time.sleep, on_remote_task=None):
        self.deadline, self.canceled = deadline, canceled
        self.clock, self.sleep, self.on_remote_task = clock, sleep, on_remote_task
        self.remote_task = None

    def check(self):
        if self.canceled and self.canceled():
            raise ParseStopped('CANCELED', self.remote_task)
        if self.deadline is not None and self.clock() >= self.deadline:
            raise ParseStopped('DEADLINE_EXCEEDED', self.remote_task)

    def timeout(self, ceiling):
        self.check()
        remaining = self.deadline-self.clock() if self.deadline is not None else ceiling
        if remaining <= 0: raise ParseStopped('DEADLINE_EXCEEDED', self.remote_task)
        return min(ceiling, remaining)

    def wait(self, seconds):
        end = self.clock() + seconds
        while self.clock() < end:
            self.sleep(self.timeout(min(.25, end-self.clock())))
        self.check()

    def submitted(self, batch_id):
        self.remote_task = {'provider': 'mineru-cloud', 'task_id': str(batch_id)}
        if self.on_remote_task:
            try:
                self.on_remote_task(dict(self.remote_task))
            except Exception as exc:
                exc.remote_task = self.remote_task
                raise
        self.check()


def _retry(fn, context: str, attempts: int = 4, *, control=None):
    control = control or ParseControl()
    for i in range(1, attempts + 1):
        control.check()
        try:
            result = fn()
            control.check()
            return result
        except ParseStopped:
            raise
        except Exception as err:
            if not _is_retryable(err) or i == attempts:
                # Do not expose signed URLs, authentication headers or response bodies.
                failure = PdfParseError(f'MinerU Cloud {context} failed ({type(err).__name__})')
                failure.remote_task = control.remote_task
                raise failure from err
            control.wait(.4 * i)


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
        client_factory=None, clock=time.monotonic, sleep=time.sleep,
    ) -> None:
        self.client_factory = client_factory or httpx.Client
        self.clock, self.sleep = clock, sleep
        self.api_key = api_key or os.getenv("PDF_MINERU_CLOUD_API_KEY", "")
        self.base_url = (base_url or os.getenv("PDF_MINERU_CLOUD_BASE_URL") or MINERU_CLOUD_DEFAULT_BASE).rstrip("/")
        self.language = language
        self.enable_formula = enable_formula
        self.enable_table = enable_table
        self.model_version = model_version

    def is_configured(self) -> bool:
        return bool(self.api_key)

    # ── 主入口 ──────────────────────────────────────────────────────────────
    def parse(self, pdf: bytes, *, filename: str = "document.pdf", deadline=None,
              canceled=None, on_remote_task=None) -> ParsedPdf:
        control = ParseControl(deadline=deadline, canceled=canceled, clock=self.clock,
                               sleep=self.sleep, on_remote_task=on_remote_task)
        control.check()
        if not self.api_key:
            raise PdfParseError("MinerU Cloud API key is required (PDF_MINERU_CLOUD_API_KEY)")

        upload_name = _sanitize_filename(filename)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        started = self.clock()

        with self.client_factory(trust_env=False) as client:
            # Step 1: 建 batch，拿预签名上传 URL
            def _create_batch():
                resp = client.post(
                    f"{self.base_url}/file-urls/batch",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "files": [{"name": upload_name}],
                        "enable_formula": self.enable_formula,
                        "enable_table": self.enable_table,
                        "model_version": "MinerU-HTML" if upload_name.endswith(".html") else self.model_version,
                        "language": self.language,
                    },
                    timeout=control.timeout(_TIMEOUT_BATCH),
                )
                data = _read_envelope(resp, "file-urls/batch")
                if data and data.get("batch_id"):
                    control.submitted(data["batch_id"])
                return data

            batch = _retry(_create_batch, "create batch", control=control)
            batch_id = batch.get("batch_id")
            upload_urls = batch.get("file_urls") or batch.get("files")
            if not batch_id or not upload_urls:
                raise PdfParseError("MinerU Cloud batch response missing batch_id or upload URLs")

            # Step 2: PUT 上传到预签名 URL（★ 绝不带 Content-Type）
            def _upload():
                return client.put(upload_urls[0], content=pdf, timeout=control.timeout(_TIMEOUT_UPLOAD))

            put_resp = _retry(_upload, "presigned upload", attempts=5, control=control)
            if put_resp.status_code >= 400:
                raise PdfParseError(
                    f"MinerU Cloud upload failed ({put_resp.status_code}): {put_resp.text[:400]}"
                )

            control.wait(1.5)  # 给后端一点注册时间

            # Step 3: 轮询
            poll_deadline = self.clock() + _POLL_MAX_S
            control.deadline = min(control.deadline, poll_deadline) if control.deadline is not None else poll_deadline
            last_state = ""
            while True:
                control.check()
                def _poll():
                    resp = client.get(
                        f"{self.base_url}/extract-results/batch/{batch_id}",
                        headers={**headers, "Accept": "application/json"},
                        timeout=control.timeout(_TIMEOUT_POLL),
                    )
                    return _read_envelope(resp, "extract-results/batch")

                status = _retry(_poll, "poll batch", attempts=3, control=control)
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
                    control.wait(_POLL_INTERVAL_S)
                    continue
                if state != last_state:
                    last_state = state
                if state == "failed":
                    raise PdfParseError(
                        f"MinerU Cloud parsing failed: {(row or {}).get('err_msg') or 'unknown error'}"
                    )
                if state == "done" and row.get("full_zip_url"):
                    result = self._parse_zip(client, row["full_zip_url"], control=control)
                    result.metadata.update(
                        {
                            "parser": self.provider_id,
                            "taskId": batch_id,
                            "processingTime": round(self.clock() - started, 2),
                            "fileName": upload_name,
                        }
                    )
                    control.check()
                    return result
                control.wait(_POLL_INTERVAL_S)


    # ── ZIP 解包与归一 ──────────────────────────────────────────────────────
    def _parse_zip(self, client: httpx.Client, zip_url: str, *, control=None) -> ParsedPdf:
        control = control or ParseControl()
        def _download():
            return client.get(zip_url, timeout=control.timeout(_TIMEOUT_ZIP), follow_redirects=True)

        resp = _retry(_download, "ZIP download", control=control)
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
                "pageIndices": sorted(set(pages)) if isinstance(content_list, list) else [],
                "layout": content_list if isinstance(content_list, list) else [],
            },
        )
