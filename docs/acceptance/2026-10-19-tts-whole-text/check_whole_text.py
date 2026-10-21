"""Exercise production audio generation without loading another GPU model."""
import ast
import collections
import hashlib
import io
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import numpy as np
import soundfile as sf

source = Path('services/local_tts/qwen_server.py').read_text()
tree = ast.parse(source)
ns = dict(np=np, sf=sf, io=io, hashlib=hashlib, time=time,
          SpeechRequest=SimpleNamespace, LANGUAGE_ALIASES={'zh-cn': 'chinese'},
          VOICE_LANG={'vivian': 'chinese'}, CACHE_SIZE=256,
          _cache=collections.OrderedDict(), _cache_lock=threading.Lock(),
          _stats=dict(infer_ms=0, sentences=0, cache_hits=0))
functions = {'_generate_audio', '_cache_get', '_cache_put', '_wav_bytes'}
exec(compile(ast.Module(body=[node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name in functions], type_ignores=[]),
    'qwen_server.py', 'exec'), ns)
calls = []
def generate(**kwargs):
    calls.append(kwargs)
    return [np.zeros(2400, dtype=np.float32)], 24000
ns['model'] = SimpleNamespace(generate_custom_voice=generate)
for length in (41, 407, 778, 1500):
    text = ('基准值（pivot）在当前位置。下一步比较 a[i] 和 a[j]，时间复杂度 O(n²)。\n' * 40)[:length]
    req = SimpleNamespace(input=text, language='zh-CN', instructions='自然、清晰的教师讲解语气',
                          speed=1.0, response_format='wav')
    before = len(calls)
    audio, mime, duration = ns['_generate_audio'](req, 'vivian')
    assert len(calls) == before + 1
    assert calls[-1]['text'] == text.strip()
    assert isinstance(calls[-1]['text'], str)
    assert calls[-1]['speaker'] == 'vivian'
    assert calls[-1]['instruct'] == req.instructions
    assert audio[:4] == b'RIFF' and mime == 'audio/wav' and duration == 100
    assert ns['_generate_audio'](req, 'vivian')[0] == audio
    assert len(calls) == before + 1
assert '_split_sentences' not in source
compile(source, 'qwen_server.py', 'exec')
print('PASS: 41/407/778/1500 characters reach the model unchanged in one call; WAV and cache checks passed.')
