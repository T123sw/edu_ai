"""Cached narration derived from an authorized, immutable classroom version."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path
from weakref import WeakValueDictionary

from app.services.tts_service import SpeechService
from app.self_learning.classroom_context import narration_sentences

_locks = WeakValueDictionary()
_lock_registry_guard = threading.Lock()


def narration_segments(text: str) -> list[str]:
    """Small transport chunks for responsive playback, never a content limit."""
    return [sentence[offset:offset + 100] for sentence in narration_sentences(text)
            for offset in range(0, len(sentence), 100)]


async def narration_audio(*, action: dict, audio_dir: Path, tts=None) -> Path:
    service = tts or SpeechService(response_format='mp3')
    config = service._resolve_http_config(speed=action.get('speed'))
    text = str(action.get('text') or '').strip()
    if not text:
        raise ValueError('Empty narration')
    # No credentials in filenames or logs. Voice/model changes invalidate cache.
    identity = {k: config[k] for k in ('url', 'model', 'voice', 'speed', 'language', 'instructions')}
    if config.get('protocol') == 'qwen-audio-tts':
        identity.update({k: config[k] for k in ('protocol', 'volume', 'pitch', 'sample_rate', 'response_format')})
    identity.update(text=text, max_input_chars=config['max_input_chars'])
    key = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    destination = audio_dir / f'narration-{key}.mp3'
    # Workers use separate asyncio.run loops. A loop-bound asyncio.Lock cannot
    # serialize them; poll a process-wide thread lock without blocking any loop.
    with _lock_registry_guard:
        lock = _locks.setdefault(str(destination), threading.Lock())
    while not lock.acquire(blocking=False):
        await asyncio.sleep(.025)
    try:
        if destination.is_file() and destination.stat().st_size:
            return destination
        audio_dir.mkdir(parents=True, exist_ok=True)
        # Split transport-sized input without dropping any of the lecture text.
        size = config['max_input_chars']
        with tempfile.TemporaryDirectory(prefix='.narration-', dir=audio_dir) as folder:
            root = Path(folder)
            clips = []
            for index, offset in enumerate(range(0, len(text), size)):
                audio, fmt = await service.synthesize(
                    text=text[offset:offset + size], audio_id=f'{key}-{index}', speed=config['speed'])
                if fmt not in {'mp3', 'wav', 'ogg', 'm4a'} or not audio:
                    raise ValueError('Invalid narration audio')
                clip = root / f'{index}.{fmt}'
                clip.write_bytes(audio)
                clips.append(clip)
            if len(clips) == 1 and clips[0].suffix == '.mp3':
                result = clips[0]
            else:
                listing = root / 'clips.txt'
                listing.write_text(''.join(f"file '{p.name}'\n" for p in clips))
                result = root / 'joined.mp3'
                proc = await asyncio.create_subprocess_exec(
                    'ffmpeg', '-v', 'error', '-f', 'concat', '-safe', '1', '-i', str(listing),
                    '-codec:a', 'libmp3lame', '-y', str(result),
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                try:
                    await asyncio.wait_for(proc.wait(), timeout=120)
                    if proc.returncode or not result.is_file():
                        raise ValueError('Narration encoding failed')
                finally:
                    if proc.returncode is None:
                        proc.kill()
                        await proc.wait()
            os.replace(result, destination)
        return destination
    finally:
        lock.release()
