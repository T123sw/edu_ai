"""Render a minimal native composition with the verified, full scene voiceover."""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
import json
import shutil
import subprocess
from app.integrations.hyperframes.runtime import NativeRuntime, RUNTIME

root=Path('docs/acceptance/2026-10-19-narration-paths').resolve()
project=root/'live/video-workspace/video'
meta=json.loads((project/'audio_meta.json').read_text())
voice=meta['voices'][0]
duration=voice['duration_s']
(project/'assets').mkdir(exist_ok=True)
shutil.copyfile(RUNTIME/'node_modules/gsap/dist/gsap.min.js',project/'assets/gsap.min.js')
(project/'index.html').write_text('''<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=640,height=360"><script src="assets/gsap.min.js"></script>
<style>*{box-sizing:border-box;margin:0}html,body{width:640px;height:360px;overflow:hidden;background:#14223a;color:white;font-family:sans-serif}#root{width:640px;height:360px;padding:40px;display:flex;flex-direction:column;justify-content:center;gap:20px}h1{font-size:32px}p{font-size:20px;line-height:1.8;color:#c7defa}</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="DURATION" data-width="640" data-height="360">
<h1 id="title" class="clip" data-start="0" data-duration="DURATION" data-track-index="0">快速排序：一趟划分</h1>
<p class="clip" data-start="0" data-duration="DURATION" data-track-index="1">完整场景讲稿 · 单次配音<br>选择基准 → 划分区间 → 递归处理</p>
<audio src="AUDIO" class="clip" data-start="0" data-duration="DURATION" data-track-index="2"></audio></div>
<script>window.__timelines=window.__timelines||{};const tl=gsap.timeline({paused:true});tl.fromTo('#title',{opacity:0},{opacity:1,duration:.6},0);tl.to({}, {duration:DURATION-.6});window.__timelines.main=tl;tl.seek(0);</script></body></html>
'''.replace('DURATION',str(duration)).replace('AUDIO',voice['path']))
runtime=NativeRuntime()
info=runtime.render(str(project),str(project/'verification.mp4'))
assert any(s['codec_type']=='audio' for s in info['streams'])
assert any(s['codec_type']=='video' for s in info['streams'])
assert abs(float(info['format']['duration'])-duration)<.3
result=subprocess.run(['ffmpeg','-v','error','-i',str(project/'verification.mp4'),'-f','null','-'],capture_output=True,text=True)
assert result.returncode==0 and not result.stderr,result.stderr
(root/'video-render.json').write_text(json.dumps({'status':'passed','scope':'Minimal native composition, using full verified scene audio','probe':info},ensure_ascii=False,indent=2))
print('NATIVE_MP4_RENDER_AND_DECODE_PASSED',flush=True)
