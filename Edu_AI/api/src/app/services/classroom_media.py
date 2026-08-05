"""迁移 sidecar 生成的课件配音到 edu_ai 自己的存储（SPEC-04 §5 D1）。

背景：sidecar 开 `enableTTS` 后会把 `speech` action 的 `audioUrl` 回填成它
自己的临时地址（`{sidecar_base_url}/api/classroom-media/...`）。SPEC-02 §6
不变量 5 要求落库前 audioUrl 必须指向 edu_ai 可达存储，而不是这个 sidecar
地址——否则播放会依赖 sidecar 进程持续存活，且校验会直接拒绝落库（见
classroom_validation._looks_like_sidecar_local_url）。这个模块就是把音频
字节下载下来、落到 edu_ai 自己的课程存储里，再把 audioUrl 改写成 edu_ai
自己的 HTTP 地址（`/api/courses/{course_id}/classrooms/{classroom_id}/audio/
{filename}`，由 courses.py 的路由serve）。
"""

from __future__ import annotations

import mimetypes
import os
import re
from uuid import uuid4
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

from app.integrations.openmaic import OpenMaicClient
from app.services.runtime_config_resolver import runtime_config_resolver
from core.course_storage import CourseStorageManager
import httpx

_FALLBACK_EXTENSION = ".bin"


def _extension_for(audio_url: str, content_type: Optional[str]) -> str:
    suffix = Path(urlsplit(audio_url).path).suffix
    if suffix:
        return suffix
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return guessed
    return _FALLBACK_EXTENSION


async def migrate_classroom_speech_audio(
    *,
    scenes: list[dict[str, Any]],
    course_id: str,
    classroom_id: str,
    active_client: OpenMaicClient,
    course_storage_manager: CourseStorageManager,
) -> int:
    """就地改写 `scenes` 里 speech action 的 `audioUrl`：把指向 sidecar 的
    地址下载到本地、换成 edu_ai 自己的可达地址。没有 `audioUrl`（没开 TTS）
    或者已经不是 sidecar 地址的 action 原样跳过（幂等，重复调用安全）。

    返回实际迁移的音频文件数，供调用方记日志/断言用。
    """
    sidecar_base = active_client.config.base_url.rstrip("/")
    audio_dir: Optional[Path] = None
    migrated = 0

    for scene in scenes:
        for action in scene.get("actions") or []:
            if action.get("type") != "speech":
                continue
            audio_url = action.get("audioUrl")
            if not audio_url or not audio_url.startswith(sidecar_base):
                continue

            audio_bytes, content_type = await active_client.download_media(audio_url)

            if audio_dir is None:
                audio_dir = course_storage_manager.get_classroom_audio_dir(course_id, classroom_id)
                audio_dir.mkdir(parents=True, exist_ok=True)

            stem = str(action.get("audioId") or action.get("id") or f"audio-{migrated}")
            filename = f"{stem}{_extension_for(audio_url, content_type)}"
            (audio_dir / filename).write_bytes(audio_bytes)

            action["audioUrl"] = f"/api/courses/{course_id}/classrooms/{classroom_id}/audio/{filename}"
            migrated += 1

    return migrated


async def synthesize_classroom_speech_audio(
    *,
    scenes: list[dict[str, Any]],
    course_id: str,
    classroom_id: str,
    course_storage_manager: CourseStorageManager,
    tts_config: Optional[dict[str, Any]] = None,
    http_client: Optional[httpx.AsyncClient] = None,
) -> int:
    """Fill missing speech audio through an active OpenAI-compatible TTS config."""
    resolved = tts_config or runtime_config_resolver.resolve("tts")
    if resolved.get("_source") not in {"user", "system"}:
        return 0
    base_url = str(resolved.get("base_url") or "").rstrip("/")
    api_key = str(resolved.get("api_key") or "")
    model = str(resolved.get("model") or "")
    voice = str(resolved.get("voice") or "alloy")
    if not (base_url and api_key and model):
        return 0

    owned_client = http_client is None
    client = http_client or httpx.AsyncClient(trust_env=False)
    audio_dir: Optional[Path] = None
    generated = 0
    try:
        for scene in scenes:
            for action in scene.get("actions") or []:
                text = str(action.get("text") or "").strip()
                if action.get("type") != "speech" or action.get("audioUrl") or not text:
                    continue
                response = await client.post(
                    f"{base_url}/audio/speech",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "voice": voice,
                        "input": text,
                        "response_format": "mp3",
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                if audio_dir is None:
                    audio_dir = course_storage_manager.get_classroom_audio_dir(
                        course_id, classroom_id
                    )
                    audio_dir.mkdir(parents=True, exist_ok=True)
                safe_id = re.sub(
                    r"[^A-Za-z0-9._-]+",
                    "-",
                    str(action.get("audioId") or action.get("id") or uuid4().hex),
                ).strip("-")
                filename = f"{safe_id or uuid4().hex}.mp3"
                destination = audio_dir / filename
                temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
                try:
                    with temporary.open("wb") as stream:
                        stream.write(response.content)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
                action["audioId"] = safe_id
                action["audioUrl"] = (
                    f"/api/courses/{course_id}/classrooms/{classroom_id}/audio/{filename}"
                )
                generated += 1
    finally:
        if owned_client:
            await client.aclose()
    return generated
