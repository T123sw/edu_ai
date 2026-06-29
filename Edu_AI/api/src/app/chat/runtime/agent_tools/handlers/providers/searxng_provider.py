"""SearXNG image search provider.

Endpoint: GET {base_url}/search?q=...&categories=images&format=json&safesearch=...

SearXNG returns a JSON body shaped like:
    {
      "results": [
        {
          "url":            "<page url>",
          "img_src":        "<image url>",
          "thumbnail_src":  "<thumbnail url>",
          "title":          "...",
          "resolution":     "1920x1080",     # may be absent
          "img_width":      1920,            # may be absent
          "img_height":     1080,            # may be absent
          "source":         "...",
          "engine":         "google images",
        },
        ...
      ]
    }
"""
from __future__ import annotations

import httpx


class SearxngImageSearchProvider:
    name = "searxng"

    def __init__(self, *, base_url: str, timeout: float = 8.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def search(
        self,
        *,
        query: str,
        count: int,
        style: str,
        safe: bool,
        license_: str,  # noqa: ARG002 — SearXNG has no license filter, accepted for interface parity
        owner: str | None,  # noqa: ARG002 — unused; reserved for future per-tenant quotas
    ) -> list[dict]:
        params = {
            "q": _build_query(query, style),
            "categories": "images",
            "format": "json",
            "safesearch": "1" if safe else "0",
        }
        # SearXNG ≥ 2024 ships with granian, which 502s the /search endpoint
        # when the client sends Accept-Encoding (httpx default: "gzip,deflate,zstd").
        # Workaround: use an explicit transport (default Client pool somehow
        # poisons subsequent connections) and strip the encoding negotiation
        # header on the outgoing request.
        transport = httpx.HTTPTransport()
        with httpx.Client(transport=transport, timeout=self._timeout) as client:
            req = client.build_request("GET", f"{self._base}/search", params=params)
            req.headers.pop("accept-encoding", None)
            resp = client.send(req)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results") or []
        out: list[dict] = []
        # 3x oversample — handler heuristic filtering will trim further.
        for item in results[: max(count * 3, count)]:
            width, height = _resolve_dimensions(item)
            url = item.get("img_src") or item.get("url") or ""
            if not url:
                continue
            out.append({
                "url": url,
                "source_page": item.get("url") or "",
                "title": (item.get("title") or "").strip(),
                "width": width,
                "height": height,
                "thumbnail": item.get("thumbnail_src") or item.get("thumbnail") or "",
                "license": None,
                "_provider": self.name,
            })
        return out


def _build_query(query: str, style: str) -> str:
    """SearXNG has no `style` parameter — encode it as query weighting."""
    suffix = {
        "diagram": " diagram OR flowchart OR architecture",
        "chart":   " chart OR graph OR plot",
        "real":    " photo OR photograph",
        "any":     "",
    }.get(style, "")
    return query + suffix


def _resolve_dimensions(item: dict) -> tuple[int, int]:
    width = _safe_int(item.get("img_width"))
    height = _safe_int(item.get("img_height"))
    if width and height:
        return width, height
    resolution = str(item.get("resolution") or "")
    if "x" in resolution:
        parts = resolution.split("x", 1)
        width = width or _safe_int(parts[0])
        height = height or _safe_int(parts[1])
    return width, height


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
