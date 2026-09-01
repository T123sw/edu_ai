"""Asynchronous OpenMAIC classroom video export orchestration."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

from app.services.job_store import (
    EduJob,
    JobKind,
    JobStatus,
    create_job,
    get_job,
    update_job,
)
from core.course_storage import CourseStorageManager

VIDEO_ARTIFACT_MEDIA_TYPES = {
    "classroom.mp4": "video/mp4",
    "classroom.srt": "application/x-subrip",
    "timeline.json": "application/json",
}

_FRONTEND_ROOT = Path(__file__).resolve().parents[4] / "frontend"


def build_video_export_command(
    *,
    course_id: str,
    classroom_id: str,
    output_dir: Path,
    frontend_root: Path = _FRONTEND_ROOT,
    base_url: str,
    node_executable: str = "node",
    ffmpeg_path: Optional[str] = None,
) -> list[str]:
    command = [
        node_executable,
        "--import",
        "tsx",
        str(frontend_root / "scripts" / "export-classroom-video.ts"),
        "--base-url",
        base_url,
        "--output-dir",
        str(output_dir),
        "--course-id",
        course_id,
        "--classroom-id",
        classroom_id,
        "--overwrite",
    ]
    if ffmpeg_path:
        command.extend(["--ffmpeg", ffmpeg_path])
    return command


def parse_video_export_event(line: str) -> Optional[dict[str, Any]]:
    try:
        event = json.loads(line)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(event, dict) or event.get("type") not in {
        "progress",
        "result",
        "error",
    }:
        return None
    return event


def _default_ffmpeg_path() -> str:
    configured = os.getenv("CLASSROOM_VIDEO_FFMPEG", "").strip()
    if configured:
        return configured
    conda_ffmpeg = Path(sys.prefix) / "Library" / "bin" / "ffmpeg.exe"
    return str(conda_ffmpeg) if conda_ffmpeg.exists() else "ffmpeg"


async def run_classroom_video_export_job(
    job: EduJob,
    *,
    course_id: str,
    classroom_id: str,
    auth_token: str,
    current_user: dict[str, Any],
    course_storage_manager: CourseStorageManager,
    frontend_root: Path = _FRONTEND_ROOT,
    base_url: Optional[str] = None,
    node_executable: Optional[str] = None,
    ffmpeg_path: Optional[str] = None,
) -> EduJob:
    artifact_root = course_storage_manager.get_classroom_video_dir(
        course_id, classroom_id
    )
    output_dir = artifact_root / f".job-{job.edu_job_id}"
    active_base_url = (
        base_url
        or os.getenv("CLASSROOM_VIDEO_FRONTEND_URL", "").strip()
        or "http://127.0.0.1:5173"
    )
    command = build_video_export_command(
        course_id=course_id,
        classroom_id=classroom_id,
        output_dir=output_dir,
        frontend_root=frontend_root,
        base_url=active_base_url,
        node_executable=node_executable
        or os.getenv("CLASSROOM_VIDEO_NODE", "").strip()
        or "node",
        ffmpeg_path=ffmpeg_path or _default_ffmpeg_path(),
    )
    auth_payload = json.dumps(
        {"user": current_user, "token": auth_token},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    environment = dict(os.environ)
    environment["EDU_AI_EXPORT_AUTH_JSON"] = auth_payload
    update_job(
        job.edu_job_id,
        status=JobStatus.RUNNING,
        step="preparing",
        progress=1,
        message="准备课堂视频导出",
        error=None,
        error_code=None,
    )

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(frontend_root),
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if process.stdout is None or process.stderr is None:
            raise RuntimeError("video exporter did not expose output streams")

        stderr_task = asyncio.create_task(process.stderr.read())
        result_event: Optional[dict[str, Any]] = None
        while True:
            raw_line = await process.stdout.readline()
            if not raw_line:
                break
            event = parse_video_export_event(raw_line.decode("utf-8", errors="replace"))
            if not event:
                continue
            if event["type"] == "progress":
                update_job(
                    job.edu_job_id,
                    status=JobStatus.RUNNING,
                    step=str(event.get("step") or "rendering"),
                    progress=max(1, min(99, int(event.get("progress") or 1))),
                    message=str(event.get("message") or "正在导出课堂视频"),
                )
            elif event["type"] == "result":
                result_event = event

        return_code = await process.wait()
        stderr = (await stderr_task).decode("utf-8", errors="replace").strip()
        if return_code != 0:
            raise RuntimeError(stderr[-4000:] or f"video exporter exited with {return_code}")

        missing = [
            filename
            for filename in VIDEO_ARTIFACT_MEDIA_TYPES
            if not (output_dir / filename).is_file()
        ]
        if missing:
            raise RuntimeError(f"video exporter omitted artifacts: {', '.join(missing)}")

        current = get_job(job.edu_job_id)
        if current and current.status == JobStatus.CANCEL_REQUESTED:
            shutil.rmtree(output_dir, ignore_errors=True)
            return update_job(
                job.edu_job_id,
                status=JobStatus.CANCELED,
                step="canceled",
                progress=100,
                message="任务已取消",
                result_ref=None,
            ) or job

        artifact_root.mkdir(parents=True, exist_ok=True)
        for filename in VIDEO_ARTIFACT_MEDIA_TYPES:
            os.replace(output_dir / filename, artifact_root / filename)
        shutil.rmtree(output_dir, ignore_errors=True)

        result_ref = {
            "course_id": course_id,
            "classroom_id": classroom_id,
            "video_url": f"/api/courses/{course_id}/classrooms/{classroom_id}/video/classroom.mp4",
            "subtitle_url": f"/api/courses/{course_id}/classrooms/{classroom_id}/video/classroom.srt",
            "timeline_url": f"/api/courses/{course_id}/classrooms/{classroom_id}/video/timeline.json",
            "duration_ms": int((result_event or {}).get("durationMs") or 0),
            "scene_count": int((result_event or {}).get("sceneCount") or 0),
        }
        return update_job(
            job.edu_job_id,
            status=JobStatus.SUCCEEDED,
            step="completed",
            progress=100,
            message="课堂视频导出完成",
            result_ref=result_ref,
        ) or job
    except Exception as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        return update_job(
            job.edu_job_id,
            status=JobStatus.FAILED,
            step="failed",
            progress=100,
            message="课堂视频导出失败",
            error=str(exc),
            error_code="VIDEO_EXPORT_FAILED",
        ) or job


async def submit_classroom_video_export_job(
    *,
    course_id: str,
    classroom_id: str,
    auth_token: str,
    current_user: dict[str, Any],
    owner: Optional[str],
    course_storage_manager: CourseStorageManager,
    existing_job: Optional[EduJob] = None,
) -> EduJob:
    job = existing_job or create_job(
            kind=JobKind.RENDER_VIDEO,
            owner_user_id=owner,
            course_id=course_id,
            input_summary={
                "title": f"课堂视频 · {classroom_id}",
                "resource_type": "classroom_video",
                "classroom_id": classroom_id,
                "source": "classroom-player",
            },
        )

    from app.services.platform_task_handlers import enqueue_platform_task

    return enqueue_platform_task(
        job=job,
        workflow_type="classroom_video_export",
        command={
            "course_id": course_id,
            "classroom_id": classroom_id,
            "owner_role": str(current_user.get("role") or "teacher"),
        },
    )
