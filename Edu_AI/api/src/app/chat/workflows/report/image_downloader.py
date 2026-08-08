"""Phase 6-A.2 — agent 搜来的图片本地化下载.

把 image_search 拿到的外部图 URL 下载到 `storage/searched_images/{YYYYMMDD}/`
并写一份 sidecar JSON 元数据。下载成功 → 返回 LocalizedAsset；失败 → 返回
DownloadFailure，调用方应回落到原始 URL。

设计要点：
- 全局按 sha256(URL) 去重：同 URL 第二次调用直接命中缓存，不发 HTTP 请求
- sidecar 累积 accessed_by / course_ids，全局去重前提下保留多用户/多课程归属链
- 不抛异常：任何失败都包装成 DownloadFailure 返回，不阻断报告生成
- 单图独立超时 + 单次重试，避免恶劣源站拖垮整批
- 大小预检（Content-Length 头）→ 超过上限直接放弃，不浪费带宽
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import ipaddress
import json
import mimetypes
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import urlparse

import httpx

from core import Config


_ALLOWED_EXTS = frozenset({"jpg", "jpeg", "png", "webp", "gif"})

_MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}

_BROWSER_UA_FALLBACK = "Mozilla/5.0 (compatible; EduAI/1.0)"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class LocalizedAsset:
    """A successfully-downloaded image, ready to embed in Markdown."""

    local_url: str               # "/api/images/searched/{hash}.{ext}"
    local_path: Path             # absolute filesystem path
    source_url: str              # original URL
    source_page: str
    title: str
    alt: str
    content_type: str
    size_bytes: int
    hash: str                    # 16-char sha256 prefix
    fetched_at: str              # ISO 8601 UTC

    def to_injectable_dict(self) -> dict:
        """Shape that `inject_images_into_report` consumes (mirrors image_search dict)."""
        return {
            "url": self.local_url,
            "source_page": self.source_page,
            "title": self.title,
            "alt": self.alt,
            "width": 0,
            "height": 0,
            "thumbnail": self.local_url,
            "license": None,
            "proxy_url": None,
            "_localized": True,
        }


@dataclasses.dataclass(frozen=True)
class DownloadFailure:
    """A non-fatal failure record; caller falls back to source URL."""

    source_url: str
    reason: str                  # http_4xx / timeout / too_large / invalid_content_type / network_error / missing_url / local_write_failed
    attempts: int


LocalizationResult = Union[LocalizedAsset, DownloadFailure]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def localize_image(
    asset: dict,
    *,
    owner: Optional[str] = None,
    course_id: Optional[str] = None,
    storage_root: Optional[Path] = None,
    timeout_s: Optional[float] = None,
    max_bytes: Optional[int] = None,
) -> LocalizationResult:
    """Download a single image_search asset and write sidecar JSON.

    Idempotent: returns the cached LocalizedAsset (and updates sidecar's
    accessed_by / course_ids) when the file already exists on disk.
    """
    source_url = str(asset.get("url") or "").strip()
    if not source_url:
        return DownloadFailure(source_url="", reason="missing_url", attempts=0)

    storage_root = storage_root or Path(Config.SEARCHED_IMAGE_STORAGE_ROOT)
    timeout_s = timeout_s if timeout_s is not None else float(Config.SEARCHED_IMAGE_DOWNLOAD_TIMEOUT_S)
    max_bytes = max_bytes if max_bytes is not None else int(Config.SEARCHED_IMAGE_MAX_BYTES)

    hash_ = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]

    # Cache hit: look for existing {hash}.{ext} under any date partition
    cached_path = _find_existing(storage_root, hash_)
    if cached_path is not None:
        _merge_sidecar_attribution(cached_path, owner=owner, course_id=course_id)
        return _build_localized_from_cache(cached_path, hash_, source_url, asset)

    # Cold path — actual HTTP download
    ext_hint = _extension_from_url(source_url)
    today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
    date_dir = storage_root / today
    try:
        date_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return _record_failure(storage_root, hash_, source_url, owner, course_id,
                                reason="local_write_failed", attempts=0)

    attempts = 0
    last_failure_reason: Optional[str] = None
    for attempt in range(2):  # 1 initial + 1 retry
        attempts = attempt + 1
        try:
            result = _do_download(
                source_url=source_url,
                hash_=hash_,
                ext_hint=ext_hint,
                date_dir=date_dir,
                timeout_s=timeout_s,
                max_bytes=max_bytes,
            )
        except _NonRetryableError as exc:
            last_failure_reason = exc.reason
            break
        except _RetryableError as exc:
            last_failure_reason = exc.reason
            if attempt == 0:
                time.sleep(1)
                continue
            break
        else:
            # Success — write sidecar + return
            _write_sidecar(
                result.local_path,
                source_url=source_url,
                source_page=str(asset.get("source_page") or ""),
                title=str(asset.get("title") or ""),
                content_type=result.content_type,
                size_bytes=result.size_bytes,
                fetched_at=result.fetched_at,
                owner=owner,
                course_id=course_id,
                provider=str((asset.get("provenance") or {}).get("provider") or ""),
                downloaded=True,
            )
            return LocalizedAsset(
                local_url=_local_url_for(result.local_path),
                local_path=result.local_path,
                source_url=source_url,
                source_page=str(asset.get("source_page") or ""),
                title=str(asset.get("title") or ""),
                alt=str(asset.get("alt") or asset.get("title") or "图片"),
                content_type=result.content_type,
                size_bytes=result.size_bytes,
                hash=hash_,
                fetched_at=result.fetched_at,
            )

    return _record_failure(
        storage_root, hash_, source_url, owner, course_id,
        reason=last_failure_reason or "unknown", attempts=attempts,
    )


def batch_localize(
    assets: list[dict],
    *,
    owner: Optional[str] = None,
    course_id: Optional[str] = None,
    storage_root: Optional[Path] = None,
    max_workers: int = 4,
) -> list[LocalizationResult]:
    """Localize multiple assets concurrently.

    Concurrency cap = 4 to avoid bursting a single source. Returns results
    in input order so callers can zip with the original asset list.
    """
    if not assets:
        return []
    cap = max(1, min(max_workers, len(assets)))
    with ThreadPoolExecutor(max_workers=cap) as pool:
        return list(pool.map(
            lambda a: localize_image(
                a, owner=owner, course_id=course_id, storage_root=storage_root,
            ),
            assets,
        ))


def start_async_localization(
    assets: list[dict],
    *,
    owner: Optional[str] = None,
    course_id: Optional[str] = None,
    storage_root: Optional[Path] = None,
    max_workers: int = 4,
):
    """Kick off batch_localize in a background thread; return a Future.

    Used by generate_report to overlap downloads with LLM body generation:
    fire this before build_report_markdown(), join with `resolve_async_localization`
    after the long-running LLM step completes.
    """
    import concurrent.futures

    if not assets:
        f: concurrent.futures.Future = concurrent.futures.Future()
        f.set_result([])
        return f

    # Use an isolated executor so it shuts down cleanly after the work is done.
    executor = ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(assets))))
    future = executor.submit(
        batch_localize,
        assets,
        owner=owner,
        course_id=course_id,
        storage_root=storage_root,
        max_workers=max_workers,
    )
    future.add_done_callback(lambda _f: executor.shutdown(wait=False))
    return future


def resolve_async_localization(
    future,
    original_assets: list[dict],
    *,
    extra_timeout_s: float = 5.0,
) -> list[dict]:
    """Wait for localization (with extra timeout) and produce a merged asset list.

    Each output asset uses the localized URL on success. Failed or timed-out
    downloads are omitted so unsafe, dead, or unverified external URLs never
    leak back into generated resources.
    """
    import concurrent.futures

    try:
        results: list[LocalizationResult] = future.result(timeout=extra_timeout_s)
    except (concurrent.futures.TimeoutError, Exception):
        results = []

    merged: list[dict] = []
    for i, original in enumerate(original_assets):
        result = results[i] if i < len(results) else None
        if isinstance(result, LocalizedAsset):
            payload = result.to_injectable_dict()
            # Carry over original alt/title if downloader didn't pick them up
            payload.setdefault("title", str(original.get("title") or ""))
            payload["alt"] = str(
                original.get("alt") or original.get("title") or payload.get("alt") or "图片"
            )
            merged.append(payload)
        else:
            continue
    return merged


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

class _RetryableError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class _NonRetryableError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _validate_public_image_url(value: str) -> None:
    parsed = urlparse(str(value or ""))
    hostname = (parsed.hostname or "").strip().lower()
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise _NonRetryableError("unsafe_url")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise _NonRetryableError("unsafe_url")

    addresses: set[str] = set()
    try:
        addresses.add(str(ipaddress.ip_address(hostname)))
    except ValueError:
        try:
            for info in socket.getaddrinfo(hostname, parsed.port or 443):
                addresses.add(str(info[4][0]))
        except OSError:
            return
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if not ip.is_global:
            raise _NonRetryableError("unsafe_url")


@dataclasses.dataclass
class _DownloadOutcome:
    local_path: Path
    content_type: str
    size_bytes: int
    fetched_at: str


def _do_download(
    *,
    source_url: str,
    hash_: str,
    ext_hint: Optional[str],
    date_dir: Path,
    timeout_s: float,
    max_bytes: int,
) -> _DownloadOutcome:
    _validate_public_image_url(source_url)
    headers = {
        "User-Agent": getattr(Config, "SEARCHED_IMAGE_USER_AGENT", None) or _BROWSER_UA_FALLBACK,
        # Intentionally NO Referer — hotlink-protected sites care about it.
        "Accept": "image/*,*/*;q=0.8",
    }

    transport = httpx.HTTPTransport()
    try:
        def validate_redirect_request(request: httpx.Request) -> None:
            _validate_public_image_url(str(request.url))

        with httpx.Client(
            transport=transport,
            timeout=timeout_s,
            follow_redirects=True,
            max_redirects=3,
            event_hooks={"request": [validate_redirect_request]},
        ) as client:
            try:
                # Preflight HEAD-ish: just look at headers via streaming GET.
                with client.stream("GET", source_url, headers=headers) as resp:
                    status = resp.status_code
                    if status == 403 or status == 404 or 400 <= status < 500:
                        raise _NonRetryableError(f"http_{status}")
                    if status >= 500:
                        raise _RetryableError(f"http_{status}")
                    if status != 200:
                        raise _RetryableError(f"http_{status}")

                    content_type = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                    if content_type and not content_type.startswith("image/"):
                        raise _NonRetryableError("invalid_content_type")

                    declared_length = _safe_int(resp.headers.get("content-length"))
                    if declared_length and declared_length > max_bytes:
                        raise _NonRetryableError("too_large")

                    ext = _extension_from_content_type(content_type) or ext_hint or "bin"
                    if ext not in _ALLOWED_EXTS:
                        raise _NonRetryableError("invalid_content_type")

                    final_path = date_dir / f"{hash_}.{ext}"
                    tmp_path = date_dir / f"{hash_}.{ext}.part"

                    total = 0
                    try:
                        with tmp_path.open("wb") as fp:
                            for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                                if not chunk:
                                    continue
                                total += len(chunk)
                                if total > max_bytes:
                                    raise _NonRetryableError("too_large")
                                fp.write(chunk)
                    except OSError:
                        _safe_unlink(tmp_path)
                        raise _NonRetryableError("local_write_failed")
                    except _NonRetryableError:
                        _safe_unlink(tmp_path)
                        raise

                    try:
                        tmp_path.replace(final_path)
                    except OSError:
                        _safe_unlink(tmp_path)
                        raise _NonRetryableError("local_write_failed")

                    return _DownloadOutcome(
                        local_path=final_path,
                        content_type=content_type or f"image/{ext}",
                        size_bytes=total,
                        fetched_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
                    )
            except httpx.TimeoutException:
                raise _RetryableError("timeout")
            except httpx.HTTPError:
                raise _RetryableError("network_error")
    except (_NonRetryableError, _RetryableError):
        raise
    except Exception:
        raise _RetryableError("network_error")


def _find_existing(storage_root: Path, hash_: str) -> Optional[Path]:
    """Search any date partition for {hash}.{ext}."""
    if not storage_root.exists():
        return None
    for ext in _ALLOWED_EXTS:
        # date partitions are non-deterministic — list and scan
        for date_dir in storage_root.iterdir():
            if not date_dir.is_dir():
                continue
            candidate = date_dir / f"{hash_}.{ext}"
            if candidate.exists():
                return candidate
    return None


def _build_localized_from_cache(
    path: Path, hash_: str, source_url: str, asset: dict
) -> LocalizedAsset:
    sidecar = _read_sidecar(path)
    return LocalizedAsset(
        local_url=_local_url_for(path),
        local_path=path,
        source_url=source_url,
        source_page=str(sidecar.get("source_page") or asset.get("source_page") or ""),
        title=str(sidecar.get("title") or asset.get("title") or ""),
        alt=str(asset.get("alt") or asset.get("title") or sidecar.get("title") or "图片"),
        content_type=str(sidecar.get("content_type") or _guess_mime_from_path(path)),
        size_bytes=int(sidecar.get("size_bytes") or path.stat().st_size),
        hash=hash_,
        fetched_at=str(sidecar.get("fetched_at") or _dt.datetime.now(_dt.timezone.utc).isoformat()),
    )


def _record_failure(
    storage_root: Path, hash_: str, source_url: str,
    owner: Optional[str], course_id: Optional[str],
    *, reason: str, attempts: int,
) -> DownloadFailure:
    """Write a sidecar describing the failure (no image file), and return DownloadFailure."""
    today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
    date_dir = storage_root / today
    try:
        date_dir.mkdir(parents=True, exist_ok=True)
        sidecar_path = date_dir / f"{hash_}.json"
        existing = _read_sidecar_path(sidecar_path)
        record = {
            **existing,
            "hash": hash_,
            "source_url": source_url,
            "downloaded": False,
            "failure_reason": reason,
            "attempts": attempts,
            "attempted_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        _accumulate(record, "accessed_by", owner)
        _accumulate(record, "course_ids", course_id)
        sidecar_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # sidecar writing best-effort; never let it propagate
    return DownloadFailure(source_url=source_url, reason=reason, attempts=attempts)


def _write_sidecar(
    image_path: Path,
    *,
    source_url: str,
    source_page: str,
    title: str,
    content_type: str,
    size_bytes: int,
    fetched_at: str,
    owner: Optional[str],
    course_id: Optional[str],
    provider: str,
    downloaded: bool,
) -> None:
    sidecar_path = image_path.with_suffix(".json")
    existing = _read_sidecar_path(sidecar_path)
    record = {
        **existing,
        "hash": image_path.stem,
        "source_url": source_url,
        "source_page": source_page,
        "title": title,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "fetched_at": existing.get("fetched_at") or fetched_at,
        "last_accessed_at": fetched_at,
        "downloaded": downloaded,
        "provider": provider or existing.get("provider", ""),
    }
    _accumulate(record, "accessed_by", owner)
    _accumulate(record, "course_ids", course_id)
    try:
        sidecar_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _merge_sidecar_attribution(
    image_path: Path, *, owner: Optional[str], course_id: Optional[str]
) -> None:
    """Cache hit path: update sidecar's accessed_by / course_ids / last_accessed_at."""
    sidecar_path = image_path.with_suffix(".json")
    record = _read_sidecar_path(sidecar_path)
    if not record:
        # Sidecar lost — regenerate minimal record so we don't lose attribution chain
        record = {
            "hash": image_path.stem,
            "source_url": "",
            "downloaded": True,
            "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
    changed = False
    if _accumulate(record, "accessed_by", owner):
        changed = True
    if _accumulate(record, "course_ids", course_id):
        changed = True
    record["last_accessed_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    try:
        sidecar_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        if changed:
            pass  # best-effort


def _accumulate(record: dict, key: str, value: Optional[str]) -> bool:
    """Append `value` to record[key] (a list of unique strings) if non-empty + new. Returns True if added."""
    if not value:
        return False
    existing = list(record.get(key) or [])
    if value in existing:
        return False
    existing.append(value)
    record[key] = existing
    return True


def _read_sidecar(image_path: Path) -> dict:
    return _read_sidecar_path(image_path.with_suffix(".json"))


def _read_sidecar_path(sidecar_path: Path) -> dict:
    try:
        if sidecar_path.exists():
            return json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _local_url_for(local_path: Path) -> str:
    return f"/api/images/searched/{local_path.name}"


def _extension_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    last = parsed.path.rsplit("/", 1)[-1]
    if "." not in last:
        return None
    ext = last.rsplit(".", 1)[-1].lower()
    if "?" in ext:
        ext = ext.split("?", 1)[0]
    return ext if ext in _ALLOWED_EXTS else None


def _extension_from_content_type(content_type: str) -> Optional[str]:
    return _MIME_TO_EXT.get(content_type)


def _guess_mime_from_path(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
