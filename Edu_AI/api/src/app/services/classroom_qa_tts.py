"""Qwen TTS synthesis and atomic classroom answer audio persistence."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from app.integrations.openmaic import OpenMaicClient
from app.services.openmaic_tts_service import OpenMaicTtsService
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
        service: OpenMaicTtsService | None = None,
        client: OpenMaicClient | None = None,
        provider_id: str = Config.OPENMAIC_LIVE_TTS_PROVIDER,
        voice: str = Config.OPENMAIC_LIVE_TTS_VOICE,
        speed: float = Config.OPENMAIC_LIVE_TTS_SPEED,
    ) -> None:
        self.service = service or OpenMaicTtsService(
            client=client,
            provider_id=provider_id,
            voice=voice,
            speed=speed,
        )

    async def synthesize_and_store(
        self,
        *,
        session_dir: Path,
        turn_id: str,
        text: str,
    ) -> tuple[str, str]:
        audio, format_name = await self.service.synthesize(
            text=text,
            audio_id=turn_id,
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
