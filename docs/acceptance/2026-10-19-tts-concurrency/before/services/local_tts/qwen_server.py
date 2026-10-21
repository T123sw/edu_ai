"""SPEC-16 compatible local Qwen3-TTS HTTP service."""

from __future__ import annotations

import asyncio
import collections
import hashlib
import io
import logging
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

# Set before importing the Hub/Transformers clients (they cache these flags).
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import librosa
import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from qwen_tts import Qwen3TTSModel


log = logging.getLogger("local_tts")
MODEL_DIR = os.environ.get("QWEN_TTS_MODEL", "/home/zxqs_ep/data/models/qwen3-tts")
DEVICE = os.environ.get("QWEN_TTS_DEVICE", "cuda:0")
MODEL_ID = os.environ.get("QWEN_TTS_MODEL_ID", "qwen3-tts")
VOICES = [
    {"id": "vivian", "name": "Vivian", "language": "zh-CN", "gender": "female"},
    {"id": "serena", "name": "Serena", "language": "zh-CN", "gender": "female"},
    {"id": "uncle_fu", "name": "Uncle Fu", "language": "zh-CN", "gender": "male"},
    {"id": "dylan", "name": "Dylan", "language": "zh-CN", "gender": "male"},
    {"id": "eric", "name": "Eric", "language": "zh-CN", "gender": "male"},
    {"id": "ryan", "name": "Ryan", "language": "en-US", "gender": "male"},
    {"id": "aiden", "name": "Aiden", "language": "en-US", "gender": "male"},
    {"id": "ono_anna", "name": "Ono Anna", "language": "ja-JP", "gender": "female"},
    {"id": "sohee", "name": "Sohee", "language": "ko-KR", "gender": "female"},
]
VOICE_IDS = {voice["id"] for voice in VOICES}
DEFAULT_VOICE = "vivian"
VOICE_LANG = {
    "vivian": "chinese",
    "serena": "chinese",
    "uncle_fu": "chinese",
    "dylan": "chinese",
    "eric": "chinese",
    "ryan": "english",
    "aiden": "english",
    "ono_anna": "japanese",
    "sohee": "korean",
}
LANGUAGE_ALIASES = {
    "zh": "chinese",
    "zh-cn": "chinese",
    "en": "english",
    "en-us": "english",
    "ja": "japanese",
    "ja-jp": "japanese",
    "ko": "korean",
    "ko-kr": "korean",
}
FORMATS = ["mp3", "wav"]

# Each speech request is synthesized as one complete utterance. Let the model
# interpret punctuation; splitting into independent fragments loses continuity.
BATCH_SIZE = 1  # Retained for the existing response-header/stats contract.
CACHE_SIZE = max(0, int(os.environ.get("QWEN_TTS_CACHE_SIZE", "256")))
_cache: "collections.OrderedDict[str, tuple[bytes, str, int]]" = collections.OrderedDict()
_cache_lock = threading.Lock()
_stats = {"requests": 0, "cache_hits": 0, "batch_calls": 0, "fallback_calls": 0,
          "sentences": 0, "audio_ms": 0, "infer_ms": 0}


def _cache_get(key: str):
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            _stats["cache_hits"] += 1
            return _cache[key]
    return None


def _cache_put(key: str, value):
    if not CACHE_SIZE:
        return
    with _cache_lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)

_model_ready = False
print(f"[TTS] Loading Qwen3-TTS from {MODEL_DIR} on {DEVICE}...", flush=True)
try:
    if not Path(MODEL_DIR).is_dir():
        raise FileNotFoundError("QWEN_TTS_MODEL must be an existing local directory")
    model = Qwen3TTSModel.from_pretrained(
        MODEL_DIR,
        device_map=DEVICE,
        dtype=torch.bfloat16,
        local_files_only=True,
    )
    _model_ready = True
    print("[TTS] Model loaded.", flush=True)
except Exception as _exc:  # noqa: BLE001 - keep the process alive for /health
    model = None
    print(f"[TTS] Model loading failed: {_exc}", flush=True)

# P8: 并发控制。用 asyncio.Queue 做有界信号量，满载立即拒绝。
MAX_CONCURRENT = max(1, int(os.environ.get("QWEN_TTS_MAX_CONCURRENCY", "1")))
_slots: asyncio.Queue = asyncio.Queue(maxsize=MAX_CONCURRENT)

