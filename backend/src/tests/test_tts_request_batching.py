import asyncio
import ast
import hashlib
import logging
from pathlib import Path
from types import SimpleNamespace
import time
import uuid

import numpy as np
import pytest
from services.local_tts.batching import SpeechBatchQueue
from services.local_tts.voice_profile import VOICE_PROFILE, VOICE_INSTRUCTIONS, GENERATION_OPTIONS, request_sampling


@pytest.fixture
def anyio_backend(): return 'asyncio'


@pytest.mark.anyio
async def test_seven_complete_requests_run_in_two_native_batches_in_order():
    calls = []
    def process(items):
        calls.append(list(items))
        return [value + '-audio' for value in items]
    queue = SpeechBatchQueue(process, max_batch=4, max_chars=1600, length=len, batch_window=.02)
    inputs = [str(i) + '完整讲稿。' * 30 for i in range(7)]
    try:
        outputs = await asyncio.gather(*(queue.submit(value) for value in inputs))
        assert outputs == [value + '-audio' for value in inputs]
        assert [len(batch) for batch in calls] == [4, 3]
        assert [text for batch in calls for text in batch] == inputs
    finally: await queue.close()


@pytest.mark.anyio
async def test_batch_budget_never_splits_an_utterance_and_failure_is_isolated():
    calls = []
    def process(items):
        calls.append(list(items))
        return [RuntimeError('one bad request') if item.startswith('b') else item for item in items]
    queue = SpeechBatchQueue(process, max_batch=4, max_chars=1600, length=len, batch_window=.01)
    inputs = ['a'*800, 'b'*800, 'c'*800]
    try:
        results = await asyncio.gather(*(queue.submit(v) for v in inputs), return_exceptions=True)
        assert results[0] == inputs[0] and isinstance(results[1], RuntimeError) and results[2] == inputs[2]
        assert calls == [inputs[:2], inputs[2:]]
        assert await queue.submit('next') == 'next'
    finally: await queue.close()


@pytest.mark.anyio
async def test_cancelled_queued_request_is_not_inferred():
    calls = []
    queue = SpeechBatchQueue(lambda items: calls.extend(items) or items, length=len, batch_window=.05)
    first = asyncio.create_task(queue.submit('first'))
    canceled = asyncio.create_task(queue.submit('cancel-me'))
    await asyncio.sleep(.01)
    canceled.cancel()
    with pytest.raises(asyncio.CancelledError): await canceled
    assert await first == 'first'
    await queue.close()
    assert calls == ['first']


def engine(model):
    tree = ast.parse(Path('services/local_tts/qwen_server.py').read_text())
    names = {'_request_key', '_generate_batch', '_generate_audio'}
    cache = {}
    ns = dict(hashlib=hashlib, uuid=uuid, time=time, log=logging.getLogger('test-tts'),
              VOICE_PROFILE=VOICE_PROFILE, VOICE_INSTRUCTIONS=VOICE_INSTRUCTIONS, GENERATION_OPTIONS=GENERATION_OPTIONS,
              request_sampling=request_sampling,
              LANGUAGE_ALIASES={'zh-cn':'chinese'}, VOICE_LANG={'vivian':'chinese'}, model=model,
              torch=SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:False)),
              _cache_get=cache.get, _cache_put=lambda k,v:cache.__setitem__(k,v),
              _encode_audio=lambda req,audio,sr:(str(int(audio[0])).encode(), 'audio/mpeg', 100),
              _stats={k:0 for k in ['model_calls','batch_calls','max_batch_observed','infer_ms','fallback_calls','requests','sentences','audio_ms']})
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'qwen_server.py','exec'),ns)
    return ns


def requests(n):
    return [(SimpleNamespace(input=str(i)+'完整讲稿。'*20,language='zh-CN',instructions='自然讲解',speed=1.0,response_format='mp3'),'vivian') for i in range(n)]


def test_native_gpu_batch_receives_full_distinct_texts_and_preserves_output_mapping():
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        return [np.array([i]) for i in range(len(kwargs['text']))], 24000
    ns = engine(SimpleNamespace(generate_custom_voice=generate))
    inputs = requests(4)
    results = ns['_generate_batch'](inputs)
    assert len(calls) == 1 and calls[0]['text'] == [r.input for r,_ in inputs]
    assert calls[0]['speaker'] == ['vivian']*4
    assert calls[0]['do_sample'] is False and calls[0]['subtalker_dosample'] is False
    assert calls[0]['instruct'] == [VOICE_INSTRUCTIONS]*4
    assert [r[0] for r in results] == [b'0',b'1',b'2',b'3']
    assert len({r[4] for r in results}) == 1 and all(r[3]==4 for r in results)
    assert ns['_generate_batch'](inputs)[0][4] == 'cache' and len(calls) == 1


def test_oom_retries_smaller_batches_without_cutting_text():
    calls = []
    def generate(**kwargs):
        assert kwargs['do_sample'] is False and kwargs['subtalker_dosample'] is False
        texts = kwargs['text'];calls.append(texts)
        if len(texts)>2: raise MemoryError('simulated GPU capacity')
        return [np.array([int(t[0])]) for t in texts],24000
    ns = engine(SimpleNamespace(generate_custom_voice=generate))
    inputs=requests(4);result=ns['_generate_batch'](inputs)
    assert calls == [[r.input for r,_ in inputs],[r.input for r,_ in inputs[:2]],[r.input for r,_ in inputs[2:]]]
    assert [r[0] for r in result] == [b'0',b'1',b'2',b'3']
    assert all(r[3]==2 for r in result) and ns['_stats']['fallback_calls']==1


def test_scene_instructions_cannot_change_narrator_style_or_reuse_legacy_cache():
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        return [np.array([1])], 24000
    ns = engine(SimpleNamespace(generate_custom_voice=generate))
    req, voice = requests(1)[0]
    req.instructions = '用激动的高音角色声线朗读'
    first = ns['_generate_batch']([(req, voice)])
    assert calls[0]['instruct'] == VOICE_INSTRUCTIONS
    old_key = hashlib.sha256(
        f'whole-v2|{voice}|chinese|{req.instructions}|{req.speed}|{req.response_format}|{req.input}'.encode()
    ).hexdigest()
    assert ns['_request_key'](req, voice) != old_key
    req.instructions = '低沉、沙哑'
    repeated = ns['_generate_batch']([(req, voice)])
    assert repeated[0][:3] == first[0][:3] and len(calls) == 1


def test_waveform_decode_limits_memory_without_splitting_any_code_sequence():
    from services.local_tts.batching import bound_waveform_decode
    calls=[]
    def original(items):
        calls.append(items)
        return [items[0]['audio_codes']],24000
    tokenizer=SimpleNamespace(decode=original)
    model=SimpleNamespace(model=SimpleNamespace(speech_tokenizer=tokenizer))
    bound_waveform_decode(model)
    codes=[{'audio_codes':np.arange(1000+i)} for i in range(4)]
    waves,rate=tokenizer.decode(codes)
    assert rate==24000 and len(calls)==4
    for code,wave,call in zip(codes,waves,calls):
        assert len(call)==1 and call[0] is code and wave is code['audio_codes']
