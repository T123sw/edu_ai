from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
RECORDINGS_DIR = BASE_DIR / "data" / "recordings"


@dataclass(frozen=True)
class RecordingPaths:
    video: Path
    audio: Path
    final: Path


def safe_session_id(sessionid) -> str:
    value = str(sessionid or "0").strip() or "0"
    for char in '<>:"\\\\|?*/':
        value = value.replace(char, "__")
    return value


def recording_paths_for_session(sessionid) -> RecordingPaths:
    safe_id = safe_session_id(sessionid)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return RecordingPaths(
        video=RECORDINGS_DIR / f"temp{safe_id}.mp4",
        audio=RECORDINGS_DIR / f"temp{safe_id}.aac",
        final=RECORDINGS_DIR / f"record_{safe_id}.mp4",
    )
