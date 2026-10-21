"""Resolve environment, system and user provider settings with snapshot support."""

from __future__ import annotations

import os
from contextvars import ContextVar, Token
from typing import Any

from core.config import Config

from app.services.runtime_config_store import PROVIDER_FIELDS, RuntimeConfigStore, runtime_config_store


_runtime_owner: ContextVar[str | None] = ContextVar("runtime_config_owner", default=None)
_runtime_snapshot: ContextVar[dict[str, str] | None] = ContextVar(
    "runtime_config_snapshot", default=None
)


ENVIRONMENT_DEFAULTS: dict[str, dict[str, Any]] = {
    "llm": {
        "provider_name": "environment",
        "base_url": Config.DEEP_MODEL_API_BASE,
        "api_key": Config.resolve_llm_api_key(
            Config.DEEP_MODEL_API_BASE,
            Config.DEEP_MODEL_API_KEY,
        ),
        "model": Config.LLM_MODEL_DEEP,
        "timeout_seconds": 120,
    },
    "embedding": {
        "provider_name": "environment",
        "base_url": Config.EMBEDDING_API_BASE,
        "api_key": Config.OPENROUTER_API_KEY,
        "model": Config.EMBEDDING_MODEL,
        "dimensions": Config.GEMINI_EMBEDDING_DIMENSIONS,
        "timeout_seconds": Config.EMBEDDING_TIMEOUT_SEC,
    },
    "tts": {
        "provider_name": os.getenv("TTS_PROVIDER_NAME", "local-qwen-tts"),
        "base_url": Config.TTS_API_BASE,
        "api_key": os.getenv("TTS_API_KEY", os.getenv("LOCAL_TTS_API_KEY", "")),
        "model": Config.TTS_MODEL,
        "voice": Config.TTS_VOICE,
        "timeout_seconds": Config.TTS_TIMEOUT_SECONDS,
    },
    "web_search": {
        "provider_name": "environment",
        "base_url": "",
        "api_key": "",
        "model": Config.IMAGE_SEARCH_PROVIDER,
        "timeout_seconds": 15,
    },
    "pdf_parser": {
        "provider_name": "environment",
        "base_url": "",
        "api_key": "",
        "model": "",
        "timeout_seconds": 60,
    },
    "classroom": {
        "provider_name": "environment",
        "base_url": "",
        "api_key": "",
        "model": "",
        "timeout_seconds": 60,
    },
}


class RuntimeConfigResolver:
    def __init__(self, store: RuntimeConfigStore | None = None):
        self.store = store or runtime_config_store

    def capture_snapshot(self, owner_user_id: str) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for provider in PROVIDER_FIELDS:
            if provider in {"tts", "classroom"}:
                continue
            user = self.store.get_active_values(
                scope="user", owner_id=owner_user_id, provider=provider
            )
            if user:
                snapshot[provider] = f"user:{user[0]}"
                continue
            system = self.store.get_active_values(
                scope="system", owner_id="system", provider=provider
            )
            if system:
                snapshot[provider] = f"system:{system[0]}"
        return snapshot

    def resolve(
        self,
        provider: str,
        *,
        owner_user_id: str | None = None,
        snapshot: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if provider not in PROVIDER_FIELDS:
            raise ValueError("invalid provider")
        if provider == "tts" and Config.TTS_LOCAL_ONLY:
            return {
                **ENVIRONMENT_DEFAULTS["tts"],
                "_source": "environment",
                "_revision_id": None,
                "_local_only": True,
            }
        if provider == "tts":
            # Deployment switch owns both modes; saved local/cloud profiles and
            # old task snapshots must not silently select the other provider.
            return {
                "provider_name": "qwen-audio-remote",
                "_protocol": "qwen-audio-tts",
                "_source": "environment",
                "_revision_id": None,
                "_local_only": False,
                "base_url": os.getenv("TTS_REMOTE_API_BASE", "https://dashscope.aliyuncs.com/api/v1"),
                "api_key": os.getenv("TTS_REMOTE_API_KEY", ""),
                "model": os.getenv("TTS_REMOTE_MODEL", "qwen-audio-3.1-tts-flash"),
                "voice": os.getenv("TTS_REMOTE_VOICE", "longanhuan_v3.1"),
                "speed": os.getenv("TTS_REMOTE_SPEED", "1.0"),
                "timeout_seconds": os.getenv("TTS_REMOTE_TIMEOUT_SECONDS", "120"),
                "response_format": os.getenv("TTS_REMOTE_RESPONSE_FORMAT", "mp3"),
                "language": os.getenv("TTS_REMOTE_LANGUAGE", "zh"),
                "instructions": os.getenv("TTS_REMOTE_INSTRUCTIONS", ""),
                "volume": os.getenv("TTS_REMOTE_VOLUME", "50"),
                "pitch": os.getenv("TTS_REMOTE_PITCH", "1.0"),
                "sample_rate": os.getenv("TTS_REMOTE_SAMPLE_RATE", "24000"),
            }
        owner = owner_user_id or _runtime_owner.get()
        selected_snapshot = snapshot if snapshot is not None else _runtime_snapshot.get()
        if selected_snapshot and provider in selected_snapshot:
            scope, revision_id = selected_snapshot[provider].split(":", 1)
            owner_id = owner if scope == "user" else "system"
            selected = self.store.get_active_values(
                scope=scope,
                owner_id=owner_id or "",
                provider=provider,
                revision_id=revision_id,
            )
            if selected:
                return {
                    **selected[1],
                    "_source": scope,
                    "_revision_id": selected[0],
                }
        if owner:
            user = self.store.get_active_values(
                scope="user", owner_id=owner, provider=provider
            )
            if user:
                return {**user[1], "_source": "user", "_revision_id": user[0]}
        system = self.store.get_active_values(
            scope="system", owner_id="system", provider=provider
        )
        if system:
            return {**system[1], "_source": "system", "_revision_id": system[0]}
        return {**ENVIRONMENT_DEFAULTS[provider], "_source": "environment", "_revision_id": None}


def set_runtime_config_context(
    *, owner_user_id: str, snapshot: dict[str, str] | None
) -> tuple[Token, Token]:
    return (
        _runtime_owner.set(owner_user_id),
        _runtime_snapshot.set(dict(snapshot or {})),
    )


def reset_runtime_config_context(tokens: tuple[Token, Token]) -> None:
    _runtime_owner.reset(tokens[0])
    _runtime_snapshot.reset(tokens[1])


runtime_config_resolver = RuntimeConfigResolver()
