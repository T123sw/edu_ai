from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
import json
from pathlib import Path
import subprocess
import time

import pytest

from app.integrations.hyperframes.runtime import UPSTREAM
from app.integrations.hyperframes.workflow_agent import WorkflowTools
from app.integrations.hyperframes.workflow_audio import audio_provider


def finish(tools, result):
    until=time.monotonic()+30
    while result.get('exit_code') is None and time.monotonic()<until:
        time.sleep(.2)
        result=tools.call('poll_command',{'command_id':result['command_id']})
    assert result['exit_code']==0,result
    return result


def test_async_command_survives_http_request_thread_and_is_scoped(tmp_path):
    tools=WorkflowTools(tmp_path,lambda:None)
    try:
        with ThreadPoolExecutor(max_workers=1) as request:
            result=request.submit(tools.call,'run_command',{'command':'sleep .4; node -e "console.log(123)"'}).result()
        result=finish(tools,result)
        assert '123' in result['output']
        assert not tools.call('read_file',{'path':'/etc/passwd'})['ok']
        assert not tools.call('write_file',{'path':str(UPSTREAM/'README.md'),'content':'changed'})['ok']
    finally:tools.close()


@pytest.mark.parametrize('override,expected', [(None, 'true'), ('false', 'false')])
def test_native_render_scheduling_reaches_sandbox_and_can_be_disabled(tmp_path, monkeypatch, override, expected):
    monkeypatch.delenv('HF_CAPTURE_PARALLEL_STREAM', raising=False)
    if override is not None:
        monkeypatch.setenv('HF_CAPTURE_PARALLEL_STREAM', override)
    tools = WorkflowTools(tmp_path, lambda: None)
    try:
        result = finish(tools, tools.call('run_command', {
            'command': "node -e 'console.log(process.env.HF_CAPTURE_PARALLEL_STREAM)'"}))
        assert result['output'].strip() == expected
    finally:
        tools.close()


def test_unmodified_native_audio_adapter_uses_host_voice_and_syncs_duration(tmp_path):
    # Use a long path to also exercise AF_UNIX's short-address host bridge.
    workspace=tmp_path/('persistent-project-'+'a'*80);workspace.mkdir()
    project=workspace/'video';project.mkdir()
    (project/'SCRIPT.md').write_text('## Opening (Frame 1)\n\n    中文讲稿由原生工作流编写。\n')
    (project/'STORYBOARD.md').write_text('---\nformat: 1920x1080\nmusic: none\n---\n## Frame 1 — Opening\n- duration: 10s\n- src: compositions/frames/01-opening.html\n- status: outline\n')
    source=workspace/'fixture.mp3'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=0.3',str(source)],check=True)
    spoken=[]
    configuration=ContextVar('speech-config');configuration.set('selected-user-provider')
    def voice(text,cache,options):
        assert configuration.get()=='selected-user-provider'
        spoken.append(text)
        return source
    tools=WorkflowTools(workspace,lambda:None)
    try:
        with audio_provider(workspace,guard=lambda:None,options={},narrate=voice):
            script=UPSTREAM/'skills/faceless-explainer/scripts/audio.mjs'
            result=tools.call('run_command',{'command':f'cd "{project}" && node "{script}" --script SCRIPT.md --storyboard STORYBOARD.md --hyperframes . --out audio_meta.json'})
            finish(tools,result)
            meta=json.loads((project/'audio_meta.json').read_text())
            assert len(meta['voices'])==1 and meta['voices'][0]['frame']==1
            assert .25<meta['voices'][0]['duration_s']<.5
            assert (project/meta['voices'][0]['path']).is_file()
            finish(tools,tools.call('run_command',{'command':f'cd "{project}" && node "{script}" sync-durations --audio-meta audio_meta.json --storyboard STORYBOARD.md'}))
            assert 'duration: 10s' not in (project/'STORYBOARD.md').read_text()
            assert spoken==['中文讲稿由原生工作流编写。']
    finally:tools.close()


def test_course_nodes_keep_required_report_quiz_bundle_with_optional_video():
    from app.course_preparation.resource_selection import course_resource_types
    from app.course_preparation.schemas import PreparationRequest
    from uuid import uuid4
    request=PreparationRequest(request_id=uuid4(),operation='create_course',goal='只生成视频',overrides={'include_classroom':True})
    assert course_resource_types(request)==['report','quiz','classroom']
    assert course_resource_types(request,['classroom'])==['report','quiz','classroom']
    explicit=request.model_copy(update={'overrides':request.overrides.model_copy(update={'required_resource_types':('quiz',)})})
    assert course_resource_types(explicit)==['report','quiz','classroom']


def test_native_temporary_files_survive_separate_commands_without_host_tmp_access(tmp_path):
    tools=WorkflowTools(tmp_path,lambda:None)
    try:
        finish(tools,tools.call('run_command',{'command':"printf 'native snapshot' > /tmp/native-output.txt"}))
        result=finish(tools,tools.call('run_command',{'command':'cat /tmp/native-output.txt'}))
        assert result['output']=='native snapshot'
        assert tools.call('read_file',{'path':'/tmp/native-output.txt'})['content']=='native snapshot'
        assert not tools.call('read_file',{'path':'/tmp/../../etc/passwd'})['ok']
    finally:tools.close()
