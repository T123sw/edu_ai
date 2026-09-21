"""Preparation-specific renderer and phase/checkpoint contracts (no live model)."""
import copy
import json
from types import SimpleNamespace

import pytest

from app.course_preparation.adapters import classroom
from app.course_preparation.classroom_storyboard import (
    ClassroomStoryboard, render_storyboard, storyboard_metadata, validate_teaching_bindings,
)
from app.course_preparation.classroom_render_checks import ClassroomFailure, require_renderable
from app.course_preparation.tool_registry import digest


def teaching_context():
    return {'objective_ids': ['n1:o1'], 'requirements': [{'requirement_id': 'r1', 'text': '先例后理'}],
            'node_budget_minutes': 10, 'resource_target_minutes': None,
            'learning_activities': ['追踪调用并核对回执'], 'prior_knowledge': '认识加法',
            'prerequisites': [], 'effective_preferences': {'style': '简洁'}}


def board_data():
    common = {'objective_ids': ['n1:o1'], 'requirement_ids': ['r1'],
              'student_action': 'observe', 'feedback': 'none', 'estimated_seconds': 60}
    return {'scenes': [
        {**common, 'scene_id': 'example', 'purpose': 'example', 'title': '追踪一次加法',
         'screen': ['从参数到真实结果'], 'narration': '先观察 add 的实际请求与执行结果。',
         'steps': [{'label': '请求', 'detail': 'add(a=12,b=30)', 'narration': '模型提出 add，请求参数是十二和三十。'},
                   {'label': '校验和执行', 'detail': '12 + 30 = 42', 'narration': '程序校验数字后求和，得到四十二。'},
                   {'label': '回传', 'detail': 'result: 42', 'narration': '把真实结果四十二交回模型。'},
                   {'label': '回答', 'detail': '结果为 42', 'narration': '模型依据回执回答四十二。'}]},
        {**common, 'scene_id': 'principle', 'purpose': 'explanation', 'title': '职责分工',
         'screen': ['模型选择工具', '程序校验和执行'], 'narration': '再归纳原理：模型提出调用，程序负责执行。'},
        {**common, 'scene_id': 'check', 'purpose': 'practice', 'title': '检查理解',
         'screen': ['add 缺少 b 时应怎样处理？'], 'narration': 'add 缺少 b 时应怎样处理？',
         'student_action': 'answer', 'feedback': 'on_submit', 'estimated_seconds': 90,
         'question': {'question_id': 'q1', 'prompt': 'add 缺少 b 时应怎样处理？',
                      'options': [{'value': 'A', 'label': '直接求和'}, {'value': 'B', 'label': '返回参数缺失错误'}],
                      'answer': 'B', 'analysis': '缺少参数时不能执行工具，应返回参数缺失错误。'}}]}


def test_example_order_changes_actual_screen_and_speech_order():
    board = ClassroomStoryboard.model_validate(board_data())
    validate_teaching_bindings(board, teaching_context())
    content = render_storyboard(board, '课堂', 'resource-1')
    assert [s['id'] for s in content['scenes']][:2] == ['resource-1:example', 'resource-1:principle']
    assert content['scenes'][0]['actions'][0]['text'].startswith('先观察')
    swapped = board.model_copy(update={'scenes': (board.scenes[1], board.scenes[0], board.scenes[2])})
    reversed_content = render_storyboard(swapped, '课堂', 'resource-1')
    assert reversed_content['scenes'][0]['actions'][0]['text'].startswith('再归纳')
    assert require_renderable(content)['passed']


