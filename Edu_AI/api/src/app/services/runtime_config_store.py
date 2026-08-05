"""Encrypted, versioned runtime provider configuration storage.

Secrets are never serialized as plaintext. Each revision is immutable except
for lifecycle metadata, and publication uses an atomic replace so an interrupted
write cannot destroy the last active configuration.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.config import Config


ProviderKey = Literal[
    "llm",
    "embedding",
    "tts",
    "web_search",
    "pdf_parser",
    "classroom",
]
ScopeKey = Literal["user", "system"]

PROVIDER_FIELDS: dict[str, tuple[str, ...]] = {
    "llm": ("base_url", "api_key", "model"),
    "embedding": ("base_url", "api_key", "model", "dimensions"),
    "tts": ("base_url", "api_key", "model", "voice"),
    "web_search": ("base_url", "api_key", "model"),
    "pdf_parser": ("base_url", "api_key", "model"),
    "classroom": ("base_url", "api_key", "model"),
}
SECRET_FIELDS = {"api_key", "secret_key", "access_token", "token"}
VALID_STATES = {"draft", "verified", "invalid", "active", "superseded"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:3]}••••••{value[-3:]}"


class RuntimeConfigStore:
    _lock = threading.RLock()

    def __init__(self, root: Path | None = None, master_key: str | None = None):
        self.root = Path(root or Config.RUNTIME_CONFIG_ROOT)
        source_key = (
            master_key
            or os.getenv("RUNTIME_CONFIG_MASTER_KEY")
            or os.getenv("JWT_SECRET_KEY")
            or "edu-ai-local-runtime-config-key"
        )
        self._cipher = AESGCM(hashlib.sha256(source_key.encode("utf-8")).digest())

    def create_draft(
        self,
        *,
        scope: ScopeKey,
        owner_id: str,
        provider: ProviderKey,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_identity(scope=scope, owner_id=owner_id, provider=provider)
        normalized = self._normalize_values(provider, values)
        revision = {
            "revision_id": f"rcfg_{uuid4().hex}",
            "status": "draft",
            "created_at": _now_iso(),
            "verified_at": None,
            "activated_at": None,
            "validation_error": None,
            "payload_fingerprint": hashlib.sha256(
                json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
            "encrypted_payload": self._encrypt(normalized),
        }
        with self._lock:
            record = self._load_record(scope, owner_id, provider)
            record["revisions"].append(revision)
            self._write_record(scope, owner_id, provider, record)
        return self._public_revision(revision, normalized)

    def get_revision(
        self,
        *,
        scope: ScopeKey,
        owner_id: str,
        provider: ProviderKey,
        revision_id: str,
        include_values: bool = False,
    ) -> dict[str, Any] | None:
        self._validate_identity(scope=scope, owner_id=owner_id, provider=provider)
        record = self._load_record(scope, owner_id, provider)
        revision = next(
            (item for item in record["revisions"] if item["revision_id"] == revision_id),
            None,
        )
        if revision is None:
            return None
        values = self._decrypt(revision["encrypted_payload"])
        return (
            {**revision, "values": values}
            if include_values
            else self._public_revision(revision, values)
        )

    def list_provider(
        self,
        *,
        scope: ScopeKey,
        owner_id: str,
        provider: ProviderKey,
    ) -> dict[str, Any]:
        self._validate_identity(scope=scope, owner_id=owner_id, provider=provider)
        record = self._load_record(scope, owner_id, provider)
        revisions = [
            self._public_revision(item, self._decrypt(item["encrypted_payload"]))
            for item in reversed(record["revisions"])
        ]
        return {
            "scope": scope,
            "owner_id": owner_id,
            "provider": provider,
            "active_revision_id": record.get("active_revision_id"),
            "revisions": revisions,
        }

    def mark_verification(
        self,
        *,
        scope: ScopeKey,
        owner_id: str,
        provider: ProviderKey,
        revision_id: str,
        ok: bool,
        error: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            record = self._load_record(scope, owner_id, provider)
            revision = self._require_revision(record, revision_id)
            if revision["status"] == "active":
                raise ValueError("active configuration cannot be re-verified")
            revision["status"] = "verified" if ok else "invalid"
            revision["verified_at"] = _now_iso()
            revision["validation_error"] = None if ok else _clean(error)[:500]
            self._write_record(scope, owner_id, provider, record)
            return self._public_revision(
                revision, self._decrypt(revision["encrypted_payload"])
            )

    def activate(
        self,
        *,
        scope: ScopeKey,
        owner_id: str,
        provider: ProviderKey,
        revision_id: str,
    ) -> dict[str, Any]:
        with self._lock:
            record = self._load_record(scope, owner_id, provider)
            revision = self._require_revision(record, revision_id)
            if revision["status"] != "verified":
                raise ValueError("only a verified configuration can be activated")
            current_id = record.get("active_revision_id")
            if current_id:
                current = self._require_revision(record, current_id)
                current["status"] = "superseded"
            revision["status"] = "active"
            revision["activated_at"] = _now_iso()
            record["active_revision_id"] = revision_id
            self._write_record(scope, owner_id, provider, record)
            return self._public_revision(
                revision, self._decrypt(revision["encrypted_payload"])
            )

    def rollback(
        self,
        *,
        scope: ScopeKey,
        owner_id: str,
        provider: ProviderKey,
    ) -> dict[str, Any]:
        with self._lock:
            record = self._load_record(scope, owner_id, provider)
            current_id = record.get("active_revision_id")
            candidates = [
                item
                for item in reversed(record["revisions"])
                if item["revision_id"] != current_id
                and item["status"] in {"verified", "superseded"}
                and item.get("verified_at")
            ]
            if not candidates:
                raise ValueError("no verified configuration is available for rollback")
            if current_id:
                self._require_revision(record, current_id)["status"] = "superseded"
            previous = candidates[0]
            previous["status"] = "active"
            previous["activated_at"] = _now_iso()
            record["active_revision_id"] = previous["revision_id"]
            self._write_record(scope, owner_id, provider, record)
            return self._public_revision(
                previous, self._decrypt(previous["encrypted_payload"])
            )

    def get_active_values(
        self,
        *,
        scope: ScopeKey,
        owner_id: str,
        provider: ProviderKey,
        revision_id: str | None = None,
    ) -> tuple[str, dict[str, Any]] | None:
        record = self._load_record(scope, owner_id, provider)
        selected_id = revision_id or record.get("active_revision_id")
        if not selected_id:
            return None
        revision = next(
            (item for item in record["revisions"] if item["revision_id"] == selected_id),
            None,
        )
        if revision is None or (revision_id is None and revision["status"] != "active"):
            return None
        return revision["revision_id"], self._decrypt(revision["encrypted_payload"])

    def _normalize_values(self, provider: str, values: dict[str, Any]) -> dict[str, Any]:
        allowed = PROVIDER_FIELDS[provider]
        unknown = sorted(set(values) - set(allowed))
        if unknown:
            raise ValueError(f"unsupported configuration fields: {', '.join(unknown)}")
        normalized = {
            field: (int(value) if field == "dimensions" and value not in (None, "") else _clean(value))
            for field, value in values.items()
            if value not in (None, "")
        }
        if not _clean(normalized.get("base_url")):
            raise ValueError("base_url is required")
        if not _clean(normalized.get("api_key")):
            raise ValueError("api_key is required")
        if provider in {"llm", "embedding", "tts"} and not _clean(normalized.get("model")):
            raise ValueError("model is required")
        return normalized

    @staticmethod
    def _validate_identity(*, scope: str, owner_id: str, provider: str) -> None:
        if scope not in {"user", "system"}:
            raise ValueError("invalid configuration scope")
        if provider not in PROVIDER_FIELDS:
            raise ValueError("invalid provider")
        if not _clean(owner_id):
            raise ValueError("owner_id is required")

    @staticmethod
    def _require_revision(record: dict[str, Any], revision_id: str) -> dict[str, Any]:
        revision = next(
            (item for item in record["revisions"] if item["revision_id"] == revision_id),
            None,
        )
        if revision is None:
            raise KeyError(revision_id)
        if revision.get("status") not in VALID_STATES:
            raise ValueError("invalid configuration state")
        return revision

    def _path(self, scope: str, owner_id: str, provider: str) -> Path:
        safe_owner = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:24]
        return self.root / scope / safe_owner / f"{provider}.json"

    def _load_record(self, scope: str, owner_id: str, provider: str) -> dict[str, Any]:
        path = self._path(scope, owner_id, provider)
        if not path.exists():
            return {
                "schema_version": 1,
                "scope": scope,
                "owner_id_hash": hashlib.sha256(owner_id.encode("utf-8")).hexdigest(),
                "provider": provider,
                "active_revision_id": None,
                "revisions": [],
            }
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("runtime configuration store is unreadable") from exc
        if value.get("provider") != provider or not isinstance(value.get("revisions"), list):
            raise RuntimeError("runtime configuration store is invalid")
        return value

    def _write_record(
        self, scope: str, owner_id: str, provider: str, record: dict[str, Any]
    ) -> None:
        path = self._path(scope, owner_id, provider)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        serialized = json.dumps(record, ensure_ascii=False, indent=2)
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)

    def _encrypt(self, values: dict[str, Any]) -> str:
        nonce = os.urandom(12)
        plaintext = json.dumps(values, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ciphertext = self._cipher.encrypt(nonce, plaintext, b"edu-ai-runtime-config-v1")
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def _decrypt(self, token: str) -> dict[str, Any]:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        plaintext = self._cipher.decrypt(
            raw[:12], raw[12:], b"edu-ai-runtime-config-v1"
        )
        return json.loads(plaintext.decode("utf-8"))

    @staticmethod
    def _public_revision(
        revision: dict[str, Any], values: dict[str, Any]
    ) -> dict[str, Any]:
        public_values = {
            key: (_mask_secret(_clean(value)) if key in SECRET_FIELDS else value)
            for key, value in values.items()
        }
        return {
            "revision_id": revision["revision_id"],
            "status": revision["status"],
            "created_at": revision["created_at"],
            "verified_at": revision.get("verified_at"),
            "activated_at": revision.get("activated_at"),
            "validation_error": revision.get("validation_error"),
            "values": public_values,
        }


runtime_config_store = RuntimeConfigStore()
