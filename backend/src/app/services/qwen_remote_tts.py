"""Qwen-Audio-TTS HTTP adapter (SpeechSynthesizer, not Qwen3-TTS).

Protocol: https://help.aliyun.com/zh/model-studio/qwen-audio-tts-http-api
"""
from __future__ import annotations

import asyncio
import math
import hashlib
import os
import random
import time
from email.utils import parsedate_to_datetime

from app.integrations.hyperframes.stage_limits import ADMISSION_GUARD, ProviderRate, StageSlots
from urllib.parse import urlsplit, urlunsplit

import httpx

_MAX_BYTES = 10 * 1024 * 1024
_ENDPOINT = '/services/audio/tts/SpeechSynthesizer'


def _number(value, default, lower, upper):
    number = float(default if value in (None, '') else value)
    if not math.isfinite(number) or not lower <= number <= upper:
        raise ValueError('远程配音参数超出支持范围，请检查 TTS_REMOTE 配置')
    return number


def remote_config(profile, *, speed=None, response_format=''):
    base = str(profile.get('base_url') or '').strip().rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('请将 TTS_REMOTE_API_BASE 设置为百炼 HTTPS 接口地址')
    key = str(profile.get('api_key') or '').strip()
    if not key:
        raise ValueError('远程配音尚未配置，请填写 TTS_REMOTE_API_KEY')
    model = str(profile.get('model') or '').strip()
    voice = str(profile.get('voice') or '').strip()
    if not model.startswith('qwen-audio-') or not voice:
        raise ValueError('请检查 TTS_REMOTE_MODEL 和 TTS_REMOTE_VOICE')
    fmt = response_format or profile.get('response_format') or 'mp3'
    if fmt not in {'mp3', 'wav'}:
        raise ValueError('远程配音目前支持 mp3 或 wav 格式')
    sample_rate = int(profile.get('sample_rate') or 24000)
    if sample_rate not in {8000, 12000, 16000, 22050, 24000, 44100, 48000}:
        raise ValueError('远程配音采样率不受支持')
    return dict(protocol='qwen-audio-tts', url=base if base.endswith(_ENDPOINT) else base + _ENDPOINT,
        api_key=key, model=model, voice=voice, response_format=fmt, sample_rate=sample_rate,
        speed=_number(speed if speed is not None else profile.get('speed'), 1, .5, 2),
        timeout=_number(profile.get('timeout_seconds'), 120, 1, 120),
        volume=int(_number(profile.get('volume'), 50, 0, 100)),
        pitch=_number(profile.get('pitch'), 1, .5, 2), max_input_chars=1500,
        language=str(profile.get('language') or '').strip(),
        instructions=str(profile.get('instructions') or '').strip())


def _retry_delay(value, attempt):
    try:
        delay = float(value)
    except (ValueError, TypeError):
        try:
            delay = parsedate_to_datetime(value).timestamp() - time.time()
        except (ValueError, TypeError, OverflowError):
            delay = 0
    # Never retry before Retry-After. Invalid headers use bounded backoff.
    if not math.isfinite(delay):
        delay = 0
    return max(0, delay, min(16, 2 ** attempt)) + random.uniform(0, .5)


async def _request(http, method, url, *, limit, admission=None, **kwargs):
    attempts = 4
    guard = ADMISSION_GUARD.get()
    for attempt in range(attempts):
        guard()
        slots, rate = admission if admission else (None, None)
        acquired = False
        retry_delay = None
        try:
            if slots:
                while True:
                    while not slots.acquire(blocking=False):
                        guard()
                        await asyncio.sleep(.1)
                    acquired = True
                    guard()
                    delay = rate.try_start()
                    if delay <= 0:
                        break
                    slots.release()
                    acquired = False
                    await asyncio.sleep(min(delay, .5))
            async with http.stream(method, url, **kwargs) as response:
                if response.status_code in {429, 500, 502, 503, 504}:
                    retry_delay = _retry_delay(response.headers.get('Retry-After'), attempt)
                    if rate and response.status_code == 429:
                        rate.cool_down(retry_delay)
                    if attempt == attempts - 1:
                        raise RuntimeError(f'远程配音请求失败（HTTP {response.status_code}）')
                elif response.status_code != 200:
                    raise RuntimeError(f'远程配音请求失败（HTTP {response.status_code}）')
                else:
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > limit:
                            raise RuntimeError('远程配音响应超过传输大小上限')
                    return bytes(body), response.headers.get('content-type', '').split(';')[0].strip()
        except httpx.HTTPError:
            if attempt == attempts - 1:
                raise RuntimeError('远程配音连接超时或中断，请稍后重试') from None
            retry_delay = _retry_delay(None, attempt)
        finally:
            if acquired:
                slots.release()
        # Close response and release concurrency before retry/backoff.
        remaining = retry_delay
        while remaining > 0:
            guard()
            duration = min(.5, remaining)
            await asyncio.sleep(duration)
            remaining -= duration
    raise RuntimeError('远程配音未返回音频')


def _audio_url(value):
    parsed = urlsplit(str(value or ''))
    # The provider returns signed OSS URLs. Do not fetch arbitrary URLs supplied
    # in a response, follow redirects or forward the provider's Bearer token.
    if (parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password
            or not (parsed.hostname or '').endswith('.aliyuncs.com')
            or parsed.port not in {None, 80, 443}):
        raise RuntimeError('远程配音返回的音频地址无效')
    return urlunsplit(('https', parsed.hostname, parsed.path, parsed.query, ''))


async def synthesize_remote(text, config, *, transport=None):
    import json
    fields = dict(text=text, voice=config['voice'], format=config['response_format'],
        sample_rate=config['sample_rate'], rate=config['speed'], volume=config['volume'], pitch=config['pitch'])
    if config['language']:
        fields['language_hints'] = [config['language']]
    if config['instructions']:
        fields['instruction'] = config['instructions']
    identity = hashlib.sha256((urlsplit(config['url']).netloc + ':' + (os.getenv('TTS_REMOTE_LIMIT_GROUP') or config['api_key'])).encode()).hexdigest()
    slots = StageSlots('tts:' + identity, int(os.getenv('TTS_REMOTE_CONCURRENCY', '8')))
    rate = ProviderRate('tts:' + identity, interval=1 / max(.1, float(os.getenv('TTS_REMOTE_REQUESTS_PER_SECOND', '4'))))
    async with httpx.AsyncClient(timeout=config['timeout'], transport=transport, follow_redirects=False) as http:
        body, _ = await _request(http, 'POST', config['url'], limit=1024 * 1024, admission=(slots, rate),
            json={'model': config['model'], 'input': fields},
            headers={'Authorization': 'Bearer ' + config['api_key'], 'Content-Type': 'application/json'})
        try:
            result = json.loads(body)
            audio_url = result['output']['audio']['url']
        except (ValueError, TypeError, KeyError):
            raise RuntimeError('远程配音未返回可下载的音频') from None
        audio, mime = await _request(http, 'GET', _audio_url(audio_url), limit=_MAX_BYTES)
    fmt = config['response_format']
    valid = (audio.startswith(b'RIFF') and audio[8:12] == b'WAVE') if fmt == 'wav' else (
        audio.startswith(b'ID3') or len(audio) >= 2 and audio[0] == 255 and audio[1] & 224 == 224)
    if not valid or mime in {'text/html', 'application/json'}:
        raise RuntimeError('远程配音返回的音频为空或格式不正确')
    return audio, fmt