def test_quiz_answers_have_only_submit_feedback_and_flow_has_real_targets():
    board = ClassroomStoryboard.model_validate(board_data())
    content = render_storyboard(board, '课堂', 'r')
    quiz = content['scenes'][-1]
    assert quiz['type'] == quiz['content']['type'] == 'quiz'
    assert quiz['content']['questions'][0]['answer'] == ['B']
    assert '缺少参数时不能执行' not in json.dumps(quiz['actions'], ensure_ascii=False)
    flow = content['scenes'][0]
    targets = {e['id'] for e in flow['content']['canvas']['elements'] if e['type'] == 'shape'}
    assert len([a for a in flow['actions'] if a['type'] == 'spotlight' and a['elementId'] in targets]) == 4
    assert len([e for e in flow['content']['canvas']['elements'] if e['type'] == 'shape']) > 4
    meta = storyboard_metadata(board, content)
    assert meta['duration']['value_minutes'] == 3.5
    assert meta['duration']['basis'] == 'estimated'
    assert meta['media_duration']['basis'] == 'unknown'
    assert meta['question_bindings'][-1]['question_id'] == 'r:check:q1'


@pytest.mark.parametrize('change', ['answer', 'objective', 'purpose', 'duplicate', 'leak'])
def test_invalid_semantics_are_rejected(change):
    data = board_data()
    if change == 'answer': data['scenes'][-1]['question']['answer'] = 'C'
    if change == 'objective': data['scenes'][0]['objective_ids'] = ['other:o1']
    if change == 'purpose': data['scenes'][0]['purpose'] = 'slide'
    if change == 'duplicate': data['scenes'][1]['scene_id'] = 'example'
    if change == 'leak': data['scenes'][-1]['narration'] += '答案是 B。'
    with pytest.raises(ValueError):
        validate_teaching_bindings(ClassroomStoryboard.model_validate(data), teaching_context())


def test_more_than_six_scenes_is_not_rejected_and_node_budget_is_not_resource_target():
    data = board_data()
    for i in range(6):
        scene = copy.deepcopy(data['scenes'][1]); scene['scene_id'] = f'extra{i}'; scene['estimated_seconds'] = 120
        data['scenes'].insert(-1, scene)
    board = ClassroomStoryboard.model_validate(data)
    validate_teaching_bindings(board, teaching_context())
    with pytest.raises(ValueError, match='RESOURCE_DURATION'):
        validate_teaching_bindings(board, {**teaching_context(), 'resource_target_minutes': 1})
    with pytest.raises(ValueError, match='SCENE_LIMIT'):
        validate_teaching_bindings(board, teaching_context(), max_scenes=8)


class Gateway:
    def __init__(self, raw=None):
        self.calls = []; self.phases = []; self.raw = raw or board_data()
    def chat(self, messages, **kwargs):
        self.calls.append(messages)
        request = json.loads(messages[-1]['content'])
        if 'preparation' in request:
            checks = [{'binding_index': item['binding_index'],
                       'passed': True, 'reason': '测试替身确认具体教学位置'}
                      for key, collection in [('requirement_id', 'applied_requirements'), ('objective_id', 'objective_bindings')]
                      for item in request['preparation'][collection]]
            return json.dumps({'preparation_checks': checks}, ensure_ascii=False)
        return json.dumps(self.raw, ensure_ascii=False)


class Checkpoint:
    def __init__(self): self.candidate = None
    def load_review_candidate(self): return copy.deepcopy(self.candidate)
    def save_review_candidate(self, **candidate): self.candidate = copy.deepcopy(candidate)


def passed_audit(content):
    from app.chat.harness.reviewed_report import CRITERIA
    from app.chat.harness.reviewed_resource import digest as content_digest
    return {'decision': 'pass', 'method': 'model_review', 'resource_type': 'classroom',
            'content_sha256': content_digest('classroom', content),
            'checks': [{'criterion': c, 'passed': True} for c in CRITERIA],
            'scene_checks': [{'scene_index': i, 'screen_reasoning': '测试替身逐页回执', 'screen_passed': True,
                'speech_checks': [{'action_index': j, 'reasoning': '测试替身逐句回执', 'passed': True}
                                  for j, a in enumerate(s['actions']) if a['type'] == 'speech']}
                             for i, s in enumerate(content['scenes'])]}


