"""Real seven-chapter benchmark and native multi-scene audio acceptance."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import threading
import time
from types import SimpleNamespace
import urllib.request

from dotenv import load_dotenv
load_dotenv('.env')
from sqlalchemy import create_engine,text
import httpx
from app.services.tts_service import SpeechService
from app.services.studio_learning_resources import render_podcast
from app.integrations.hyperframes.workflow_audio import audio_provider
from app.integrations.hyperframes.workflow_agent import WorkflowTools
from app.integrations.hyperframes.runtime import UPSTREAM

root=Path('docs/acceptance/2026-10-19-tts-concurrency').resolve()
work=root/'live';work.mkdir(exist_ok=True)
for attempt in range(60):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8191/health',timeout=2) as r: health=json.load(r)
        if health.get('status')=='ok' and health.get('service')=='local-tts' and health.get('device')=='cuda:1':break
    except Exception:pass
    time.sleep(1)
else:raise RuntimeError('batch TTS not healthy')
resolve=SpeechService._resolve_http_config
SpeechService._resolve_http_config=lambda self,**kwargs:{**resolve(self,**kwargs),'url':'http://127.0.0.1:8191/v1/audio/speech'}
post=httpx.AsyncClient.post;calls=[];guard=threading.Lock()
async def recorded(self,url,**kwargs):
    payload=kwargs['json'];item={'chars':len(payload['input']),'text_sha256':hashlib.sha256(payload['input'].encode()).hexdigest(),'started_at':time.time()}
    with guard:calls.append(item)
    response=await post(self,url,**kwargs)
    item.update(elapsed_seconds=round(time.time()-item['started_at'],2),http_status=response.status_code,
                batch_id=response.headers.get('x-tts-batch-id'),batch_size=response.headers.get('x-audio-batch'),
                fragments=response.headers.get('x-audio-fragments'),input_chars=response.headers.get('x-audio-input-chars'))
    with guard:(root/'live-calls.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2))
    print(json.dumps({'tts':item},ensure_ascii=False),flush=True)
    return response
httpx.AsyncClient.post=recorded

job='studio_fee1f2ac1264c40d2394e7216027'
with create_engine(os.environ['DATABASE_URL']).connect() as c:
    c.execute(text('SET TRANSACTION READ ONLY'))
    content=c.execute(text('select raw_payload from materials where material_id=:job'),{'job':job}).scalar_one()['content']
    baseline=dict(c.execute(text('select started_at,finished_at from durable_tasks where task_id=:job'),{'job':job}).mappings().one())
baseline['wall_seconds']=baseline['finished_at']-baseline['started_at']
(root/'podcast-script.json').write_text(json.dumps(content,ensure_ascii=False,indent=2))
ctx=SimpleNamespace(is_cancel_requested=lambda:False,is_lease_valid=lambda:True,
                    progress=lambda *v:print(json.dumps({'progress':v},ensure_ascii=False),flush=True))
start=time.monotonic()
asyncio.run(render_podcast(content,work/'podcast',ctx))
wall=time.monotonic()-start
expected=[hashlib.sha256(s['text'].encode()).hexdigest() for s in content['segments']]
assert len(calls)==7 and sorted(c['text_sha256'] for c in calls)==sorted(expected)
assert all(c['http_status']==200 and c['fragments']=='1' and int(c['input_chars'])==c['chars'] for c in calls)
assert max(int(c['batch_size']) for c in calls)>=2
assert max(c['started_at'] for c in calls)-min(c['started_at'] for c in calls)<3
podcast_results={'wall_seconds':round(wall,2),'baseline_job_wall_seconds':round(baseline['wall_seconds'],2),
                 'speedup_vs_previous_job':round(baseline['wall_seconds']/wall,2),'calls':list(calls),
                 'baseline_scope':'Previous production run of the same seven-chapter script; includes original script-writing and saving overhead.'}
(root/'podcast-result.json').write_text(json.dumps(podcast_results,ensure_ascii=False,indent=2))
print('SEVEN_CHAPTER_PODCAST_PASSED',json.dumps(podcast_results),flush=True)

texts=[
'快速排序先选取一个基准值，再比较左右两边的元素。这个场景保留完整的讲稿，用来验证多个场景同时配音时，每个场景仍然拥有独立且完整的声音文件。',
'划分结束后，基准值左右两边的元素满足相对大小关系。两边内部还不一定有序，需要继续递归处理，不能把一次划分理解成整个排序过程已经结束。',
'递归处理的关键是让问题规模不断缩小。当区间只有零个或者一个元素时，就可以直接返回。每个场景的声音应该对应自己的文字，不能与其他场景混在一起。',
'最后回顾整个流程：选择基准，划分区间，递归处理子序列。我们将四个完整场景并行送入配音服务，再按照原来的场景顺序组装，保持讲解的先后关系。']
workspace=work/'video-workspace';project=workspace/'video';project.mkdir(parents=True,exist_ok=True)
(project/'SCRIPT.md').write_text('\n\n'.join(f'## Scene {i+1} (Frame {i+1})\n\n    {t}' for i,t in enumerate(texts))+'\n')
(project/'STORYBOARD.md').write_text('---\nformat: 1920x1080\nmusic: none\n---\n'+'\n'.join(f'## Frame {i+1} — Scene {i+1}\n- duration: 10s\n- src: compositions/frames/0{i+1}.html\n- status: outline\n' for i in range(4)))
def finish(tools,result):
    deadline=time.monotonic()+1800
    while result.get('exit_code') is None and time.monotonic()<deadline:
        time.sleep(2);result=tools.call('poll_command',{'command_id':result['command_id']})
    assert result.get('exit_code')==0,result
native=UPSTREAM/'skills/faceless-explainer/scripts/audio.mjs';tools=WorkflowTools(workspace,lambda:None)
video_start=time.monotonic()
try:
    with audio_provider(workspace,guard=lambda:None,options={'voice':'vivian','speed':1.0}):
        command=f'cd {shlex.quote(str(project))} && node {shlex.quote(str(native))} --script SCRIPT.md --storyboard STORYBOARD.md --hyperframes . --out audio_meta.json'
        finish(tools,tools.call('run_command',{'command':command}))
        meta=json.loads((project/'audio_meta.json').read_text())
        assert [v['frame'] for v in meta['voices']]==[1,2,3,4]
        finish(tools,tools.call('run_command',{'command':f'cd {shlex.quote(str(project))} && node {shlex.quote(str(native))} sync-durations --audio-meta audio_meta.json --storyboard STORYBOARD.md'}))
finally:tools.close()
video_calls=calls[7:]
assert len(video_calls)==4 and sorted(c['text_sha256'] for c in video_calls)==sorted(hashlib.sha256(t.encode()).hexdigest() for t in texts)
assert max(int(c['batch_size']) for c in video_calls)>=2 and all(c['fragments']=='1' for c in video_calls)
checks=[]
for p in [work/'podcast/podcast.mp3']+[project/v['path'] for v in meta['voices']]:
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(p)]))
    decoded=subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],capture_output=True,text=True)
    assert decoded.returncode==0 and not decoded.stderr
    checks.append({'file':str(p.relative_to(root)),'duration':float(probe['format']['duration'])})
with urllib.request.urlopen('http://127.0.0.1:8191/stats',timeout=5) as r:stats=json.load(r)
result={'status':'passed','podcast':podcast_results,'video':{'wall_seconds':round(time.monotonic()-video_start,2),'calls':video_calls,'metadata':meta},'media':checks,'tts_stats':stats}
(root/'live-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('PODCAST_AND_VIDEO_PARALLEL_AUDIO_PASSED',flush=True)
