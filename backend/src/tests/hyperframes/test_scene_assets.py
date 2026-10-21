import json
from pathlib import Path
import subprocess
import threading
import time

from app.integrations.hyperframes.workflow_agent import WorkflowTools
from app.integrations.hyperframes.workflow_audio import audio_provider
from tests.hyperframes.test_workflow_host import finish


def test_general_video_audio_request_resolves_relative_to_project(tmp_path):
    project = tmp_path/'video'; project.mkdir()
    request = project/'audio_request.json'
    request.write_text(json.dumps({'lines': [{'id': 'opening', 'text': '完整讲稿'}]}))
    fixture = tmp_path/'tone.mp3'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=0.2',str(fixture)],check=True)
    calls = []
    def voice(text, cache, options):
        calls.append(text); return fixture
    tools = WorkflowTools(tmp_path, lambda: None)
    try:
        with audio_provider(tmp_path, guard=lambda: None, options={}, narrate=voice):
            for path in ('audio_request.json', str(request)):
                finish(tools, tools.call('prepare_narration', {'project_directory': str(project), 'request_file': path}))
        assert calls == ['完整讲稿']
        meta = json.loads((project/'audio_meta.json').read_text())
        assert meta['voices'][0]['id'] == 'opening'
        assert meta['voices'][0]['duration_s'] > 0
    finally:
        tools.close()


def test_native_scene_preparation_and_exact_dispatch_preserve_full_inputs(tmp_path):
    project = tmp_path/'video'; project.mkdir()
    (project/'SCRIPT.md').write_text('## Opening (Frame 1)\n\n    这是完整讲稿，不可缩写。\n')
    (project/'STORYBOARD.md').write_text('---\nformat: 1920x1080\nmusic: none\ncaptions: none\n---\n## Frame 1 — Opening\n- duration: 10s\n- src: compositions/frames/01-opening.html\n- status: outline\n- blueprint: kinetic-type-beats\n- rules: 3d-camera-flight, motion-blur-streak\n')
    (project/'frame.md').write_text('NATIVE_DESIGN_SENTINEL')
    (project/'.hyperframes').mkdir()
    (project/'.hyperframes/host-assets.json').write_text('{"font_family":"Noto Sans SC"}')
    fixture=tmp_path/'tone.mp3'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=0.2',str(fixture)],check=True)
    calls=[]; prompts=[]
    def voice(text, cache, options):
        calls.append(text); time.sleep(.3); return fixture
    def runner(prompt, **kwargs):
        prompts.append(prompt); return {'summary':'done'}
    tools=WorkflowTools(tmp_path,lambda:None,runner=runner)
    try:
        with audio_provider(tmp_path,guard=lambda:None,options={},narrate=voice):
            first=tools.call('prepare_scene_assets',{'project_directory':str(project)})
            duplicate=tools.call('prepare_scene_assets',{'project_directory':str(project)})
            assert first['command_id']==duplicate['command_id']
            finish(tools,first)
            # A later call reuses the per-line speech cache, including after retry.
            finish(tools,tools.call('prepare_scene_assets',{'project_directory':str(project)}))
        manifest=json.loads((project/'.hyperframes/host-scene-assets.json').read_text())
        assert calls==['这是完整讲稿，不可缩写。']
        assert manifest['packets'][0]['frameId']=='01-opening'
        assert 'duration: 10s' not in (project/'STORYBOARD.md').read_text()
        role=Path(manifest['role_file']).read_text()
        packet=Path(manifest['packets'][0]['path']).read_text()
        assert len(packet.encode())>48_000  # Full native recipes survive, no trimming loop.
        result=tools.call('dispatch_frames',{'project_directory':str(project)})
        assert result['ok'], result
        tools.workers.poll(wait_seconds=5)
        assert len(prompts)==1
        assert role in prompts[0] and packet in prompts[0]
        assert 'NATIVE_DESIGN_SENTINEL' in prompts[0]
        assert str(project/'frame.md') in prompts[0]
        unknown=tools.call('dispatch_frames',{'project_directory':str(project),'frame_ids':['absent']})
        assert not unknown['ok'] and len(prompts)==1
    finally: tools.close()


def test_invalid_script_fails_before_audio_and_clears_stale_manifest(tmp_path):
    project=tmp_path/'video'; project.mkdir()
    (project/'SCRIPT.md').write_text('Unindented prose with no native frame heading')
    (project/'.hyperframes').mkdir()
    (project/'.hyperframes/host-scene-assets.json').write_text('{"packets":[]}')
    tools=WorkflowTools(tmp_path,lambda:None)
    try:
        result=tools.call('prepare_scene_assets',{'project_directory':str(project)})
        if result['exit_code'] is None:
            result=tools.call('poll_command',{'command_id':result['command_id']})
        assert result['exit_code']==1
        assert 'four spaces' in result['output']
        assert not (project/'.hyperframes/host-scene-assets.json').exists()
        assert not tools.call('prepare_scene_assets',{'project_directory':str(project),'workflow':'../elsewhere'})['ok']
    finally: tools.close()


def test_native_silent_explainer_keeps_packets_without_speech(tmp_path):
    project=tmp_path/'video'; project.mkdir()
    (project/'STORYBOARD.md').write_text('---\nformat: 1920x1080\nmusic: none\ncaptions: none\n---\n## Frame 1 — Opening\n- duration: 5s\n- src: compositions/frames/01-opening.html\n- status: outline\n- blueprint: kinetic-type-beats\n')
    (project/'frame.md').write_text('Silent teaching diagram')
    tools=WorkflowTools(tmp_path,lambda:None)
    try:
        finish(tools,tools.call('prepare_scene_assets',{'project_directory':str(project)}))
        manifest=json.loads((project/'.hyperframes/host-scene-assets.json').read_text())
        assert manifest['audio_duration_seconds']==0 and len(manifest['packets'])==1
    finally:tools.close()


def test_worker_wait_is_cancelable_without_waiting_full_interval(tmp_path):
    from app.integrations.hyperframes.workflow_workers import WorkflowWorkers
    canceled=threading.Event(); release=threading.Event()
    def guard():
        if canceled.is_set(): raise RuntimeError('cancel requested')
    pool=WorkflowWorkers(tmp_path,lambda *a,**k: release.wait(5),guard)
    pool.submit('frame')
    timer=threading.Timer(.1,canceled.set); timer.start()
    start=time.monotonic()
    try:
        import pytest
        with pytest.raises(RuntimeError,match='cancel requested'):pool.poll(wait_seconds=45)
        assert time.monotonic()-start<2
    finally: release.set();timer.cancel();pool.close()


def test_render_uses_configured_workers_and_keeps_native_memory_fallback(tmp_path, monkeypatch):
    tools=WorkflowTools(tmp_path,lambda:None)
    execute=tools.execute
    commands=[]
    def capture(name,args):
        if name=='run_command':
            commands.append(args['command']);return {'command_id':str(len(commands))}
        return execute(name,args)
    tools.execute=capture
    try:
        monkeypatch.setenv('HYPERFRAMES_RENDER_WORKERS','2')
        tools.call('render_project',{'project_directory':str(tmp_path)})
        assert '--workers 2' in commands[-1] and '--no-low-memory-mode' not in commands[-1]
        tools.operations.clear()
        monkeypatch.setenv('HYPERFRAMES_RENDER_WORKERS','1')
        tools.call('render_project',{'project_directory':str(tmp_path)})
        assert '--low-memory-mode' in commands[-1]
    finally:tools.close()
