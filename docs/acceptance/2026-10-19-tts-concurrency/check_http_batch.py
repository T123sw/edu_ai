"""Exercise real FastAPI routes/queue/encoding with an isolated deterministic model."""
import sys
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import io
import time
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

calls=[]
class FakeModel:
    def __init__(self):
        self.model=SimpleNamespace(speech_tokenizer=SimpleNamespace(decode=lambda value:None))
    def generate_custom_voice(self,**kwargs):
        calls.append(kwargs)
        time.sleep(.1)
        texts=kwargs['text'] if isinstance(kwargs['text'],list) else [kwargs['text']]
        return [np.full(2400,(int(t[0])+1)*.1,dtype=np.float32) for t in texts],24000
sys.modules['qwen_tts']=SimpleNamespace(Qwen3TTSModel=SimpleNamespace(from_pretrained=lambda *a,**k:FakeModel()))
from services.local_tts.qwen_server import app
with TestClient(app) as client:
    def request(i):
        text=str(i)+'完整的一节讲稿，不能切成短句。'*10
        return text,client.post('/v1/audio/speech',json={'model':'qwen3-tts','input':text,'voice':'vivian','response_format':'wav'})
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(request,range(4)))
    assert len(calls)==1 and len(calls[0]['text'])==4
    assert len({r.headers['x-tts-batch-id'] for _,r in results})==1
    for i,(text,r) in enumerate(results):
        assert r.status_code==200,r.text
        assert r.headers['x-audio-fragments']=='1' and int(r.headers['x-audio-input-chars'])==len(text)
        wave,rate=sf.read(io.BytesIO(r.content))
        assert rate==24000 and abs(wave.mean()-(i+1)*.1)<.001
    assert client.get('/health').json()['status']=='ok'
    stats=client.get('/stats').json()
    assert stats['max_batch_observed']==4 and stats['active_requests']==0
    assert client.post('/v1/audio/speech',json={'model':'qwen3-tts','input':'字'*1501}).status_code==413
print('PASS: four HTTP requests share one native model batch; full text and corresponding audio preserved, no fragments, 1501 characters explicitly rejected.')