@pytest.fixture
def generation(monkeypatch):
    import app.chat.harness.reviewed_resource as review_module
    gateway = Gateway()
    def scoped(g, phase, context):
        g.phases.append((phase, context)); return g
    monkeypatch.setattr(classroom, '_phase_gateway', scoped)
    def review(content, config, gateway=None, checkpoint=None):
        assert config['teaching_context']['learning_activities']
        assert gateway is not None
        return content, passed_audit(content)
    monkeypatch.setattr(review_module, 'review_classroom', review)
    payload = SimpleNamespace(title='课堂', focus='', research_context='授权证据', teaching_context=teaching_context())
    args = {'payload': payload, 'gateway': gateway, 'context': None,
            'artifact': {'resource_id': 'r', 'spec_digest': 'spec-1', 'artifact_id': 'a1', 'spec': {'schema_version': 2}}}
    return args, review_module


def test_generation_context_reaches_writer_reviewer_and_bound_output(generation):
    args, _ = generation
    result = classroom.generate_classroom_draft(**args)
    request = json.loads(args['gateway'].calls[0][-1]['content'])
    assert request['teaching_context'] == teaching_context()
    assert args['gateway'].phases[0][0] == 'classroom_write'
    meta = result['generation_state']['preparation']
    assert meta['spec_digest'] == 'spec-1'
    assert meta['teaching_context_digest'] == digest(teaching_context())
    assert meta['render_checks']['passed'] and meta['render_checks']['browser_layout'] == 'not_checked'


def test_review_format_failure_resumes_same_content_without_rewriting(generation, monkeypatch):
    args, review_module = generation
    checkpoint = Checkpoint(); seen = []
    def review(content, config, gateway=None, checkpoint=None):
        seen.append(digest(content))
        checkpoint.save_review_candidate(content=content, content_digest=digest(content),
            spec_digest='spec-1', review_state={'attempt': len(seen)})
        if len(seen) == 1: raise ValueError('review_format')
        return content, passed_audit(content)
    monkeypatch.setattr(review_module, 'review_classroom', review)
    with pytest.raises(ValueError, match='review_format'):
        classroom.generate_classroom_draft(**args, checkpoint=checkpoint)
    assert checkpoint.candidate['review_state']['storyboard']
    classroom.generate_classroom_draft(**args, checkpoint=checkpoint)
    assert len(args['gateway'].calls) == 2 and seen[0] == seen[1]


@pytest.mark.parametrize('field', ['spec_digest', 'content_digest', 'teaching_context_digest'])
def test_stale_checkpoint_fails_closed(generation, field):
    args, _ = generation; checkpoint = Checkpoint()
    classroom.generate_classroom_draft(**args, checkpoint=checkpoint)
    target = checkpoint.candidate['review_state'] if field == 'teaching_context_digest' else checkpoint.candidate
    target[field] = 'tampered'
    with pytest.raises(ClassroomFailure) as failure:
        classroom.generate_classroom_draft(**args, checkpoint=checkpoint)
    assert failure.value.code == 'CLASSROOM_CHECKPOINT_STALE'


@pytest.mark.parametrize('media', ['external_image', 'narration_audio'])
def test_required_media_cannot_silently_degrade(generation, media):
    args, _ = generation
    args['gateway'].raw['required_media'] = [media]
    with pytest.raises(ClassroomFailure) as failure:
        classroom.generate_classroom_draft(**args)
    assert failure.value.code == 'CLASSROOM_REQUIRED_MEDIA_UNAVAILABLE'
    detail = failure.value.detail
    if hasattr(detail, 'model_dump'): detail = detail.model_dump()
    assert detail['category'] == 'provider'


def test_canceled_during_slow_writer_does_not_save_or_review(generation):
    args, _ = generation; canceled = False; checkpoint = Checkpoint()
    original = args['gateway'].chat
    def slow(*a, **k):
        nonlocal canceled
        canceled = True
        return original(*a, **k)
    args['gateway'].chat = slow
    args['context'] = SimpleNamespace(is_cancel_requested=lambda: canceled)
    with pytest.raises(ClassroomFailure) as failure:
        classroom.generate_classroom_draft(**args, checkpoint=checkpoint)
    assert failure.value.code == 'CANCELED' and checkpoint.candidate is None


