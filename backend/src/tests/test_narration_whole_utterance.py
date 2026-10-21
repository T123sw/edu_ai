import json
import hashlib
from types import SimpleNamespace

import httpx
import pytest

from app.services.classroom_narration import narration_audio
from app.services.tts_service import SpeechService
from tests.personal_studio.test_studio import setup


@pytest.fixture
def anyio_backend():
    return 'asyncio'


class Resolver:
    def resolve(self, *args):
        return dict(base_url='http://127.0.0.1:8188/v1', model='qwen3-tts', voice='vivian', timeout_seconds=120)


@pytest.mark.anyio
async def test_long_narration_is_one_complete_request_and_has_time_to_finish(tmp_path):
    text = ('这是一个超过四十字的完整段落，包含基准值、子序列和数组 a[i]，不应当在词语中间被截断。\n' * 10).strip()
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, content=b'ID3-audio', headers={'Content-Type': 'audio/mpeg'})
    service = SpeechService(long_form=True, config_resolver=Resolver(), transport=httpx.MockTransport(respond))
    result = await narration_audio(action={'text': text}, audio_dir=tmp_path, tts=service)
    assert result.read_bytes() == b'ID3-audio'
    assert len(calls) == 1 and json.loads(calls[0].content)['input'] == text
    assert calls[0].extensions['timeout']['read'] > 120
    assert await narration_audio(action={'text': text}, audio_dir=tmp_path, tts=service) == result
    assert len(calls) == 1


@pytest.mark.anyio
async def test_oversize_text_is_never_split_or_silently_truncated(tmp_path):
    calls = []
    def respond(request):
        calls.append(request)
        raise AssertionError('oversize input must not reach HTTP')
    service = SpeechService(long_form=True, config_resolver=Resolver(), transport=httpx.MockTransport(respond))
    with pytest.raises(ValueError, match='not split or truncated'):
        await narration_audio(action={'text': '字' * 1501}, audio_dir=tmp_path, tts=service)
    with pytest.raises(ValueError, match='not split or truncated'):
        await service.synthesize(text='字' * 1501, audio_id='oversize')
    assert not calls and not list(tmp_path.glob('narration-*'))


def test_podcast_enqueue_and_retry_have_long_form_execution_window(setup):
    client, _, store, _ = setup
    request = dict(course_id='course', chapter_id='variables', request_id='whole-utterance',
                   title='变量', resource_type='podcast', config={'duration_minutes': 5})
    response = client.post('/api/personal-studio/generate', json=request)
    assert response.status_code == 202, response.text
    task = store.get_durable(response.json()['edu_job_id'])
    assert task.command['execution_timeout_seconds'] == 7200
    from app.services.podcast_generation_policy import generation_limits
    assert generation_limits({'execution_timeout_seconds': 300})['execution_timeout_seconds'] == 7200
    assert generation_limits({'execution_timeout_seconds': 10000})['execution_timeout_seconds'] == 10000
    from app.services.job_store import get_job, update_job, JobStatus
    from app.services.job_retry_service import retry_durable_job
    original = get_job(task.task_id)
    update_job(task.task_id, status=JobStatus.FAILED, retryable=True)
    retried = retry_durable_job(original, owner_user_id='alice', task_store=store)
    assert store.get_durable(retried.edu_job_id).command['execution_timeout_seconds'] == 7200


@pytest.mark.anyio
@pytest.mark.parametrize('old_version', [None, 'whole-utterance-v2'])
async def test_previous_fragmented_cache_is_not_reused(tmp_path, old_version):
    calls = []
    service = SpeechService(long_form=True, config_resolver=Resolver(),
        transport=httpx.MockTransport(lambda req: (calls.append(req) or httpx.Response(
            200, content=b'ID3-whole-audio', headers={'Content-Type':'audio/mpeg'}))))
    text = '原来的碎片缓存不应该被整段配音复用。'
    config = service._resolve_http_config(speed=None)
    identity = {k:config[k] for k in ('url','model','voice','speed','language','instructions')}
    identity.update(text=text,max_input_chars=config['max_input_chars'])
    if old_version:
        identity['narration_version'] = old_version
    key = hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    old = tmp_path / f'narration-{key}.mp3'
    old.write_bytes(b'ID3-fragmented-audio')
    result = await narration_audio(action={'text':text},audio_dir=tmp_path,tts=service)
    assert result != old and result.read_bytes() == b'ID3-whole-audio' and len(calls) == 1
