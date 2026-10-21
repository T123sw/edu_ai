"""SPEC-16 compatible local Qwen3-TTS HTTP service."""

from __future__ import annotations

import asyncio
import collections
from contextlib import asynccontextmanager
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
BATCH_SIZE = max(1, min(8, int(os.environ.get("QWEN_TTS_REQUEST_BATCH_SIZE", "4"))))
CACHE_SIZE = max(0, int(os.environ.get("QWEN_TTS_CACHE_SIZE", "256")))
_cache: "collections.OrderedDict[str, tuple[bytes, str, int]]" = collections.OrderedDict()
_cache_lock = threading.Lock()
_stats = {"requests": 0, "cache_hits": 0, "batch_calls": 0, "fallback_calls": 0,
          "sentences": 0, "audio_ms": 0, "infer_ms": 0, "model_calls": 0, "max_batch_observed": 0}


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
    from services.local_tts.batching import bound_waveform_decode
    bound_waveform_decode(model)
    _model_ready = True
    print("[TTS] Model loaded.", flush=True)
except Exception as _exc:  # noqa: BLE001 - keep the process alive for /health
    model = None
    print(f"[TTS] Model loading failed: {_exc}", flush=True)

from services.local_tts.batching import SpeechBatchQueue


@asynccontextmanager
async def lifespan(app):
    app.state.speech_batches = SpeechBatchQueue(
        _generate_batch, max_batch=BATCH_SIZE,
        max_pending=max(1, int(os.environ.get("QWEN_TTS_MAX_PENDING", "64"))),
        max_chars=max(1500, int(os.environ.get("QWEN_TTS_BATCH_MAX_CHARS", "1600"))),
    )
    try:
        yield
    finally:
        await app.state.speech_batches.close()


app = FastAPI(title="local-tts", version="1.0.0", lifespan=lifespan)
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


def _request_key(req, voice):
    language = LANGUAGE_ALIASES.get((req.language or "").strip().lower(), VOICE_LANG[voice])
    return hashlib.sha256(
        f"whole-v2|{voice}|{language}|{req.instructions or ''}|{req.speed}|"
        f"{req.response_format}|{req.input}".encode("utf-8")
    ).hexdigest()


def _encode_audio(req, audio, sample_rate):
    audio = np.asarray(audio, dtype=np.float32).squeeze()
    if audio.size == 0:
        raise RuntimeError("empty audio")
    if req.speed != 1.0:
        audio = librosa.effects.time_stretch(audio, rate=req.speed)
    duration_ms = round(len(audio) * 1000 / sample_rate)
    wav = _wav_bytes(audio, sample_rate)
    if req.response_format == "wav":
        return wav, "audio/wav", duration_ms
    process = subprocess.run(
        ["ffmpeg", "-y", "-i", "pipe:0", "-f", "mp3", "-b:a", "128k", "pipe:1"],
        input=wav, capture_output=True, check=True,
    )
    if not process.stdout:
        raise RuntimeError("empty encoded audio")
    return process.stdout, "audio/mpeg", duration_ms


def _generate_batch(items):
    """Batch complete utterances on GPU; never split an individual input."""
    results = [None] * len(items)
    missing = []
    for index, (req, voice) in enumerate(items):
        cached = _cache_get(_request_key(req, voice))
        if cached is not None:
            results[index] = (*cached, 0, "cache")
        else:
            missing.append((index, req, voice))
    if not missing:
        return results
    batch_id = uuid.uuid4().hex[:12]
    texts = [req.input.strip() for _, req, _ in missing]
    speakers = [voice for _, _, voice in missing]
    languages = [LANGUAGE_ALIASES.get((req.language or "").strip().lower(), VOICE_LANG[voice])
                 for _, req, voice in missing]
    instructions = [req.instructions or "" for _, req, _ in missing]
    size = len(missing)
    _stats["model_calls"] += 1
    _stats["batch_calls"] += int(size > 1)
    _stats["max_batch_observed"] = max(_stats["max_batch_observed"], size)
    started = time.monotonic()
    log.warning("tts_batch_started batch_id=%s size=%s chars=%s", batch_id, size, [len(t) for t in texts])
    failure = None
    try:
        wavs, sample_rate = model.generate_custom_voice(
            text=texts if size > 1 else texts[0],
            speaker=speakers if size > 1 else speakers[0],
            language=languages if size > 1 else languages[0],
            instruct=instructions if size > 1 else instructions[0],
        )
        if len(wavs) != size:
            raise RuntimeError("speech model output count mismatch")
    except Exception as exc:
        failure = exc
    _stats["infer_ms"] += int((time.monotonic() - started) * 1000)
    if failure is not None:
        log.warning("tts_batch_failed batch_id=%s size=%s error=%s", batch_id, size, type(failure).__name__)
        if size == 1:
            results[missing[0][0]] = failure
            return results
        # Retry smaller groups of complete requests, including on GPU OOM.
        # Release failed inference frames/tensors before retrying.
        failure.__traceback__ = None
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        _stats["fallback_calls"] += 1
        midpoint = size // 2
        for group in (missing[:midpoint], missing[midpoint:]):
            retried = _generate_batch([(req, voice) for _, req, voice in group])
            for (index, _, _), result in zip(group, retried):
                results[index] = result
        return results
    for (index, req, voice), audio in zip(missing, wavs):
        try:
            output = _encode_audio(req, audio, sample_rate)
            _cache_put(_request_key(req, voice), output)
            _stats["requests"] += 1
            _stats["sentences"] += 1
            _stats["audio_ms"] += output[2]
            results[index] = (*output, size, batch_id)
        except Exception as exc:
            results[index] = exc
    log.warning("tts_batch_finished batch_id=%s size=%s elapsed=%.2f", batch_id, size, time.monotonic()-started)
    return results


def _generate_audio(req, voice):
    result = _generate_batch([(req, voice)])[0]
    if isinstance(result, Exception):
        raise result
    return result[:3]


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
        "active_requests": app.state.speech_batches.active,
        "queued_requests": app.state.speech_batches.pending,
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

    pending = asyncio.create_task(app.state.speech_batches.submit((req, voice)))
    try:
        # All workers share this queue. One GPU invocation processes several
        # independent full requests together instead of rejecting busy peers.
        while not pending.done():
            await asyncio.wait([pending], timeout=.5)
            if await request.is_disconnected():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
                return Response(status_code=499)
        output, mime, duration_ms, batch_size, batch_id = await pending
    except asyncio.QueueFull:
        return JSONResponse(status_code=429, content={"error": {
            "code": "queue_full", "message": "TTS waiting queue is full",
            "retryable": True, "request_id": req_id}}, headers={"Retry-After": "5"})
    except Exception:
        log.exception("qwen_tts_inference_failed request_id=%s text_length=%d", req_id, len(req.input))
        return _err("inference_failed", "TTS inference failed", 500, True, req_id)
    finally:
        if not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
    return Response(
        content=output,
        media_type=mime,
        headers={
            "X-Request-ID": req_id,
            "X-Audio-Format": req.response_format,
            "X-Audio-Duration-Ms": str(duration_ms),
            "X-Audio-Batch": str(batch_size),
            "X-TTS-Batch-ID": batch_id,
            "X-Audio-Fragments": "1",
            "X-Audio-Input-Chars": str(len(req.input.strip())),
        },
    )
