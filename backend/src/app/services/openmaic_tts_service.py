"""Provider-neutral OpenAI-compatible TTS client owned by Edu_AI."""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from typing import Any

import httpx

from app.integrations.openmaic import OpenMaicClient
from app.services.runtime_config_resolver import runtime_config_resolver
from core.config import Config


_MAX_AUDIO_BYTES = 10 * 1024 * 1024
_SUPPORTED_FORMATS = frozenset({"mp3", "wav", "ogg", "m4a"})


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _bounded_float(value: Any, *, default: float, lower: float, upper: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return min(upper, max(lower, parsed))


def _speech_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/audio/speech"):
        # The legacy LOCAL_TTS_BASE_URL value was the complete endpoint.
        return normalized
    return f"{normalized}/audio/speech"


class OpenMaicTtsService:
    """Synthesize through the effective runtime ``tts`` configuration.

    Configuration is resolved for every call so request middleware and durable
    task snapshots retain the documented precedence. ``client`` plus an
    explicit ``provider_id`` remains only as an injected legacy test seam;
    production calls use the Edu_AI-owned HTTP boundary.
    """

    def __init__(
        self,
        *,
        client: OpenMaicClient | None = None,
        provider_id: str | None = None,
        voice: str | None = None,
        speed: float | None = None,
        response_format: str | None = None,
        config_resolver: Any = runtime_config_resolver,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.client = client
        self._legacy_provider_id = _clean(provider_id)
        self._legacy_sidecar = client is not None and bool(self._legacy_provider_id)
        # Classroom generation supplies voice without a provider id. The QA
        # wrapper still supplies its historical profile, which must not override
        # an active per-user/runtime configuration.
        self._voice_override = _clean(voice) if provider_id is None else ""
        self._speed_override = speed if provider_id is None else None
        self._format_override = _clean(response_format).lower()
        self._resolver = config_resolver
        self._transport = transport

        if self._legacy_sidecar:
            self.provider_id = self._legacy_provider_id
            self.voice = _clean(voice)
            self.speed = _bounded_float(speed, default=1.0, lower=0.5, upper=2.0)
            if not self.voice:
                raise ValueError("The classroom TTS profile is incomplete")
        else:
            # Retained for metrics/logging compatibility. Effective values are
            # refreshed by _resolve_http_config for each call.
            self.provider_id = self._legacy_provider_id or "runtime-tts"
            self.voice = self._voice_override
            self.speed = _bounded_float(speed, default=1.0, lower=0.5, upper=2.0)

    async def synthesize(
        self,
        *,
        text: str,
        audio_id: str,
        speed: float | None = None,
    ) -> tuple[bytes, str]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", audio_id):
            raise ValueError("audio_id is not safe for TTS")

        if self._legacy_sidecar:
            speech_text = _clean(text)[:1500]
            if not speech_text:
                raise ValueError("TTS text must not be empty")
            assert self.client is not None
            return await self.client.synthesize_tts(
                text=speech_text,
                audio_id=audio_id,
                provider_id=self.provider_id,
                voice=self.voice,
                speed=(
                    _bounded_float(speed, default=self.speed, lower=0.5, upper=2.0)
                    if speed is not None
                    else self.speed
                ),
            )

        config = self._resolve_http_config(speed=speed)
        speech_text = _clean(text)
        if not speech_text:
            raise ValueError("TTS text must not be empty")
        max_chars = int(config["max_input_chars"])
        if len(speech_text) > max_chars:
            speech_text = speech_text[:max_chars]
        return await self._synthesize_http(speech_text, config)

    def _resolve_http_config(self, *, speed: float | None) -> dict[str, Any]:
        resolved = dict(self._resolver.resolve("tts") or {})
        is_environment = resolved.get("_source") == "environment"

        def configured(field: str, *environment_names: str, default: Any = "") -> Any:
            value = resolved.get(field)
            if value not in (None, "") or not is_environment:
                return value
            for name in environment_names:
                candidate = os.getenv(name)
                if candidate not in (None, ""):
                    return candidate
            return default

        base_url = _clean(
            configured(
                "base_url",
                "TTS_API_BASE",
                "LOCAL_TTS_BASE_URL",
                "EDGE_TTS_BASE_URL",
                default="http://127.0.0.1:8188/v1",
            )
        )
        model = _clean(
            configured("model", "TTS_MODEL", "LOCAL_TTS_MODEL", default="qwen3-tts")
        )
        voice = self._voice_override or _clean(
            configured(
                "voice",
                "TTS_VOICE",
                "LOCAL_TTS_DEFAULT_VOICE",
                "EDGE_TTS_DEFAULT_VOICE",
                default=Config.OPENMAIC_LIVE_TTS_VOICE or "vivian",
            )
        )
        if not base_url or not model or not voice:
            raise ValueError("The runtime TTS configuration is incomplete")

        configured_speed = (
            resolved.get("speed")
            or os.getenv("TTS_SPEED")
            or os.getenv("OPENMAIC_LIVE_TTS_SPEED")
            or 1.0
        )
        requested_speed = (
            speed
            if speed is not None
            else self._speed_override
            if self._speed_override is not None
            else configured_speed
        )
        response_format = (
            self._format_override
            or _clean(resolved.get("response_format"))
            or _clean(os.getenv("TTS_RESPONSE_FORMAT", "mp3"))
        )
        response_format = response_format.lower()
        if response_format not in _SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported TTS response format: {response_format}")

        self.provider_id = _clean(resolved.get("provider_name")) or "environment"
        self.voice = voice
        self.speed = _bounded_float(requested_speed, default=1.0, lower=0.5, upper=2.0)
        return {
            "url": _speech_url(base_url),
            "api_key": _clean(
                configured("api_key", "TTS_API_KEY", "LOCAL_TTS_API_KEY")
            ),
            "model": model,
            "voice": voice,
            "speed": self.speed,
            "response_format": response_format,
            "timeout": _bounded_float(
                configured(
                    "timeout_seconds",
                    "TTS_TIMEOUT_SECONDS",
                    "LOCAL_TTS_TIMEOUT_SECONDS",
                    default=120,
                ),
                default=120,
                lower=1,
                upper=120,
            ),
            "max_input_chars": int(
                _bounded_float(
                    os.getenv("TTS_MAX_INPUT_CHARS", "1500"),
                    default=1500,
                    lower=1,
                    upper=1500,
                )
            ),
            "language": _clean(os.getenv("TTS_LANGUAGE", "zh-CN")),
            "instructions": _clean(
                os.getenv("TTS_INSTRUCTIONS", "自然、清晰的教师讲解语气")
            ),
        }

    async def _synthesize_http(
        self, text: str, config: dict[str, Any]
    ) -> tuple[bytes, str]:
        req_id = f"req_{uuid.uuid4().hex[:12]}"
        payload = {
            "model": config["model"],
            "input": text,
            "voice": config["voice"],
            "response_format": config["response_format"],
            "speed": config["speed"],
            "language": config["language"],
            "instructions": config["instructions"],
        }
        headers = {"Content-Type": "application/json", "X-Request-ID": req_id}
        if config["api_key"]:
            headers["Authorization"] = f"Bearer {config['api_key']}"

        response: httpx.Response | None = None
        try:
            async with httpx.AsyncClient(
                timeout=config["timeout"], transport=self._transport
            ) as http:
                for attempt in (1, 2):
                    try:
                        response = await http.post(
                            config["url"], json=payload, headers=headers
                        )
                    except httpx.HTTPError as exc:
                        if attempt == 1:
                            await asyncio.sleep(1.0)
                            continue
                        raise RuntimeError(
                            f"local TTS unreachable: {type(exc).__name__}"
                        ) from exc
                    if response.status_code in (429, 503, 504) and attempt == 1:
                        retry_after = response.headers.get("retry-after", "1")
                        try:
                            delay = min(5.0, max(0.0, float(retry_after)))
                        except ValueError:
                            delay = 1.0
                        await asyncio.sleep(delay)
                        continue
                    break
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"local TTS transport error: {type(exc).__name__}"
            ) from exc

        if response is None:
            raise RuntimeError("local TTS: no response")
        if response.status_code != 200:
            error_code = "invalid_response"
            try:
                error_code = (
                    _clean(response.json().get("error", {}).get("code"))
                    or error_code
                )
            except (ValueError, AttributeError):
                pass
            raise RuntimeError(
                f"local TTS failed: HTTP {response.status_code} code={error_code}"
            )

        mime = response.headers.get("content-type", "").lower()
        if not mime.startswith("audio/"):
            raise RuntimeError(f"local TTS bad mime: {mime!r}")

        # P6: 根据响应 Content-Type 映射实际格式，与请求格式比对
        mime_to_format = {
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/wave": "wav",
            "audio/ogg": "ogg",
            "audio/mp4": "m4a",
            "audio/x-m4a": "m4a",
        }
        actual_format = None
        for key, fmt in mime_to_format.items():
            if mime.startswith(key):
                actual_format = fmt
                break
        if actual_format is None:
            raise RuntimeError(f"local TTS unsupported mime: {mime!r}")

        requested_format = str(config["response_format"]).lower()
        if actual_format != requested_format:
            raise RuntimeError(
                f"local TTS format mismatch: requested {requested_format}, got {actual_format} (mime={mime!r})"
            )

        audio = response.content
        if not audio:
            raise RuntimeError("local TTS returned empty audio")
        if len(audio) > _MAX_AUDIO_BYTES:
            raise RuntimeError(
                f"local TTS audio exceeds {_MAX_AUDIO_BYTES // (1024 * 1024)}MiB"
            )
        return audio, actual_format
