"""Real model comparison, isolated from user media and active TTS process."""
import os
os.environ['QWEN_TTS_DEVICE']='cuda:0'
import json,time,hashlib,io
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from services.local_tts import qwen_server as server
from services.local_tts.voice_profile import GENERATION_OPTIONS,VOICE_INSTRUCTIONS
root=Path('docs/acceptance/2026-10-19-stable-voice');out=root/'audio';out.mkdir(exist_ok=True)
texts=[
'快速排序先选取一个基准值，再比较左右两边的元素。这个场景保留完整的讲稿，用来验证多个场景同时配音时，每个场景仍然拥有独立且完整的声音文件。',
'划分结束后，基准值左右两边的元素满足相对大小关系。两边内部还不一定有序，需要继续递归处理，不能把一次划分理解成整个排序过程已经结束。',
'递归处理的关键是让问题规模不断缩小。当区间只有零个或者一个元素时，就可以直接返回。每个场景的声音应该对应自己的文字，不能与其他场景混在一起。',
'最后回顾整个流程：选择基准，划分区间，递归处理子序列。我们将四个完整场景并行送入配音服务，再按照原来的场景顺序组装，保持讲解的先后关系。']
records=json.loads((root/'baseline-initial.json').read_text())
def save(group,values,signals,sr,elapsed):
 for i,(text,a) in enumerate(zip(values,signals)):
  a=np.asarray(a).squeeze();name=f'{group}-{i}.wav';sf.write(out/name,a,sr)
  row={'name':name,'text':text,'chars':len(text),'duration':round(len(a)/sr,4),'sample_rate':sr,'samples':len(a),'sha256_float':hashlib.sha256(a.tobytes()).hexdigest(),'peak':float(np.max(np.abs(a))),'elapsed_batch':round(elapsed,2)}
  records.append(row)
  assert len(a)>sr and np.isfinite(a).all() and np.max(np.abs(a))>.005
  assert len(a)/sr < len(text)*.6+12,('possible repetition/runaway',row)
 (root/'real-model.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
 print('FINISHED',group,round(elapsed,2),[r['duration'] for r in records if r['name'].startswith(group+'-')],flush=True)
def run(group,values,stable=True):
 start=time.monotonic()
 if stable:
  pairs=[(server.SpeechRequest(model='qwen3-tts',input=t,voice='vivian',response_format='wav',instructions='自然、清晰的教师讲解语气'),'vivian') for t in values]
  server._cache.clear() # Ensure repeated text is genuinely inferred again.
  result=server._generate_batch(pairs)
  waves=[];sr=24000
  for r in result:
   if isinstance(r,Exception):raise r
   a,sr=sf.read(io.BytesIO(r[0]));waves.append(a)
 else:
  waves,sr=server.model.generate_custom_voice(text=values,speaker=['vivian']*len(values),language=['chinese']*len(values),instruct=['自然、清晰的教师讲解语气']*len(values))
 save(group,values,waves,sr,time.monotonic()-start)
GENERATION_OPTIONS['max_new_tokens']=720
run('stable',texts)
run('repeat',[texts[0],texts[0],texts[1]])
long_text=json.loads(Path('docs/acceptance/2026-10-19-tts-concurrency/podcast-script.json').read_text())['segments'][0]['text']
GENERATION_OPTIONS['max_new_tokens']=2200
run('long',[long_text])
print('REAL_MODEL_COMPLETE',flush=True)
