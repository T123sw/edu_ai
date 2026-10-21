import asyncio,json,time,urllib.request
from pathlib import Path
import httpx
import soundfile as sf
from services.local_tts.pitch import median_pitch
root=Path('docs/acceptance/2026-10-19-stable-voice');out=root/'online';out.mkdir(exist_ok=True)
async def main():
 deadline=time.monotonic()+180
 while time.monotonic()<deadline:
  try:
   async with httpx.AsyncClient(timeout=3) as client:
    r=await client.get('http://127.0.0.1:8191/health');health=r.json()
   if health.get('voice_profile')=='stable-narration-v1':break
  except Exception:pass
  await asyncio.sleep(2)
 else:raise RuntimeError('stable TTS not ready')
 rows=json.loads((root/'real-model.json').read_text())
 texts=[r['text'] for r in rows if r['name'].startswith('stable-')]
 assert len(texts)==4
 async with httpx.AsyncClient(timeout=600) as client:
  async def request(index,text):
   start=time.monotonic()
   r=await client.post('http://127.0.0.1:8191/v1/audio/speech',json={'model':'qwen3-tts','input':text,'voice':'vivian','language':'zh-CN','speed':1,'instructions':['高音、兴奋','低沉、沙哑','夸张角色','自然讲解'][index],'response_format':'wav'})
   r.raise_for_status()
   assert r.headers['x-voice-profile']=='stable-narration-v1' and r.headers['x-voice-id']=='vivian'
   assert r.headers['x-audio-fragments']=='1'
   path=out/f'scene-{index+1}.wav';path.write_bytes(r.content)
   print('RESPONSE',index,round(time.monotonic()-start,2),flush=True)
   return {'index':index,'chars':len(text),'file':path.name,'batch_id':r.headers['x-tts-batch-id'],'batch_size':int(r.headers['x-audio-batch']),'elapsed_seconds':round(time.monotonic()-start,2)}
  results=await asyncio.gather(*(request(i,t) for i,t in enumerate(texts)))
 assert max(r['batch_size'] for r in results)>=2
 for row in results:
  audio,sr=sf.read(out/row['file']);pitch=median_pitch(audio,sr)
  row.update(pitch_median_hz=round(pitch,2),duration=len(audio)/sr)
  assert abs(pitch-240)<20,row
 (root/'online-result.json').write_text(json.dumps({'status':'passed','health':health,'results':results},ensure_ascii=False,indent=2))
 print('ONLINE_STABLE_PARALLEL_VOICE_PASSED',json.dumps(results),flush=True)
asyncio.run(main())
