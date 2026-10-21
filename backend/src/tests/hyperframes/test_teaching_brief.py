import json
from types import SimpleNamespace
import pytest

from app.integrations.hyperframes.teaching_brief import effective_preferences, generate_teaching_brief, validate_brief
from app.integrations.hyperframes.generation import generate_content
from app.integrations.hyperframes.projects import ProjectStore
from app.course_preparation.schemas import PreparationOverrides
from tests.hyperframes.native_workflow_fixtures import Gateway, Checkpoint, Runner, Runtime


def test_explicit_video_preferences_override_legacy_duration_and_false_is_preserved():
    request = {'requested_video_minutes': 8, 'video_preferences': {'target_minutes': 2, 'narration': False}}
    prefs = effective_preferences(request)
    assert prefs['explicit'] == {'target_minutes': 2, 'narration': False}
    assert prefs['defaults']['target_minutes'] == 5
    assert 'video_preferences' not in PreparationOverrides().model_dump()


def test_brief_corrects_only_a_concrete_format_error_once():
    class Recover(Gateway):
        def chat(self, messages, **kwargs):
            if not self.calls:
                self.calls += 1
                return 'invalid json'
            return super().chat(messages, **kwargs)
    gateway = Recover()
    value = generate_teaching_brief({'request': '冒泡排序'}, gateway, guard=lambda: None)
    assert value['calls'] == 2 and gateway.calls == 2


def test_brief_rejects_overwriting_explicit_duration():
    value = json.loads(Gateway().chat([]))
    with pytest.raises(ValueError, match='explicitly configured video duration'):
        validate_brief(value, {'video_preferences': {'target_minutes': 2}})


def test_revision_does_not_expand_existing_video_to_new_default():
    prefs = effective_preferences({'original_content': {'content': {'timeline': {'duration': 120}}}})
    assert prefs['defaults']['target_minutes'] == 2
    assert prefs['defaults']['duration_source'] == 'existing'


def test_brief_is_checkpointed_before_native_failure_and_not_repeated(tmp_path):
    class Interrupted(Runner):
        def run(self, prompt): raise RuntimeError('native interrupted')
    gateway = Gateway(); checkpoint = Checkpoint()
    args = dict(gateway=gateway, artifact={'resource_id': 'r'}, checkpoint=checkpoint,
                store=ProjectStore(tmp_path/'projects'), runtime=Runtime())
    payload = SimpleNamespace(title='教学', focus='完整讲解')
    with pytest.raises(RuntimeError, match='native interrupted'):
        generate_content(payload, runner_factory=Interrupted, **args)
    assert checkpoint.state['state']['teaching_brief']['decisions']['target_minutes'] == 5
    generate_content(payload, runner_factory=Runner, **args)
    assert gateway.calls == 1


def test_cancel_prevents_brief_model_call():
    gateway = Gateway()
    def guard(): raise RuntimeError('CANCELED')
    with pytest.raises(RuntimeError, match='CANCELED'):
        generate_teaching_brief({}, gateway, guard=guard)
    assert gateway.calls == 0


def test_existing_v1_workspace_resumes_without_new_brief(tmp_path):
    import hashlib
    from app.integrations.hyperframes.workflow import legacy_creation_brief
    payload = SimpleNamespace(title='旧课', focus='用户旧要求')
    brief = legacy_creation_brief(payload); brief['assets'] = []
    identity = hashlib.sha256(json.dumps({'brief':brief,'spec':None,'resource_id':'r','media':{},
        'pipeline':'upstream-workflow-v1'},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    project = tmp_path/'workflows'/identity/'videos/existing'
    project.mkdir(parents=True); (project/'BRIEF.md').write_text('existing brief')
    gateway = Gateway()
    generate_content(payload, gateway=gateway, artifact={'resource_id':'r'}, store=ProjectStore(tmp_path/'projects'),
                     runtime=Runtime(), runner_factory=Runner)
    assert gateway.calls == 0


def test_pre_visual_contract_v2_workspace_resumes_its_existing_brief(tmp_path):
    import hashlib
    from app.integrations.hyperframes.workflow import creation_brief
    payload = SimpleNamespace(title='旧版五分钟课', focus='完整讲解')
    brief = creation_brief(payload); brief.pop('course_visual_contract'); brief['assets'] = []
    identity = hashlib.sha256(json.dumps({'brief':brief,'spec':None,'resource_id':'r','media':{},
        'pipeline':'teaching-brief-v2'},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    workspace = tmp_path/'workflows'/identity
    project = workspace/'videos/existing'
    project.mkdir(parents=True); (project/'BRIEF.md').write_text('existing brief')
    checkpoint = Checkpoint()
    checkpoint.state = {'request_digest':identity, 'state':{'teaching_brief':json.loads(Gateway().chat([]))}}
    gateway = Gateway()
    generate_content(payload, gateway=gateway, artifact={'resource_id':'r'}, checkpoint=checkpoint,
        store=ProjectStore(tmp_path/'projects'), runtime=Runtime(), runner_factory=Runner)
    assert gateway.calls == 0
    assert checkpoint.state['request_digest'] == identity
    assert checkpoint.state['state']['runtime']['history'][0]['build_id'] == 'unrecorded'
