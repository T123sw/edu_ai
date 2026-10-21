"""Production now delegates authorship to full upstream workflows."""
from types import SimpleNamespace
import json
import zipfile
import pytest
from app.integrations.hyperframes.generation import generate_content
from app.integrations.hyperframes.projects import ProjectStore
from app.integrations.hyperframes.workflow import creation_brief
from tests.hyperframes.native_workflow_fixtures import Checkpoint, Runner, Runtime, Gateway


def test_brief_carries_user_intent_without_platform_story_or_quiz_policy():
    payload=SimpleNamespace(title='截距',focus='旧平台模板',research_context='SOURCE_SENTINEL',
        classroom_options={'enable_tts':False,'include_visuals':False},
        teaching_context={'request_goal':'只要 40 秒视频，不要题目','resource_target_minutes':2/3,
          'requirements':[{'text':'展示平移'}],'learning_activities':['平台强加测验'],
          'self_check':'平台强加提问','node_budget_minutes':20})
    brief=creation_brief(payload)
    assert brief['request']=='只要 40 秒视频，不要题目'
    assert brief['media_requirements']=={'enable_tts':False,'include_visuals':False}
    assert brief['sources']=='SOURCE_SENTINEL'
    assert brief['requested_video_minutes']==2/3
    assert brief['learning_activities'] == ['平台强加测验']  # Context is retained; explicit no-quiz intent wins in conversion.
    assert brief['node_budget_minutes'] == 20


def test_native_delivery_preserves_upstream_files_and_imports_actual_timeline(tmp_path):
    Runner.calls=[];store=ProjectStore(tmp_path/'projects');checkpoint=Checkpoint()
    result=generate_content(SimpleNamespace(title='截距',focus='用户需求'),gateway=Gateway(),
        artifact={'resource_id':'r1','spec_digest':'spec'},checkpoint=checkpoint,
        store=store,runtime=Runtime(),runner_factory=Runner)
    assert len(Runner.calls)==1
    assert result['timeline']['duration']==2.75
    segment=result['timeline']['segments'][0]
    assert segment['narration']=='完整原生讲稿，不是平台生成的 JSON。'
    assert segment['id']=='01-concept' and segment['start']==0
    assert segment['audio_path']=='assets/voice.mp3'
    with zipfile.ZipFile(store.file(result['project'],'exports/project.zip')) as archive:
        assert {'BRIEF.md','STORYBOARD.md','SCRIPT.md','frame.md','compositions/frames/01-concept.html'}<=set(archive.namelist())


def test_resume_import_does_not_reauthor_or_rerender(tmp_path):
    Runner.calls=[];runtime=Runtime();runtime.fail=True;checkpoint=Checkpoint()
    args=dict(gateway=Gateway(),artifact={'resource_id':'r1'},checkpoint=checkpoint,
        store=ProjectStore(tmp_path/'projects'),runtime=runtime,runner_factory=Runner)
    payload=SimpleNamespace(title='截距',focus='用户需求')
    with pytest.raises(RuntimeError,match='probe interrupted'):generate_content(payload,**args)
    assert checkpoint.state['state']['receipt']
    runtime.fail=False
    result=generate_content(payload,**args)
    assert generate_content(payload,**args)==result
    assert len(Runner.calls)==1


def test_failed_native_worker_keeps_files_and_never_falls_back(tmp_path):
    class Failed(Runner):
        def run(self,prompt):
            (self.workspace/'partial-storyboard.md').write_text('native intermediate')
            raise TimeoutError('native agent interrupted')
    store=ProjectStore(tmp_path/'projects');checkpoint=Checkpoint()
    with pytest.raises(TimeoutError):generate_content(SimpleNamespace(title='T',focus='需求'),gateway=Gateway(),
        artifact={'resource_id':'r'},store=store,checkpoint=checkpoint,runner_factory=Failed)
    assert list((tmp_path/'workflows').glob('*/partial-storyboard.md'))
    assert 'published' not in checkpoint.state['state']
    assert not list(store.root.glob('*'))


def test_changed_request_uses_separate_workspace_and_preserves_previous_project(tmp_path):
    Runner.calls=[];store=ProjectStore(tmp_path/'projects');checkpoint=Checkpoint()
    args=dict(gateway=Gateway(),artifact={'resource_id':'r'},store=store,checkpoint=checkpoint,
        runtime=Runtime(),runner_factory=Runner)
    first=generate_content(SimpleNamespace(title='T',focus='第一次需求'),**args)
    generate_content(SimpleNamespace(title='T',focus='修改需求'),**args)
    assert len(Runner.calls)==2
    assert len(list((tmp_path/'workflows').iterdir()))==2
    assert store.file(first['project'],'SCRIPT.md').is_file()