app = FastAPI(title="local-tts", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SpeechRequest(BaseModel):
    model: str = Field(..., min_length=1)
    input: str = Field(..., min_length=1, max_length=1500)
    voice: str = DEFAULT_VOICE
    response_format: str = "mp3"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    language: Optional[str] = None
    instructions: Optional[str] = None


def _err(
    code: str,
    message: str,
    status: int,
    retryable: bool = False,
    req_id: str = "",
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "request_id": req_id,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    is_too_long = any(error.get("type") == "string_too_long" for error in exc.errors())
    return _err(
        "input_too_long" if is_too_long else "invalid_request",
        "TTS input is too long" if is_too_long else "Invalid TTS request",
        413 if is_too_long else 400,
        req_id=req_id,
    )


def _wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV")
    return buffer.getvalue()


def _generate_audio(req: SpeechRequest, voice: str) -> tuple[bytes, str, int]:
    requested_language = (req.language or "").strip().lower()
    language = LANGUAGE_ALIASES.get(requested_language, VOICE_LANG[voice])

    cache_key = hashlib.sha256(
        f"{voice}|{language}|{req.instructions or ''}|{req.speed}|"
        f"{req.response_format}|{req.input}".encode("utf-8")
    ).hexdigest()
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    text = req.input.strip()
    infer_t0 = time.time()
    wavs, sample_rate = model.generate_custom_voice(
        text=text,
        speaker=voice,
        language=language,
        **({"instruct": req.instructions} if req.instructions else {}),
    )
    _stats["infer_ms"] += int((time.time() - infer_t0) * 1000)
    _stats["sentences"] += 1
    if len(wavs) != 1:
        raise RuntimeError("expected one audio output for one speech request")
    audio = wavs[0]
    audio = np.asarray(audio, dtype=np.float32).squeeze()
    if audio.size == 0:
        raise RuntimeError("empty audio")
    if req.speed != 1.0:
        audio = librosa.effects.time_stretch(audio, rate=req.speed)
    duration_ms = round(len(audio) * 1000 / sample_rate)
    wav = _wav_bytes(audio, sample_rate)

    if req.response_format == "wav":
        _cache_put(cache_key, (wav, "audio/wav", duration_ms))
        return wav, "audio/wav", duration_ms
    process = subprocess.run(
        ["ffmpeg", "-y", "-i", "pipe:0", "-f", "mp3", "-b:a", "128k", "pipe:1"],
        input=wav,
        capture_output=True,
        check=True,
    )
    if not process.stdout:
        raise RuntimeError("empty encoded audio")
    _cache_put(cache_key, (process.stdout, "audio/mpeg", duration_ms))
    _stats["requests"] += 1
    _stats["audio_ms"] += duration_ms
    return process.stdout, "audio/mpeg", duration_ms


@app.get("/health")
async def health() -> Response:
    # P8: /health 不阻塞；模型加载中返回 503
    if not _model_ready or model is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "loading",
                "service": "local-tts",
                "model_loaded": False,
                "model": MODEL_ID,
                "device": DEVICE,
                "formats": FORMATS,
            },
        )
    return JSONResponse(
        {
            "status": "ok",
            "service": "local-tts",
            "model_loaded": True,
            "model": MODEL_ID,
            "device": DEVICE,
            "formats": FORMATS,
        }
    )


@app.get("/stats")
async def stats():
    with _cache_lock:
        cache_len = len(_cache)
    return {
        "batch_size": BATCH_SIZE,
        "cache_size": CACHE_SIZE,
        "cache_entries": cache_len,
        **_stats,
    }


@app.get("/v1/models")
async def list_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": MODEL_ID, "object": "model", "owned_by": "local"}],
    }


@app.get("/v1/audio/voices")
async def list_voices(model: Optional[str] = None) -> Response:
    if model and model != MODEL_ID:
        return _err("model_not_found", "TTS model was not found", 404)
    return JSONResponse({"object": "list", "data": VOICES})


@app.post("/v1/audio/speech")
async def speech(req: SpeechRequest, request: Request) -> Response:
    req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    if req.model != MODEL_ID:
        return _err("model_not_found", "TTS model was not found", 404, req_id=req_id)
    voice = req.voice.strip().lower()
    if voice not in VOICE_IDS:
        return _err("voice_not_found", "TTS voice was not found", 404, req_id=req_id)
    if not req.input.strip():
        return _err("invalid_request", "input is empty", 400, req_id=req_id)
    if req.response_format not in FORMATS:
        return _err(
            "unsupported_format",
            f"unsupported: {req.response_format}",
            422,
            req_id=req_id,
        )
    # P8: 模型未就绪 -> 503
    if not _model_ready or model is None:
        return _err(
            "model_loading", "TTS model is loading", 503, True, req_id
        )

    # P8: 有界队列，满载 -> 429 + Retry-After
    try:
        _slots.put_nowait(1)
    except asyncio.QueueFull:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "queue_full",
                    "message": "TTS inference queue is full",
                    "retryable": True,
                    "request_id": req_id,
                }
            },
            headers={"Retry-After": "5"},
        )

    try:
        # P8: 在线程池里跑推理，不阻塞事件循环
        output, mime, duration_ms = await asyncio.to_thread(_generate_audio, req, voice)
    except Exception:  # noqa: BLE001 - normalize provider failures at HTTP boundary
        log.exception(
            "qwen_tts_inference_failed request_id=%s model=%s voice=%s text_length=%d",
            req_id,
            req.model,
            voice,
            len(req.input),
        )
        return _err(
            "inference_failed",
            "TTS inference failed",
            500,
            True,
            req_id,
        )
    finally:
        try:
            _slots.get_nowait()
        except asyncio.QueueEmpty:
            pass
    return Response(
        content=output,
        media_type=mime,
        headers={
            "X-Request-ID": req_id,
            "X-Audio-Format": req.response_format,
            "X-Audio-Duration-Ms": str(duration_ms),
            "X-Audio-Batch": str(BATCH_SIZE),
        },
    )
