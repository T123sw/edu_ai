"""Qwen TTS synthesis and atomic classroom answer audio persistence."""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

from app.integrations.openmaic import OpenMaicClient, get_openmaic_client
from core.config import Config


_FORMAT_DETAILS = {
    "mp3": ("mp3", "audio/mpeg"),
    "wav": ("wav", "audio/wav"),
    "ogg": ("ogg", "audio/ogg"),
    "m4a": ("m4a", "audio/mp4"),
}


class ClassroomQaTtsService:
    def __init__(
        self,
        *,
        client: OpenMaicClient | None = None,
        provider_id: str = Config.OPENMAIC_LIVE_TTS_PROVIDER,
        voice: str = Config.OPENMAIC_LIVE_TTS_VOICE,
        speed: float = Config.OPENMAIC_LIVE_TTS_SPEED,
    ) -> None:
        self.client = client
        self.provider_id = provider_id
        self.voice = voice
        self.speed = min(2.0, max(0.5, float(speed)))

    async def synthesize_and_store(
        self,
        *,
        session_dir: Path,
        turn_id: str,
        text: str,
    ) -> tuple[str, str]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", turn_id):
            raise ValueError("turn_id is not safe for audio persistence")
        speech_text = str(text or "").strip()[:1500]
        if not speech_text:
            raise ValueError("TTS text must not be empty")

        client = self.client or get_openmaic_client()
        audio, format_name = await client.synthesize_tts(
            text=speech_text,
            audio_id=turn_id,
            provider_id=self.provider_id,
            voice=self.voice,
            speed=self.speed,
        )
        details = _FORMAT_DETAILS.get(format_name)
        if details is None:
            raise ValueError(f"Unsupported classroom Q&A audio format: {format_name}")
        extension, mime_type = details
        filename = f"{turn_id}.{extension}"
        audio_dir = session_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        destination = audio_dir / filename
        temporary = audio_dir / f".{filename}.{uuid4().hex}.tmp"
        try:
            with temporary.open("wb") as stream:
                stream.write(audio)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return filename, mime_type
