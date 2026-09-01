"""Shared server-owned OpenMAIC speech profile for classroom audio."""

from __future__ import annotations

import re

from app.integrations.openmaic import OpenMaicClient, get_openmaic_client
from core.config import Config


class OpenMaicTtsService:
    def __init__(
        self,
        *,
        client: OpenMaicClient | None = None,
        provider_id: str = Config.OPENMAIC_LIVE_TTS_PROVIDER,
        voice: str = Config.OPENMAIC_LIVE_TTS_VOICE,
        speed: float = Config.OPENMAIC_LIVE_TTS_SPEED,
    ) -> None:
        self.client = client
        self.provider_id = str(provider_id).strip()
        self.voice = str(voice).strip()
        self.speed = min(2.0, max(0.5, float(speed)))
        if not self.provider_id or not self.voice:
            raise ValueError("The classroom TTS profile is incomplete")

    async def synthesize(self, *, text: str, audio_id: str) -> tuple[bytes, str]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", audio_id):
            raise ValueError("audio_id is not safe for TTS")
        speech_text = str(text or "").strip()[:1500]
        if not speech_text:
            raise ValueError("TTS text must not be empty")
        client = self.client or get_openmaic_client()
        return await client.synthesize_tts(
            text=speech_text,
            audio_id=audio_id,
            provider_id=self.provider_id,
            voice=self.voice,
            speed=self.speed,
        )
