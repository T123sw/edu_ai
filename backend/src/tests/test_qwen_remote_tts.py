import json

import httpx
import pytest

from core.config import Config
from app.services.runtime_config_resolver import RuntimeConfigResolver
from app.services.openmaic_tts_service import OpenMaicTtsService
from app.services.qwen_remote_tts import _audio_url

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.fixture
def remote(monkeypatch):
    monkeypatch.setattr(Config, 'TTS_LOCAL_ONLY', False)
    from app.services import qwen_remote_tts
    class Rate:
        def __init__(self, *a, **kw): pass
        def try_start(self): return 0
        def cool_down(self, seconds): pass
    monkeypatch.setattr(qwen_remote_tts, 'ProviderRate', Rate)
    values = dict(API_BASE='https://dashscope.aliyuncs.com/api/v1', API_KEY='remote-test-key',
        MODEL='qwen-audio-3.1-tts-flash', VOICE='longanhuan_v3.1', SPEED='0.9',
        PITCH='1.1', VOLUME='65', LANGUAGE='zh', INSTRUCTIONS='自然清晰地讲解',
        SAMPLE_RATE='24000', RESPONSE_FORMAT='mp3', TIMEOUT_SECONDS='45')
    for key, value in values.items(): monkeypatch.setenv('TTS_REMOTE_' + key, value)
    class Store:
        def get_active_values(self, **kwargs):
            raise AssertionError('TTS must not read stale saved provider profiles')
    return RuntimeConfigResolver(Store())


def service(remote, handler):
    return OpenMaicTtsService(config_resolver=remote, transport=httpx.MockTransport(handler), voice='vivian')

@pytest.mark.anyio
async def test_remote_contract_download_and_local_voice_isolation(remote):
    calls = []
    def handler(request):
        calls.append(request)
        if request.method == 'POST':
            return httpx.Response(200, json={'output': {'audio': {'url': 'http://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/test.mp3?Signature=test'}}})
        return httpx.Response(200, content=b'ID3-test-audio', headers={'Content-Type': 'audio/mpeg'})
    audio, fmt = await service(remote, handler).synthesize(text='完整课堂讲稿', audio_id='speech')
    assert (audio, fmt) == (b'ID3-test-audio', 'mp3')
    post, download = calls
    assert str(post.url) == 'https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer'
    assert post.headers['Authorization'] == 'Bearer remote-test-key'
    assert json.loads(post.content) == {'model': 'qwen-audio-3.1-tts-flash', 'input': {
        'text': '完整课堂讲稿', 'voice': 'longanhuan_v3.1', 'format': 'mp3',
        'sample_rate': 24000, 'rate': .9, 'volume': 65, 'pitch': 1.1,
        'language_hints': ['zh'], 'instruction': '自然清晰地讲解'}}
    assert 'authorization' not in download.headers
    assert download.url.scheme == 'https'
    assert post.extensions['timeout']['read'] == 45

@pytest.mark.anyio
async def test_missing_remote_key_fails_before_network_without_local_fallback(remote, monkeypatch):
    monkeypatch.setenv('TTS_REMOTE_API_KEY', '')
    calls = []
    with pytest.raises(ValueError, match='TTS_REMOTE_API_KEY'):
        await service(remote, lambda r: calls.append(r)).synthesize(text='讲稿', audio_id='speech')
    assert not calls

@pytest.mark.anyio
@pytest.mark.parametrize('status,expected', [(401, 1), (429, 4), (503, 4)])
async def test_failure_retries_are_finite_and_do_not_switch_provider(remote, monkeypatch, status, expected):
    from app.services import qwen_remote_tts as module
    async def no_sleep(*args): pass
    monkeypatch.setattr(module.asyncio, 'sleep', no_sleep)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={'message': 'do-not-expose-remote-test-key'})
    with pytest.raises(RuntimeError, match=str(status)) as error:
        await service(remote, handler).synthesize(text='讲稿', audio_id='speech')
    assert 'remote-test-key' not in str(error.value)
    assert len(calls) == expected
    assert all(r.url.host == 'dashscope.aliyuncs.com' for r in calls)

@pytest.mark.parametrize('url', ['http://127.0.0.1/audio', 'https://evil.test/audio',
    'https://dashscope.aliyuncs.com.evil.test/audio', 'file:///etc/passwd',
    'https://user:pass@dashscope.aliyuncs.com/audio'])
def test_untrusted_download_url_rejected(url):
    with pytest.raises(RuntimeError): _audio_url(url)

@pytest.mark.anyio
async def test_missing_audio_and_html_response_are_not_playable(remote):
    for bad in [True, False]:
        def handler(request):
            if request.method == 'POST':
                return httpx.Response(200, json={} if bad else {'output': {'audio': {'url': 'https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/a'}}})
            return httpx.Response(200, text='<html>error</html>')
        with pytest.raises(RuntimeError):
            await service(remote, handler).synthesize(text='讲稿', audio_id='speech')


def test_full_workspace_endpoint_and_remote_controls(remote, monkeypatch):
    monkeypatch.setenv('TTS_REMOTE_API_BASE', 'https://workspace.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer')
    config = service(remote, None)._resolve_http_config(speed=1.2)
    assert config['url'].count('SpeechSynthesizer') == 1
    assert config['speed'] == 1.2
    assert config['voice'] == 'longanhuan_v3.1'
    monkeypatch.setenv('TTS_REMOTE_PITCH', 'nan')
    with pytest.raises(ValueError): service(remote, None)._resolve_http_config(speed=None)


def test_retry_after_is_respected_and_invalid_headers_use_backoff(monkeypatch):
    from app.services.qwen_remote_tts import _retry_delay
    monkeypatch.setattr('app.services.qwen_remote_tts.random.uniform', lambda *a:0)
    assert _retry_delay('30', 0) == 30
    assert _retry_delay('bad', 2) == 4
    assert _retry_delay('-1', 0) == 1


@pytest.mark.anyio
async def test_separate_synthesis_calls_share_actual_concurrency_slots(remote, monkeypatch, tmp_path):
    import asyncio
    monkeypatch.setenv('TTS_REMOTE_CONCURRENCY','2')
    monkeypatch.setenv('EDU_STAGE_LIMIT_DIR',str(tmp_path))
    active, maximum = 0, 0
    async def handler(request):
        nonlocal active, maximum
        if request.method == 'POST':
            active += 1; maximum = max(maximum, active)
            try:
                await asyncio.sleep(.03)
                return httpx.Response(200,json={'output':{'audio':{'url':'https://test.aliyuncs.com/a'}}})
            finally: active -= 1
        return httpx.Response(200,content=b'ID3-audio')
    await asyncio.gather(*(service(remote, handler).synthesize(text='完整讲稿',audio_id=str(i)) for i in range(8)))
    assert maximum == 2


@pytest.mark.anyio
async def test_cancellation_guard_stops_admission_before_provider_request(remote):
    from app.integrations.hyperframes.stage_limits import ADMISSION_GUARD
    def cancel(): raise RuntimeError('CANCELED')
    token = ADMISSION_GUARD.set(cancel)
    calls = []
    try:
        with pytest.raises(RuntimeError, match='CANCELED'):
            await service(remote, lambda request:calls.append(request)).synthesize(text='讲稿',audio_id='c')
        assert not calls
    finally: ADMISSION_GUARD.reset(token)
