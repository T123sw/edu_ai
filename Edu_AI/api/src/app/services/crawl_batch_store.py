from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from core import Config


def _uses_postgres() -> bool:
    import os

    return str(os.getenv("APP_STATE_PERSISTENCE_MODE", "json")).strip().lower() == "postgres"


def _repository():
    from app.persistence.dependencies import get_postgres_app_state_repository

    return get_postgres_app_state_repository()


def _root() -> Path:
    path = Config.STORAGE_ROOT / "crawl_batches"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_crawl_batch(crawl_batch: Any, *, owner: str | None = None) -> str:
    batch_id = getattr(crawl_batch, "batch_id", "") or f"batch_{int(datetime.now().timestamp() * 1000)}"
    payload = _to_dict(crawl_batch)
    payload["batch_id"] = batch_id
    payload["owner_user_id"] = str(owner or "").strip() or None
    for key in ("total_urls", "success_count", "failed_count"):
        if hasattr(crawl_batch, key):
            payload[key] = getattr(crawl_batch, key)
    created_at = payload.get("created_at")
    if hasattr(created_at, "isoformat"):
        payload["created_at"] = created_at.isoformat()
    if _uses_postgres():
        _repository().put("crawl_batches", batch_id, payload, owner_user_id=owner)
    else:
        (_root() / f"{batch_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return batch_id


def load_crawl_batch(batch_id: str, *, owner: str | None = None) -> dict | None:
    if _uses_postgres():
        payload = _repository().get("crawl_batches", batch_id)
        if payload is None:
            return None
        normalized_owner = str(owner or "").strip()
        if normalized_owner and str(payload.get("owner_user_id") or "").strip() != normalized_owner:
            return None
        return payload
    path = _root() / f"{batch_id}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    normalized_owner = str(owner or "").strip()
    if normalized_owner and str(payload.get("owner_user_id") or "").strip() != normalized_owner:
        return None
    return payload


def list_batches(*, limit: int = 20, owner: str | None = None) -> list[dict]:
    batches: list[dict] = []
    normalized_owner = str(owner or "").strip()
    if _uses_postgres():
        records = _repository().list("crawl_batches")
    else:
        files = sorted(_root().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        records = []
        for path in files:
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
    for data in records:
        if normalized_owner and str(data.get("owner_user_id") or "").strip() != normalized_owner:
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
        if len(batches) >= max(1, int(limit or 20)):
            break
    return batches


def _to_dict(value: Any):
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [_to_dict(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_dict(v) for k, v in value.items()}
    return value
