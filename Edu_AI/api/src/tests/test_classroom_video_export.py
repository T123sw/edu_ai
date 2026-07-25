import json
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.classroom_video_export import (
    build_video_export_command,
    parse_video_export_event,
    run_classroom_video_export_job,
)
from app.services.job_store import JobKind, JobStatus, create_job, get_job
from core import Config
from core.course_storage import CourseStorageManager


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_render_video_is_a_first_class_edu_job_kind():
    assert JobKind.RENDER_VIDEO.value == "render_video"


def test_build_video_export_command_keeps_auth_out_of_process_arguments(tmp_path):
    command = build_video_export_command(
        course_id="course / 中文",
        classroom_id="classroom?42",
        output_dir=tmp_path / "video",
        frontend_root=tmp_path / "frontend",
        base_url="http://127.0.0.1:4173",
        node_executable="node-test",
        ffmpeg_path="D:/tools/ffmpeg.exe",
    )

    assert command[:5] == [
        "node-test",
        "--import",
        "tsx",
        str(tmp_path / "frontend" / "scripts" / "export-classroom-video.ts"),
        "--base-url",
    ]
    assert "--course-id" in command
    assert command[command.index("--course-id") + 1] == "course / 中文"
    assert "--classroom-id" in command
    assert command[command.index("--classroom-id") + 1] == "classroom?42"
    assert "--auth-json" not in command
    assert not any("secret-token" in value for value in command)


def test_parse_video_export_event_accepts_progress_and_rejects_noise():
    assert parse_video_export_event(
        json.dumps(
            {
                "type": "progress",
                "step": "encoding",
                "progress": 55,
                "message": "转码",
            }
        )
    ) == {
        "type": "progress",
        "step": "encoding",
        "progress": 55,
        "message": "转码",
    }
    assert parse_video_export_event("vite warning") is None
    assert parse_video_export_event('{"type":"unknown"}') is None


def test_course_storage_allocates_isolated_classroom_video_directory(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    expected = (
        tmp_path
        / "courses"
        / "course-1"
        / "generated_materials"
        / "classrooms"
        / "classroom-1_media"
        / "video"
    )
    assert manager.get_classroom_video_dir("course-1", "classroom-1") == expected


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("classroom.mp4", "video/mp4"),
        ("classroom.srt", "application/x-subrip"),
        ("timeline.json", "application/json"),
    ],
)
def test_video_artifact_contract_uses_stable_names(filename, content_type):
    from app.services.classroom_video_export import VIDEO_ARTIFACT_MEDIA_TYPES

    assert VIDEO_ARTIFACT_MEDIA_TYPES[filename] == content_type


class _FakeStream:
    def __init__(self, lines=(), tail=b""):
        self._lines = list(lines)
        self._tail = tail

    async def readline(self):
        return self._lines.pop(0) if self._lines else b""

    async def read(self):
        return self._tail


class _FakeProcess:
    def __init__(self):
        self.stdout = _FakeStream(
            [
                b'{"type":"progress","step":"recording","progress":30,"message":"recording"}\n',
                b'{"type":"result","durationMs":5000,"sceneCount":2}\n',
            ]
        )
        self.stderr = _FakeStream()
        self.returncode = 0

    async def wait(self):
        return self.returncode


@pytest.mark.anyio
async def test_video_job_maps_process_progress_and_persists_artifact_urls(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "jobs")
    manager = CourseStorageManager(root_path=str(tmp_path / "courses"))
    output_dir = manager.get_classroom_video_dir("course-1", "classroom-1")
    captured = {}

    async def fake_subprocess(*command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        command_output = Path(command[command.index("--output-dir") + 1])
        captured["output_dir"] = command_output
        command_output.mkdir(parents=True, exist_ok=True)
        for name in ("classroom.mp4", "classroom.srt", "timeline.json"):
            (command_output / name).write_bytes(b"artifact")
        return _FakeProcess()

    monkeypatch.setattr(
        "app.services.classroom_video_export.asyncio.create_subprocess_exec",
        fake_subprocess,
    )
    job = create_job(kind=JobKind.RENDER_VIDEO, owner="teacher")
    result = await run_classroom_video_export_job(
        job,
        course_id="course-1",
        classroom_id="classroom-1",
        auth_token="secret-token",
        current_user={"username": "teacher"},
        course_storage_manager=manager,
        frontend_root=tmp_path / "frontend",
        base_url="http://frontend",
        node_executable="node-test",
        ffmpeg_path="ffmpeg-test",
    )

    assert result.status == JobStatus.SUCCEEDED
    assert result.result_ref["duration_ms"] == 5000
    assert result.result_ref["scene_count"] == 2
    assert result.result_ref["video_url"].endswith("/video/classroom.mp4")
    assert captured["output_dir"].name == f".job-{job.edu_job_id}"
    assert all((output_dir / name).is_file() for name in ("classroom.mp4", "classroom.srt", "timeline.json"))
    assert not captured["output_dir"].exists()
    assert "secret-token" not in " ".join(captured["command"])
    assert "secret-token" in captured["env"]["EDU_AI_EXPORT_AUTH_JSON"]
    assert get_job(job.edu_job_id).status == JobStatus.SUCCEEDED
