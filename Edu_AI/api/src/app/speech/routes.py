from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.auth import get_current_user
from app.speech.transcribe import SpeechRecognitionError, build_default_transcriber
from core.config import Config


router = APIRouter(prefix="/api/speech", tags=["speech"])

_ALLOWED_AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".webm",
}


class SpeechTranscribeResponse(BaseModel):
    filename: str
    text: str


def _get_transcriber():
    return build_default_transcriber()


@router.post("/transcribe", response_model=SpeechTranscribeResponse, summary="Upload audio and transcribe it")
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    dev_pid: int = Query(1537, description="Baidu speech dev_pid"),
    current_user: dict = Depends(get_current_user),
):
    filename = file.filename or "audio.wav"
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的音频文件类型: {suffix or 'unknown'}",
        )

    username = current_user.get("username") or "anonymous"
    request_dir = Config.TEMP_DIR / "speech" / username / uuid.uuid4().hex
    request_dir.mkdir(parents=True, exist_ok=True)
    input_path = request_dir / f"upload{suffix}"

    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        text = _get_transcriber().transcribe(input_path, dev_pid=dev_pid)
        return SpeechTranscribeResponse(filename=filename, text=text)
    except SpeechRecognitionError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    finally:
        await file.close()
        shutil.rmtree(request_dir, ignore_errors=True)