def test_missing_structured_context_never_calls_writer(generation):
    args, _ = generation; args['payload'].teaching_context = None
    with pytest.raises(ClassroomFailure, match='结构化'):
        classroom.generate_classroom_draft(**args)
    assert not args['gateway'].calls


def test_reviewer_mutation_invalidates_estimate_and_requires_fresh_digest(generation, monkeypatch):
    args, review_module = generation
    def review(content, config, gateway=None, checkpoint=None):
        content['scenes'][0]['actions'][0]['text'] += '现在补充一个条件。'
        return content, passed_audit(content)
    monkeypatch.setattr(review_module, 'review_classroom', review)
    result = classroom.generate_classroom_draft(**args)
    assert result['generation_state']['preparation']['duration']['basis'] == 'unknown'


def test_unreviewed_candidate_cannot_be_returned(generation, monkeypatch):
    args, review_module = generation
    def review(content, config, gateway=None, checkpoint=None):
        return content, {'decision': 'pass'}
    monkeypatch.setattr(review_module, 'review_classroom', review)
    with pytest.raises(ClassroomFailure) as failure:
        classroom.generate_classroom_draft(**args)
    assert failure.value.code == 'CLASSROOM_REVIEW_STALE'


def test_review_resume_preserves_inner_attempt_history(generation, monkeypatch):
    args, review_module = generation; port = Checkpoint(); calls = []
    def review(content, config, gateway=None, checkpoint=None):
        state = checkpoint.load_review_candidate()['review_state']
        calls.append(state)
        if not state:
            checkpoint.save_review_candidate(content=content, content_digest=digest(content),
                spec_digest='spec-1', review_state={'version': 3, 'history': ['earlier attempts']})
            raise ValueError('review_format')
        return content, passed_audit(content)
    monkeypatch.setattr(review_module, 'review_classroom', review)
    with pytest.raises(ValueError): classroom.generate_classroom_draft(**args, checkpoint=port)
    classroom.generate_classroom_draft(**args, checkpoint=port)
    assert calls[-1]['version'] == 3


def test_gateway_timeout_is_propagated_without_saving_candidate(generation):
    args, _ = generation; port = Checkpoint()
    def timeout(*a, **k): raise TimeoutError('model timeout')
    args['gateway'].chat = timeout
    with pytest.raises(TimeoutError):
        classroom.generate_classroom_draft(**args, checkpoint=port)
    assert port.candidate is None


def test_structural_repair_rebuilds_only_broken_scene_then_reviews_again(generation, monkeypatch):
    args, review_module = generation; seen = []
    def review(content, config, gateway=None, checkpoint=None):
        seen.append(copy.deepcopy(content))
        result = copy.deepcopy(content)
        if len(seen) == 1:
            result['scenes'][0]['content']['canvas']['elements'][0]['left'] = 999
        return result, passed_audit(result)
    monkeypatch.setattr(review_module, 'review_classroom', review)
    calls = 0
    def chat(messages, **kwargs):
        nonlocal calls
        if 'preparation' in json.loads(messages[-1]['content']):
            return Gateway().chat(messages, **kwargs)
        calls += 1
        data = board_data()
        if calls == 2: data['scenes'] = data['scenes'][:1]
        return json.dumps(data, ensure_ascii=False)
    args['gateway'].chat = chat
    result = classroom.generate_classroom_draft(**args)
    assert len(seen) == 2
    assert seen[0]['scenes'][1:] == seen[1]['scenes'][1:]
    assert result['generation_state']['preparation']['render_checks']['passed']
    assert [p[0] for p in args['gateway'].phases] == ['classroom_write', 'classroom_repair', 'resource_review']


