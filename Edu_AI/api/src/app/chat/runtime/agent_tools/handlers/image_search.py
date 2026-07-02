"""image_search tool handler (Phase 6-A).

Reads provider from ctx.image_search_provider and applies heuristic filtering
to produce a clean list of image candidates. VisionReflector takes over from
here to do VLM-based quality / relevance review.

Returned payload shape (consumed by VisionReflector and downstream):
    {
        "images": [
            {
                "url": str,
                "source_page": str,
                "title": str,
                "width": int,
                "height": int,
                "thumbnail": str,
                "license": str | None,
                "proxy_url": None,         # reserved for Phase >6-A image proxy
                "provenance": {
                    "provider": str,
                    "fetched_at": str,     # ISO 8601 UTC
                },
            },
            ...
        ],
        "query": str,
        "trace": {
            "provider": str,
            "raw_count": int,
            "filtered_count": int,
        },
    }
"""
from __future__ import annotations

import datetime as _dt
from urllib.parse import urlparse

from app.chat.runtime.agent_tools.result import error_result, ok_result


_BLOCKED_HOSTS = frozenset({
    # Social/walled gardens — usually login-gated or low education value
    "pinterest.com",
    "pinimg.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    # Consumer photo CDNs — almost never relevant for technical/教学 diagrams
    # and Qwen DashScope (China) frequently times out fetching them for VLM review.
    "flickr.com",
    "staticflickr.com",
    "live.staticflickr.com",
    "500px.com",
})

_ALLOWED_EXT = frozenset({"jpg", "jpeg", "png", "webp", "gif"})

_MIN_DIMENSION = 200
_MAX_COUNT = 12
_DEFAULT_COUNT = 6


def handle_image_search(name: str, args: dict, ctx) -> dict:
    query = str(args.get("query", "")).strip()
    if not query:
        return error_result("image_search", "empty_query", "搜索词为空")

    count = max(1, min(_safe_int(args.get("count"), _DEFAULT_COUNT), _MAX_COUNT))
    style = str(args.get("style", "any") or "any")
    safe = bool(args.get("safe", True))
    license_ = str(args.get("license", "any") or "any")

    provider = getattr(ctx, "image_search_provider", None)
    if provider is None:
        return error_result(
            "image_search",
            "provider_not_configured",
            "未配置图片搜索 provider（检查 IMAGE_SEARCH_PROVIDER=bocha / BOCHA_API_KEY）",
        )

    owner = getattr(getattr(ctx, "request", None), "owner", None)

    try:
        raw = provider.search(
            query=query,
            count=count,
            style=style,
            safe=safe,
            license_=license_,
            owner=owner,
        )
    except Exception as exc:  # noqa: BLE001 — surface provider errors verbatim
        return error_result(
            "image_search",
            type(exc).__name__,
            f"图片搜索失败: {exc}",
        )

    raw = list(raw or [])
    candidates = [_normalize(img) for img in raw if _passes_heuristics(img)]
    candidates = _dedup_by_source(candidates)[:count]

    return ok_result(
        tool="image_search",
        summary=f"搜到 {len(candidates)} 张候选图（原始 {len(raw)}，过滤后 {len(candidates)}）",
        payload={
            "images": candidates,
            "query": query,
            "trace": {
                "provider": getattr(provider, "name", "unknown"),
                "raw_count": len(raw),
                "filtered_count": len(candidates),
            },
        },
    )


def _passes_heuristics(img: dict) -> bool:
    if _safe_int(img.get("width"), 0) < _MIN_DIMENSION:
        return False
    if _safe_int(img.get("height"), 0) < _MIN_DIMENSION:
        return False
    url = str(img.get("url") or "")
    if not url:
        return False
    path = url.split("?", 1)[0]
    ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    if ext not in _ALLOWED_EXT:
        return False
    host = (urlparse(url).hostname or "").lower()
    return not _is_blocked_host(host)


def _is_blocked_host(host: str) -> bool:
    """Match exact host or proper subdomain — never a substring like 'ex.com' vs 'x.com'."""
    for blocked in _BLOCKED_HOSTS:
        if host == blocked or host.endswith("." + blocked):
            return True
    return False


def _normalize(img: dict) -> dict:
    url = _absolutize(str(img["url"]))
    thumbnail = _absolutize(str(img.get("thumbnail") or url))
    return {
        "url": url,
        "source_page": str(img.get("source_page") or ""),
        "title": str(img.get("title") or "")[:200],
        "width": _safe_int(img.get("width"), 0),
        "height": _safe_int(img.get("height"), 0),
        "thumbnail": thumbnail,
        "license": img.get("license"),
        "proxy_url": None,
        "provenance": {
            "provider": str(img.get("_provider", "unknown")),
            "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        },
    }


def _absolutize(url: str) -> str:
    """Normalize protocol-relative URLs (//host/...) to https://; pass through others."""
    if url.startswith("//"):
        return "https:" + url
    return url


def _dedup_by_source(images: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for img in images:
        key = img["source_page"] or img["url"]
        if key in seen:
            continue
        seen.add(key)
        out.append(img)
    return out


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
