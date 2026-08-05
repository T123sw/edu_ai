"""`classroom_media.migrate_classroom_speech_audio` 单测（D1，SPEC-04 §5）。"""

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

pytestmark = pytest.mark.anyio

from core.course_storage import CourseStorageManager
from app.services.classroom_media import (
    migrate_classroom_speech_audio,
    synthesize_classroom_speech_audio,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_manager(tmp_path: Path) -> CourseStorageManager:
    return CourseStorageManager(root_path=str(tmp_path / f"course_data-{uuid.uuid4().hex}"))


class FakeDownloadClient:
    def __init__(self, base_url="http://localhost:3000"):
        self.config = SimpleNamespace(base_url=base_url)
        self.download_calls: list[str] = []

    async def download_media(self, url: str):
        self.download_calls.append(url)
        return b"fake-audio-bytes", "audio/mpeg"


def _scenes_with_audio(audio_url: str | None):
    return [
        {
            "id": "scene-1",
            "actions": [
                {"id": "act-1", "type": "speech", "text": "hi", "audioId": "tts_s1_act-1", "audioUrl": audio_url},
                {"id": "act-2", "type": "spotlight", "elementId": "el-1"},
            ],
        }
    ]


async def test_migrates_sidecar_audio_url_to_edu_ai_route(tmp_path):
    manager = _make_manager(tmp_path)
    client = FakeDownloadClient()
    scenes = _scenes_with_audio("http://localhost:3000/api/classroom-media/stage-1/audio/tts_s1_act-1.mp3")

    migrated = await migrate_classroom_speech_audio(
        scenes=scenes,
        course_id="course-1",
        classroom_id="stage-1",
        active_client=client,
        course_storage_manager=manager,
    )

    assert migrated == 1
    new_url = scenes[0]["actions"][0]["audioUrl"]
    assert new_url == "/api/courses/course-1/classrooms/stage-1/audio/tts_s1_act-1.mp3"
    assert client.download_calls == ["http://localhost:3000/api/classroom-media/stage-1/audio/tts_s1_act-1.mp3"]

    audio_dir = manager.get_classroom_audio_dir("course-1", "stage-1")
    saved_files = list(audio_dir.glob("*"))
    assert len(saved_files) == 1
    assert saved_files[0].read_bytes() == b"fake-audio-bytes"


async def test_no_audio_url_is_a_noop(tmp_path):
    manager = _make_manager(tmp_path)
    client = FakeDownloadClient()
    scenes = _scenes_with_audio(None)

    migrated = await migrate_classroom_speech_audio(
        scenes=scenes,
        course_id="course-1",
        classroom_id="stage-1",
        active_client=client,
        course_storage_manager=manager,
    )

    assert migrated == 0
    assert client.download_calls == []
    assert scenes[0]["actions"][0]["audioUrl"] is None


async def test_already_edu_ai_url_is_left_untouched(tmp_path):
    manager = _make_manager(tmp_path)
    client = FakeDownloadClient()
    scenes = _scenes_with_audio("/api/courses/course-1/classrooms/stage-1/audio/already-migrated.mp3")

    migrated = await migrate_classroom_speech_audio(
        scenes=scenes,
        course_id="course-1",
        classroom_id="stage-1",
        active_client=client,
        course_storage_manager=manager,
    )

    assert migrated == 0
    assert client.download_calls == []
    assert scenes[0]["actions"][0]["audioUrl"] == "/api/courses/course-1/classrooms/stage-1/audio/already-migrated.mp3"


async def test_runtime_tts_generates_missing_audio_without_exposing_key(tmp_path):
    import httpx

    captured = {}

    def handler(request: httpx.Request):
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200, content=b"mp3-bytes", headers={"content-type": "audio/mpeg"}
        )

    manager = _make_manager(tmp_path)
    scenes = [{"actions": [{"id": "speech 1", "type": "speech", "text": "你好"}]}]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        count = await synthesize_classroom_speech_audio(
            scenes=scenes,
            course_id="course-1",
            classroom_id="classroom-1",
            course_storage_manager=manager,
            tts_config={
                "_source": "user",
                "base_url": "https://tts.example/v1",
                "api_key": "tts-secret",
                "model": "speech-model",
                "voice": "warm",
            },
            http_client=client,
        )

    assert count == 1
    assert captured["authorization"] == "Bearer tts-secret"
    assert scenes[0]["actions"][0]["audioUrl"].startswith(
        "/api/courses/course-1/classrooms/classroom-1/audio/"
    )
    audio_dir = manager.get_classroom_audio_dir("course-1", "classroom-1")
    assert list(audio_dir.glob("*.mp3"))[0].read_bytes() == b"mp3-bytes"