def test_v1_checkpoint_keeps_legacy_resource_without_inventing_teaching_context(generation, monkeypatch):
    args, review_module = generation
    args['payload'].teaching_context = None
    args['artifact']['spec'] = {}  # Missing schema_version is historical v1.
    port = Checkpoint()
    script = classroom.TeachingScript(slides=[{'title': '旧课堂', 'points': ['旧内容保留'],
        'narration': '旧任务按原规格恢复，不重算摘要。' * 8}] * 2)
    old = classroom.native_classroom(script, '旧资源', 'r')
    port.save_review_candidate(content=old, content_digest=digest(old), spec_digest='spec-1', review_state={})
    def review(content, config, gateway=None, checkpoint=None): return content, passed_audit(content)
    monkeypatch.setattr(review_module, 'review_classroom', review)
    result = classroom.generate_classroom_draft(**args, checkpoint=port)
    assert result['content'] == old and not args['gateway'].calls
    assert 'preparation' not in result['generation_state']


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'unknown', 'boolean', 'rejected'])
def test_binding_review_does_not_accept_missing_or_semantically_rejected_bindings(generation, fault):
    args, _ = generation; original = args['gateway'].chat
    def chat(messages, **kwargs):
        request = json.loads(messages[-1]['content'])
        if 'failed_bindings' in request:
            return json.dumps({'repairs': [{'binding_type': c['binding_type'], 'binding_id': c['binding_id'],
                'original_locator': c['locator'], 'locator': c['locator']} for c in request['failed_bindings']]})
        result = json.loads(original(messages, **kwargs))
        if 'preparation_checks' in result:
            if fault == 'missing': result['preparation_checks'].pop()
            elif fault == 'duplicate': result['preparation_checks'][1]['binding_index'] = result['preparation_checks'][0]['binding_index']
            elif fault == 'unknown': result['preparation_checks'][0]['binding_index'] = 999
            elif fault == 'boolean': result['preparation_checks'][0]['binding_index'] = True
            else: result['preparation_checks'][0]['passed'] = False
        return json.dumps(result, ensure_ascii=False)
    args['gateway'].chat = chat
    with pytest.raises(ClassroomFailure) as failure:
        classroom.generate_classroom_draft(**args)
    assert failure.value.code == ('CLASSROOM_BINDING_REJECTED' if fault == 'rejected' else 'CLASSROOM_BINDING_REVIEW_INVALID')


def test_indexed_binding_review_restores_original_locations_without_mutating_metadata():
    board = ClassroomStoryboard.model_validate(board_data())
    content = render_storyboard(board, '课堂', 'long-resource-id')
    metadata = storyboard_metadata(board, content)
    original = copy.deepcopy(metadata)
    class ReverseGateway(Gateway):
        def chat(self, messages, **kwargs):
            result = json.loads(super().chat(messages, **kwargs))
            result['preparation_checks'].reverse()
            return json.dumps(result)
    checks = classroom._review_bindings(content, metadata, teaching_context(), gateway=ReverseGateway(), context=None)
    expected = [(key, item[key], item['locator']) for key, collection in
                [('requirement_id', 'applied_requirements'), ('objective_id', 'objective_bindings')]
                for item in metadata[collection]]
    assert [(c['binding_type'], c['binding_id'], c['locator']) for c in checks] == list(reversed(expected))
    assert metadata == original


def test_classroom_duration_feedback_identifies_actual_seconds_and_required_reduction():
    board = ClassroomStoryboard.model_validate(board_data())
    with pytest.raises(ValueError) as error:
        validate_teaching_bindings(board, {**teaching_context(), 'resource_target_minutes': 2.5})
    message = str(error.value)
    assert 'estimated_seconds=210' in message
    assert 'maximum_seconds=150' in message
    assert 'reduce_seconds=60' in message


def test_classroom_keeps_actual_duration_after_bounded_provisional_target_attempts(generation):
    args, _ = generation
    args['payload'].teaching_context['resource_repair_target_minutes'] = 2.5
    result = classroom.generate_classroom_draft(**args)
    writing = [json.loads(messages[-1]['content']) for messages in args['gateway'].calls
               if 'maximum_total_seconds' in json.loads(messages[-1]['content'])]
    assert len(writing) == 3
    assert result['generation_state']['preparation']['duration']['value_minutes'] == 3.5
    # An explicit resource maximum is still enforced on the final attempt.
    args['payload'].teaching_context['resource_target_minutes'] = 2.5
    with pytest.raises(ClassroomFailure, match='CLASSROOM_RESOURCE_DURATION_EXCEEDED'):
        classroom.generate_classroom_draft(**args)
