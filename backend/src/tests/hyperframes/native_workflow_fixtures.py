"""Explicit unit fixtures for the host boundary, never real generation evidence."""
import json
from pathlib import Path
import shutil


class Gateway:
    calls = 0
    def chat(self, messages, **kwargs):
        self.calls += 1
        return json.dumps({'brief_markdown': '---\nworkflow: general-video\nflow: automation\nstoryboard: no\nlength: 300s\n---\n## Intent\n完整解释用户的教学目标。',
                          'decisions': {'target_minutes': 5, 'duration_source': 'default', 'narration': True, 'reason': '用户未指定时长，采用默认目标'}})


class Checkpoint:
    state = None
    def load_generation_state(self): return self.state
    def save_generation_state(self, value): self.state = json.loads(json.dumps(value))


class Runtime:
    fail = False
    duration = 2.75
    def probe(self, path):
        if self.fail: raise RuntimeError('probe interrupted')
        return {'format':{'duration':str(self.duration)},'streams':[{'codec_type':'video'},{'codec_type':'audio'}]}


class Runner:
    calls = []
    def __init__(self, gateway, workspace, guard):
        self.workspace, self.guard = Path(workspace), guard
    def run(self, prompt):
        self.calls.append(json.loads((self.workspace/'REQUEST.json').read_text()))
        project = self.workspace/'videos/example';project.mkdir(parents=True,exist_ok=True)
        assets=self.workspace/'assets'
        if assets.exists(): shutil.copytree(assets,project/'assets',dirs_exist_ok=True)
        (project/'compositions/frames').mkdir(parents=True,exist_ok=True)
        (project/'compositions/frames/01-concept.html').write_text('<div data-composition-id="01-concept">完整原生分镜</div>')
        (project/'BRIEF.md').write_text('---\nworkflow: faceless-explainer\nflow: automation\nstoryboard: no\n---\n用户需求')
        (project/'frame.md').write_text('# 原生视觉设计')
        (project/'STORYBOARD.md').write_text('---\nformat: 1920x1080\n---\n## Frame 1 — 概念\n- status: animated\n- duration: 2.75s\n- src: compositions/frames/01-concept.html\n- scene: 直线动态平移\n')
        (project/'SCRIPT.md').write_text('## Concept (Frame 1)\n\n    完整原生讲稿，不是平台生成的 JSON。\n')
        (project/'assets').mkdir(exist_ok=True)
        (project/'assets/voice.mp3').write_bytes(b'unit fixture, not media')
        (project/'index.html').write_text('<html><head></head><body><div data-composition-id="main" data-duration="2.75"><div data-composition-id="01-concept" data-composition-src="compositions/frames/01-concept.html" data-start="0" data-duration="2.75"></div><audio src="assets/voice.mp3" data-start="0" data-duration="2.75"></audio></div></body></html>')
        (project/'renders').mkdir(exist_ok=True)
        video=project/'renders/video.mp4';video.write_bytes(b'unit fixture; runtime probe is injected')
        self.guard()
        return {'project_directory':str(project),'video_path':str(video)}
