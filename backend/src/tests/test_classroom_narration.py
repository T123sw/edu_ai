import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.api.self_learning import router, service
from app.auth import get_current_user
from app.services.classroom_narration import narration_audio

@pytest.fixture
def anyio_backend():
    return 'asyncio'

class Tts:
    def __init__(self):
        self.calls = []
    def _resolve_http_config(self, *, speed):
        return dict(url='http://local/speech', model='qwen', voice='vivian', speed=speed or 1,
                    language='zh', instructions='', max_input_chars=1500)
    async def synthesize(self, *, text, audio_id, speed):
        self.calls.append(text)
        await asyncio.sleep(.01)
        return b'real-provider-test-seam', 'mp3'

@pytest.mark.anyio
async def test_cache_singleflight_and_content_invalidation(tmp_path):
    tts = Tts()
    action = dict(type='speech', text='快速排序', id='speech')
    paths = await asyncio.gather(*(narration_audio(action=action, audio_dir=tmp_path, tts=tts) for _ in range(3)))
    assert len(set(paths)) == 1 and tts.calls == ['快速排序']
    changed = await narration_audio(action={**action, 'text': '修改后的讲解'}, audio_dir=tmp_path, tts=tts)
    assert changed != paths[0] and changed.read_bytes()

@pytest.mark.anyio
async def test_failed_audio_does_not_poison_cache(tmp_path):
    tts = Tts()
    async def fail(**kwargs):
        raise TimeoutError()
    tts.synthesize = fail
    with pytest.raises(TimeoutError):
        await narration_audio(action={'text': '讲解'}, audio_dir=tmp_path, tts=tts)
    assert not list(tmp_path.glob('narration-*'))
    assert not list(tmp_path.glob('.narration-*'))


def test_route_checks_access_version_and_action_before_audio(monkeypatch, tmp_path):
    import app.api.self_learning as api
    import app.services.classroom_narration as audio_module
    calls = []
    def exact(svc, owner, ref):
        if owner != 'alice':
            raise HTTPException(404, '无权访问')
        if ref.version != 2:
            raise HTTPException(409, '指定版本不可用')
        return {'scenes': [{'id': 'scene', 'actions': [dict(id='speech', type='speech', text='正确版本的讲稿')]}]}
    async def generate(**kwargs):
        calls.append(kwargs['action']['text'])
        result = tmp_path / 'audio.mp3'
        result.write_bytes(b'audio')
        return result
    monkeypatch.setattr(api, 'exact_material', exact)
    monkeypatch.setattr(audio_module, 'narration_audio', generate)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[service] = lambda: SimpleNamespace(manager=SimpleNamespace(get_classroom_audio_dir=lambda *a: tmp_path))
    app.dependency_overrides[get_current_user] = lambda: {'username': 'alice'}
    path = '/api/self-learning/courses/course/materials/classroom/material/versions/2/narration/scene/speech?segment=0'
    with TestClient(app) as c:
        assert c.post(path).content == b'audio'
        assert c.post(path.replace('/2/', '/1/')).status_code == 409
        assert c.post(path.replace('/speech', '/other')).status_code == 404
        app.dependency_overrides[get_current_user] = lambda: {'username': 'other'}
        assert c.post(path).status_code == 404
        assert calls == ['正确版本的讲稿']


def test_segmentation_keeps_full_long_lecture():
    from app.services.classroom_narration import narration_segments
    text = '你好。' + '复杂度😀' * 500 + '！最后一段。'
    pieces = narration_segments(text)
    assert ''.join(pieces) == text
    assert max(map(len, pieces)) <= 100

@pytest.mark.anyio
async def test_remote_controls_invalidate_narration_cache(tmp_path):
    class RemoteTts(Tts):
        pitch = 1.0
        def _resolve_http_config(self, *, speed):
            return {**super()._resolve_http_config(speed=speed), 'protocol': 'qwen-audio-tts',
                    'volume': 50, 'pitch': self.pitch, 'sample_rate': 24000, 'response_format': 'mp3'}
    tts = RemoteTts()
    first = await narration_audio(action={'text': '同一讲稿'}, audio_dir=tmp_path, tts=tts)
    tts.pitch = 1.1
    second = await narration_audio(action={'text': '同一讲稿'}, audio_dir=tmp_path, tts=tts)
    assert first != second and len(tts.calls) == 2


def test_cache_singleflight_across_worker_event_loops(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    tts = Tts()
    start = Barrier(3)
    def run(_):
        start.wait(timeout=5)
        return asyncio.run(narration_audio(action={'text':'并发讲稿'}, audio_dir=tmp_path, tts=tts))
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run, i) for i in range(3)]
        paths = [f.result(timeout=10) for f in futures]
    assert len(set(paths)) == 1 and tts.calls == ['并发讲稿']
    assert paths[0].read_bytes() == b'real-provider-test-seam'
