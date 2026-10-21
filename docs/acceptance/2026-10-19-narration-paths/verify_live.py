"""Isolated real TTS acceptance through podcast and unmodified native video audio paths."""
import asyncio
import hashlib
import json
import shlex
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
load_dotenv('.env')
from sqlalchemy import create_engine, text
import os
from app.services.studio_learning_resources import render_podcast
from app.services.tts_service import SpeechService
from app.integrations.hyperframes.workflow_audio import audio_provider
from app.integrations.hyperframes.workflow_agent import WorkflowTools
from app.integrations.hyperframes.runtime import UPSTREAM

root = Path('docs/acceptance/2026-10-19-narration-paths').resolve()
work = root / 'live'; work.mkdir(exist_ok=True)
calls = []
original = SpeechService._synthesize_http
async def recorded(self, speech, config):
    item = dict(chars=len(speech), sha256=hashlib.sha256(speech.encode()).hexdigest(), timeout=config['timeout'], started_at=time.time())
    calls.append(item)
    print(json.dumps({'tts_started': item}, ensure_ascii=False), flush=True)
    try:
        result = await original(self, speech, config)
        item.update(bytes=len(result[0]), elapsed_seconds=round(time.time()-item['started_at'], 2), status='ok')
        return result
    except Exception as exc:
        item.update(status='failed', error=str(exc))
        raise
    finally:
        (root/'live-calls.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2))
        print(json.dumps({'tts_finished': item}, ensure_ascii=False), flush=True)
SpeechService._synthesize_http = recorded

with create_engine(os.environ['DATABASE_URL']).connect() as connection:
    connection.execute(text('SET TRANSACTION READ ONLY'))
    payload = connection.execute(text("select raw_payload from materials where material_id='studio_81a1266898e3452bbe25ffcfe675'")).scalar_one()
long_text = payload['content']['segments'][0]['text']
closing = '这一节的重点是理解基准值与左右子序列的关系。划分结束并不意味着两边已经分别有序，接下来还需要递归处理。请保留这段完整讲稿，让模型自然表达句子之间的联系。'
context = SimpleNamespace(is_cancel_requested=lambda:False, is_lease_valid=lambda:True,
                          progress=lambda *args:print(json.dumps({'podcast_progress':args},ensure_ascii=False),flush=True))
content = dict(title='整段配音链路验证', summary='使用实际播客第一节讲稿验证。',segments=[{'title':'实际第一节','text':long_text},{'title':'总结','text':closing}])
(root/'podcast-script.json').write_text(json.dumps(content,ensure_ascii=False,indent=2))
asyncio.run(render_podcast(content, work/'podcast', context))
assert [c['sha256'] for c in calls] == [hashlib.sha256(s['text'].encode()).hexdigest() for s in content['segments']]
print('PODCAST_COMPLETED',flush=True)

video_text = '这段视频解释快速排序中的一趟划分。首先，从当前区间选择一个元素作为基准值。然后比较其余元素，让较小的值移动到左边，让较大的值移动到右边。这里要注意，一趟划分完成后，左右两段的内部并不一定有序。它保证的是相对大小关系，而不是一次就完成全部排序。接下来分别递归处理左右子序列，每次让问题规模缩小，直到区间只剩零个或者一个元素。这时不再需要继续划分。理解这个边界，才能区分划分操作和整个排序过程。'
workspace=work/'video-workspace'; workspace.mkdir(exist_ok=True)
project=workspace/'video'; project.mkdir(exist_ok=True)
(project/'SCRIPT.md').write_text('## Opening (Frame 1)\n\n    '+video_text+'\n')
(project/'STORYBOARD.md').write_text('---\nformat: 1920x1080\nmusic: none\n---\n## Frame 1 — Opening\n- duration: 10s\n- src: compositions/frames/01-opening.html\n- status: outline\n')
def finish(tools,result):
    until=time.monotonic()+1800
    while result.get('exit_code') is None and time.monotonic()<until:
        time.sleep(2)
        result=tools.call('poll_command',{'command_id':result['command_id']})
    assert result.get('exit_code')==0,result
    return result
native=UPSTREAM/'skills/faceless-explainer/scripts/audio.mjs'
tools=WorkflowTools(workspace,lambda:None)
try:
    with audio_provider(workspace,guard=lambda:None,options={'voice':'vivian','speed':1.0}):
        command=f'cd {shlex.quote(str(project))} && node {shlex.quote(str(native))} --script SCRIPT.md --storyboard STORYBOARD.md --hyperframes . --out audio_meta.json'
        finish(tools,tools.call('run_command',{'command':command}))
        meta=json.loads((project/'audio_meta.json').read_text())
        assert len(meta['voices'])==1
        assert len(calls)==3 and calls[-1]['sha256']==hashlib.sha256(video_text.encode()).hexdigest()
        command=f'cd {shlex.quote(str(project))} && node {shlex.quote(str(native))} sync-durations --audio-meta audio_meta.json --storyboard STORYBOARD.md'
        finish(tools,tools.call('run_command',{'command':command}))
        assert 'duration: 10s' not in (project/'STORYBOARD.md').read_text()
finally:
    tools.close()
print('VIDEO_NATIVE_AUDIO_COMPLETED',flush=True)
media=[work/'podcast/podcast.mp3',project/meta['voices'][0]['path']]
checks=[]
for path in media:
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_name,sample_rate,channels','-of','json',str(path)]))
    decoded=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],capture_output=True,text=True)
    assert decoded.returncode==0 and not decoded.stderr
    checks.append({'path':str(path.relative_to(root)),'probe':probe,'decode':'passed'})
result=dict(status='passed',calls=calls,media=checks,video_metadata=meta,
            scope='Real podcast renderer with two chapters; original HyperFrames audio CLI/provider plus duration sync. No full video animation generation or ASR semantic audit.')
(root/'live-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False),flush=True)
