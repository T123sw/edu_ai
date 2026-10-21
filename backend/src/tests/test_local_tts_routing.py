from __future__ import annotations

import json

import httpx
import pytest

from core.config import Config
from app.services.runtime_config_resolver import ENVIRONMENT_DEFAULTS, RuntimeConfigResolver
from app.services.openmaic_tts_service import OpenMaicTtsService


@pytest.fixture
def local_profile(monkeypatch):
    monkeypatch.setattr(Config, "TTS_LOCAL_ONLY", True)
    profile = {
        "provider_name": "local-qwen-tts",
        "base_url": "http://127.0.0.1:8188/v1",
        "api_key": "",
        "model": "qwen3-tts",
        "voice": "vivian",
        "timeout_seconds": 120,
    }
    monkeypatch.setitem(ENVIRONMENT_DEFAULTS, "tts", profile)
    return profile


class CloudStore:
    def get_active_values(self, **kwargs):
        if kwargs["provider"] != "tts":
            return None
        return "old-cloud", {
            "base_url": "https://cloud.example/v1",
            "api_key": "cloud-secret",
            "model": "cloud-tts",
            "voice": "alloy",
        }


def test_local_deployment_overrides_user_system_and_old_snapshot(local_profile):
    resolver = RuntimeConfigResolver(CloudStore())
    for snapshot in (None, {"tts": "user:old-cloud"}, {"tts": "system:old-cloud"}):
        resolved = resolver.resolve("tts", owner_user_id="student", snapshot=snapshot)
        assert resolved["base_url"] == local_profile["base_url"]
        assert resolved["api_key"] == ""
        assert resolved["timeout_seconds"] == 120
    assert "tts" not in resolver.capture_snapshot("student")


def test_remote_mode_overrides_saved_profiles_and_snapshots(local_profile, monkeypatch):
    monkeypatch.setattr(Config, "TTS_LOCAL_ONLY", False)
    resolver = RuntimeConfigResolver(CloudStore())
    for snapshot in (None, {"tts": "user:old-cloud"}):
        resolved = resolver.resolve("tts", owner_user_id="student", snapshot=snapshot)
        assert resolved["model"] == "qwen-audio-3.1-tts-flash"
        assert resolved["_protocol"] == "qwen-audio-tts"
    assert "tts" not in resolver.capture_snapshot("student")


@pytest.mark.anyio
@pytest.mark.parametrize("voice", [None, "serena", "alloy", "Cherry"])
async def test_classroom_http_uses_local_model_and_voice(local_profile, voice):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, content=b"ID3-test-audio", headers={"Content-Type": "audio/mpeg"})

    service = OpenMaicTtsService(
        config_resolver=RuntimeConfigResolver(CloudStore()),
        voice=voice,
        transport=httpx.MockTransport(respond),
    )
    audio, fmt = await service.synthesize(text="本地课堂讲解", audio_id="speech-1")
    assert audio and fmt == "mp3"
    assert len(calls) == 1
    assert str(calls[0].url) == "http://127.0.0.1:8188/v1/audio/speech"
    assert "authorization" not in calls[0].headers
    payload = json.loads(calls[0].content)
    assert payload["model"] == "qwen3-tts"
    assert payload["voice"] == ("serena" if voice == "serena" else "vivian")
    assert calls[0].extensions["timeout"]["read"] == 120


@pytest.mark.anyio
async def test_local_failure_does_not_call_cloud(local_profile):
    calls = []

    def fail(request):
        calls.append(str(request.url))
        return httpx.Response(500, json={"error": {"code": "inference_failed"}})

    service = OpenMaicTtsService(
        config_resolver=RuntimeConfigResolver(CloudStore()),
        transport=httpx.MockTransport(fail),
    )
    with pytest.raises(RuntimeError, match="inference_failed"):
        await service.synthesize(text="本地课堂讲解", audio_id="speech-1")
    assert calls == ["http://127.0.0.1:8188/v1/audio/speech"]


@pytest.mark.anyio
async def test_local_mode_rejects_cloud_endpoint_before_request(local_profile):
    local_profile["base_url"] = "https://cloud.example/v1"
    service = OpenMaicTtsService(config_resolver=RuntimeConfigResolver(CloudStore()))
    with pytest.raises(ValueError, match="loopback"):
        await service.synthesize(text="不能发送至云端", audio_id="speech-1")
