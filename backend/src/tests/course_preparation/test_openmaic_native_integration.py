"""Historical OpenMAIC record validators and generic private checkpoint fencing.
Active native runtime generation is covered by test_hyperframes_preparation.py."""

import pytest

from app.course_preparation.adapters import openmaic_native
from app.course_preparation.native_render_checks import check_native_render


def native_scene(kind, content, actions=None):
    return {'stage': {'id': 'r'}, 'scenes': [{'id': 's', 'stageId': 'r', 'type': kind, 'order': 0,
        'content': {'type': kind, **content}, 'actions': actions or [{'id': 'a', 'type': 'speech', 'text': '讲解'}]}]}


def test_native_interactive_and_quiz_types_are_enabled_but_discussion_is_rejected():
    interactive = native_scene('interactive', {'html': '<button onclick="this.textContent=2">1</button>'})
    assert check_native_render(interactive)['passed']
    interactive['scenes'][0]['actions'].append({'id': 'd', 'type': 'discussion'})
    assert not check_native_render(interactive)['passed']
    quiz = native_scene('quiz', {'questions': [{'id': 'q', 'type': 'multiple', 'question': '选偶数',
        'options': [{'value': 'A', 'label': '2'}, {'value': 'B', 'label': '4'}], 'answer': ['A', 'B'], 'analysis': '都能被2整除'}]})
    quiz['scenes'][0]['actions'][0]['text'] = '选偶数'
    assert check_native_render(quiz)['passed']
    quiz['scenes'][0]['content']['questions'][0]['answer'] = ['X']
    assert not check_native_render(quiz)['passed']
    assert not check_native_render(native_scene('pbl', {}))['passed']


def test_embedded_media_does_not_bloat_model_context():
    assert openmaic_native.model_view({'src': 'data:image/png;base64,YQ=='})['src'].startswith('[embedded media sha256=')


def test_native_generation_checkpoint_is_private_and_lease_fenced(generation):
    from tests.course_preparation.test_generation_adapter import submit
    from app.course_preparation.lifecycle_repository import StaleLease
    from app.course_preparation.tool_registry import digest
    repo, parent, adapter = generation
    _, receipt = submit(generation)
    child = adapter.artifacts.claim('alice', receipt['artifact_id'])
    port = adapter.artifacts.checkpoint_port(child)
    state = {'request_digest': 'request', 'state': {'plan': {'segments': [{'id': 's1'}]}, 'audio': {}}}
    port.save_generation_state(state)
    assert port.load_generation_state() == state
    assert port.load_review_candidate() is None
    state['state']['plan']['segments'].clear()
    assert port.load_generation_state()['state']['plan']['segments']
    body = {'stage': {'id': 'r'}, 'scenes': []}
    port.save_review_candidate(content=body, content_digest=digest(body), spec_digest=child['spec_digest'], review_state={})
    assert port.load_generation_state() is None
    assert port.load_review_candidate()['content'] == body
    repo.cancel('alice', parent.preparation_id)
    with pytest.raises(StaleLease): port.save_generation_state(state)


from tests.course_preparation.test_generation_adapter import generation


def test_missing_interactive_python_runtime_cannot_pass_static_acceptance():
    content = native_scene('interactive', {'html': '<script>loadPyodide();</script>'})
    report = check_native_render(content)
    assert not report['passed']
    assert 'runtime loader missing' in report['issues'][0]


def test_review_tool_schema_binds_interleaved_speech_to_actual_action_indexes():
    from jsonschema import Draft202012Validator
    from app.chat.harness.reviewed_resource import _classroom_review_schema
    from tests.course_preparation.test_classroom_teaching_contract import passed_audit
    content = native_scene('interactive', {'html': '<button>观察</button>'}, [
        {'id': 'widget', 'type': 'widget_reveal', 'selector': '#hint'},
        {'id': 'speech', 'type': 'speech', 'text': '观察变化'}])
    audit = passed_audit(content)
    review = {'checks': [{**c, 'reason': '逐项独立核验'} for c in audit['checks']],
              'scene_checks': audit['scene_checks'], 'blocking_issues': [], 'suggestions': []}
    validator = Draft202012Validator(_classroom_review_schema(content))
    validator.validate(review)
    review['scene_checks'][0]['speech_checks'][0]['action_index'] = 0
    assert list(validator.iter_errors(review)), 'speech ordinal must not replace its actual action index'
