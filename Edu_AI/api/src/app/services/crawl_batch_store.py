from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from core import Config


def _root() -> Path:
    path = Config.STORAGE_ROOT / "crawl_batches"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_crawl_batch(crawl_batch: Any) -> str:
    batch_id = getattr(crawl_batch, "batch_id", "") or f"batch_{int(datetime.now().timestamp() * 1000)}"
    payload = _to_dict(crawl_batch)
    payload["batch_id"] = batch_id
    for key in ("total_urls", "success_count", "failed_count"):
        if hasattr(crawl_batch, key):
            payload[key] = getattr(crawl_batch, key)
    created_at = payload.get("created_at")
    if hasattr(created_at, "isoformat"):
        payload["created_at"] = created_at.isoformat()
    (_root() / f"{batch_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return batch_id


def load_crawl_batch(batch_id: str) -> dict | None:
    path = _root() / f"{batch_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_batches(*, limit: int = 20) -> list[dict]:
    files = sorted(_root().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    batches: list[dict] = []
    for path in files[: max(1, int(limit or 20))]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        batches.append(
            {
                "batch_id": data.get("batch_id"),
                "query": data.get("query"),
                "total_urls": data.get("total_urls"),
                "success_count": data.get("success_count"),
                "failed_count": data.get("failed_count"),
                "created_at": data.get("created_at"),
            }
        )
    return batches


def _to_dict(value: Any):
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [_to_dict(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_dict(v) for k, v in value.items()}
    return value
