"""Historical storyboard renderer contracts and shared legacy test fixtures.
Active generation/recovery coverage lives in test_hyperframes_preparation.py."""
import copy
import json

import pytest

from app.course_preparation.classroom_storyboard import (
    ClassroomStoryboard, render_storyboard, storyboard_metadata, validate_teaching_bindings,
)
from app.course_preparation.classroom_render_checks import require_renderable


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
    validate_teaching_bindings(board, {**teaching_context(), 'resource_target_minutes': 1})
    with pytest.raises(ValueError, match='SCENE_LIMIT'):
        validate_teaching_bindings(board, teaching_context(), max_scenes=8)


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


def test_classroom_learning_target_does_not_reject_or_change_estimate():
    board = ClassroomStoryboard.model_validate(board_data())
    validate_teaching_bindings(board, {**teaching_context(), 'resource_target_minutes': 2.5})
    assert sum(scene.estimated_seconds for scene in board.scenes) == 210
