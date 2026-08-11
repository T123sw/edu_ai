from __future__ import annotations

import pytest

from app.services.openmaic_tts_service import OpenMaicTtsService


pytestmark = pytest.mark.anyio


class FakeOpenMaicClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def synthesize_tts(self, **kwargs):
        self.calls.append(kwargs)
        return b"ID3-shared-audio", "mp3"


async def test_shared_service_uses_the_server_owned_classroom_profile():
    client = FakeOpenMaicClient()
    service = OpenMaicTtsService(
        client=client,
        provider_id="qwen-tts",
        voice="Cherry",
        speed=1.0,
    )

    audio, format_name = await service.synthesize(
        text="  年轻女声课堂讲解。  ",
        audio_id="scene-1-speech-1",
    )

    assert audio == b"ID3-shared-audio"
    assert format_name == "mp3"
    assert client.calls == [
        {
            "text": "年轻女声课堂讲解。",
            "audio_id": "scene-1-speech-1",
            "provider_id": "qwen-tts",
            "voice": "Cherry",
            "speed": 1.0,
        }
    ]


@pytest.mark.parametrize(
    ("text", "audio_id"),
    [("", "speech-1"), ("讲解", "../unsafe"), ("讲解", "contains space")],
)
async def test_shared_service_rejects_empty_text_and_unsafe_audio_ids(text, audio_id):
    service = OpenMaicTtsService(client=FakeOpenMaicClient())

    with pytest.raises(ValueError):
        await service.synthesize(text=text, audio_id=audio_id)
