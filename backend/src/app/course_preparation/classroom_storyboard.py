"""Bounded preparation storyboard compiled to the existing OpenMAIC player.

Teaching purposes are NOT native scene types. Quiz feedback is rendered only
by QuizScenePlayer after submission; no answer-bearing speech is scheduled.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .schemas import Contract, Identifier

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identity = Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9_:-]{1,160}$')]
SCENE_PURPOSES = {'example', 'explanation', 'demonstration', 'practice', 'feedback'}
MAX_SCENES = 24  # Safety ceiling, not a pedagogical target.


class FlowStep(Contract):
    label: Text = Field(max_length=32)
    detail: Text = Field(max_length=80)
    narration: Text = Field(max_length=1200)


class Choice(Contract):
    value: Identity
    label: Text = Field(max_length=180)


class SceneQuestion(Contract):
    question_id: Identity
    prompt: Text = Field(max_length=600)
    options: tuple[Choice, ...] = Field(min_length=2, max_length=6)
    answer: Identity
    analysis: Text = Field(max_length=2000)

    @model_validator(mode='after')
    def validate_answer(self):
        values = [option.value for option in self.options]
        if len(set(values)) != len(values) or self.answer not in values:
            raise ValueError('Question answer must reference one unique option')
        return self


class StoryboardScene(Contract):
    scene_id: Identity
    objective_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)
    requirement_ids: tuple[Identifier, ...] = Field(default=(), max_length=30)
    purpose: Literal['example', 'explanation', 'demonstration', 'practice', 'feedback']
    title: Text = Field(max_length=40)
    screen: tuple[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)], ...] = Field(min_length=1, max_length=3)
    narration: Text = Field(max_length=2000)
    student_action: Literal['observe', 'answer']
    feedback: Literal['none', 'on_submit']
    estimated_seconds: int = Field(strict=True, ge=5, le=1800)
    steps: tuple[FlowStep, ...] = Field(default=(), max_length=4)
    question: SceneQuestion | None = None

    @model_validator(mode='after')
    def executable_behavior(self):
        if self.question is not None:
            if self.student_action != 'answer' or self.feedback != 'on_submit' or self.steps:
                raise ValueError('Questions require answer/on_submit and cannot have a flow diagram')
            if self.purpose not in ('practice', 'feedback'):
                raise ValueError('A question must have a practice or feedback purpose')
        elif self.student_action != 'observe' or self.feedback != 'none' or self.purpose in ('practice', 'feedback'):
            raise ValueError('Practice and feedback require an executable question')
        if self.question and (self.screen != (self.question.prompt,) or self.narration != self.question.prompt):
            raise ValueError('Quiz screen/narration must repeat only the question prompt')
        if self.steps and len(self.screen) != 1:
            raise ValueError('Flow screen must have exactly one summary')
        if self.steps and len(self.steps) < 2:
            raise ValueError('A flow diagram needs at least two steps')
        return self


class ClassroomStoryboard(Contract):
    scenes: tuple[StoryboardScene, ...] = Field(min_length=1, max_length=MAX_SCENES)
    required_media: tuple[Literal['external_image', 'narration_audio'], ...] = ()

    @model_validator(mode='after')
    def unique_identities(self):
        ids = [s.scene_id for s in self.scenes]
        questions = [s.question.question_id for s in self.scenes if s.question]
        if len(ids) != len(set(ids)) or len(questions) != len(set(questions)):
            raise ValueError('Scene and question identities must be unique')
        return self


def validate_teaching_bindings(board, teaching_context, *, max_scenes=MAX_SCENES):
    if not 1 <= max_scenes <= MAX_SCENES or len(board.scenes) > max_scenes:
        raise ValueError('CLASSROOM_SCENE_LIMIT')
    objectives = set(teaching_context['objective_ids'])
    requirements = {r['requirement_id'] for r in teaching_context.get('requirements', [])}
    for scene in board.scenes:
        if not set(scene.objective_ids) <= objectives:
            raise ValueError('CLASSROOM_UNKNOWN_OBJECTIVE')
        if not set(scene.requirement_ids) <= requirements:
            raise ValueError('CLASSROOM_UNKNOWN_REQUIREMENT')
    if set().union(*(set(s.requirement_ids) for s in board.scenes)) != requirements:
        raise ValueError('CLASSROOM_REQUIREMENT_COVERAGE_INCOMPLETE')
    if set().union(*(set(s.objective_ids) for s in board.scenes)) != objectives:
        raise ValueError('CLASSROOM_OBJECTIVE_COVERAGE_INCOMPLETE')
    if not any(s.steps for s in board.scenes):
        raise ValueError('CLASSROOM_PROCESS_VISUAL_REQUIRED')
    if not any(s.question for s in board.scenes):
        raise ValueError('CLASSROOM_CHECK_REQUIRED')
    # Single-resource target is independent of the whole-node ceiling.
    target = teaching_context.get('resource_target_minutes')
    if target and sum(s.estimated_seconds for s in board.scenes) > target * 60:
        raise ValueError('CLASSROOM_RESOURCE_DURATION_EXCEEDED')


def _text(identity, text, left, top, width, height, size):
    return {'id': identity, 'type': 'text', 'left': left, 'top': top,
            'width': width, 'height': height, 'rotate': 0,
            'content': f'<div style="font-size:{size}px;line-height:1.4">{html.escape(text)}</div>',
            'defaultFontName': 'sans-serif', 'defaultColor': '#172033', 'lineHeight': 1.4}


def _shape(identity, left, top, width, height, *, arrow=False):
    return {'id': identity, 'type': 'shape', 'left': left, 'top': top,
            'width': width, 'height': height, 'rotate': 0, 'fixedRatio': False,
            'viewBox': [100, 100], 'fill': '#2563eb' if arrow else '#eaf2ff',
            'path': 'M0 35 L60 35 L60 0 L100 50 L60 100 L60 65 L0 65 Z' if arrow else 'M0 0 L100 0 L100 100 L0 100 Z'}


def render_storyboard(board, title, resource_id):
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    stage = {'id': resource_id, 'name': title, 'createdAt': now, 'updatedAt': now}
    scenes = []
    for index, plan in enumerate(board.scenes):
        sid = f'{resource_id}:{plan.scene_id}'
        scene = {'id': sid, 'stageId': resource_id, 'title': plan.title, 'order': index,
                 'createdAt': now, 'updatedAt': now}
        if plan.question:
            q = plan.question
            scene.update(type='quiz', content={'type': 'quiz', 'questions': [{
                'id': f'{sid}:{q.question_id}', 'type': 'single', 'question': q.prompt,
                'options': [o.model_dump() for o in q.options], 'answer': [q.answer],
                'analysis': q.analysis, 'required': True, 'points': 1}]})
            # Only the prompt is spoken before submission. Never schedule the
            # model's quiz narration (which can inadvertently contain answers).
            scene['actions'] = [{'id': f'{sid}:speech', 'type': 'speech',
                                 'text': q.prompt + '。请选择答案，提交后查看解析。'}]
        else:
            elements = [_text(f'{sid}:title', plan.title, 50, 25, 900, 95, 34)]
            actions = [{'id': f'{sid}:speech', 'type': 'speech', 'text': plan.narration}]
            if plan.steps:
                elements[0] = _text(f'{sid}:title', plan.title, 50, 10, 900, 42, 30)
                elements.append(_text(f'{sid}:summary', plan.screen[0], 50, 55, 900, 72, 24))
                # Two rows, with enough vertical space for actual text layout.
                for step_index, step in enumerate(plan.steps):
                    row, col = divmod(step_index, 2)
                    x, y = 50 + col * 490, 135 + row * 195
                    eid = f'{sid}:step{step_index + 1}'
                    elements.extend([
                        _shape(eid, x, y, 410, 165),
                        _text(eid + ':label', f'{step_index + 1}. {step.label}', x + 16, y + 8, 378, 60, 26),
                        _text(eid + ':detail', step.detail, x + 16, y + 72, 378, 85, 24),
                    ])
                    if col == 0 and step_index + 1 < len(plan.steps):
                        elements.append(_shape(eid + ':arrow', x + 430, y + 70, 40, 28, arrow=True))
                    if step_index == 1 and len(plan.steps) > 2:
                        elements.append(_text(eid + ':next', '↓ 接第 3 步', x + 245, y + 167, 165, 28, 18))
                    actions.extend([
                        {'id': eid + ':focus', 'type': 'spotlight', 'elementId': eid},
                        {'id': eid + ':speech', 'type': 'speech', 'text': step.narration},
                    ])
            else:
                for i, line in enumerate(plan.screen):
                    elements.append(_text(f'{sid}:point{i + 1}', line, 60, 150 + i * 125, 880, 115, 28))
            scene.update(type='slide', content={'type': 'slide', 'canvas': {
                'id': sid + ':canvas', 'viewportSize': 1000, 'viewportRatio': 0.5625,
                'theme': {'backgroundColor': '#ffffff', 'themeColors': ['#2563eb'],
                          'fontColor': '#172033', 'fontName': 'sans-serif'},
                'background': {'type': 'solid', 'color': '#ffffff'}, 'elements': elements}}, actions=actions)
        scenes.append(scene)
    return {'stage': stage, 'scenes': scenes}


def storyboard_metadata(board, content):
    bindings, requirements, plans, questions = [], [], [], []
    for plan, scene in zip(board.scenes, content['scenes'], strict=True):
        locator = {'scene_id': scene['id']}
        if plan.question:
            questions.append({'scene_id': scene['id'], 'question_id': scene['content']['questions'][0]['id'],
                              'objective_ids': list(plan.objective_ids)})
        else:
            locator['action_id'] = scene['actions'][0]['id']
        role = 'check' if plan.question else 'explanation'
        bindings.extend({'objective_id': oid, 'locator': locator, 'role': role} for oid in plan.objective_ids)
        requirements.extend({'requirement_id': rid, 'locator': locator,
                             'explanation': f'候选落实位置：{plan.title}；需独立审阅确认语义'} for rid in plan.requirement_ids)
        plans.append({'scene_id': scene['id'], 'purpose': plan.purpose,
                      'student_action': plan.student_action, 'feedback': plan.feedback,
                      'estimated_seconds': plan.estimated_seconds})
    return {'objective_bindings': bindings, 'applied_requirements': requirements,
            'scene_plans': plans, 'question_bindings': questions, 'duration': {
                'value_minutes': round(sum(s.estimated_seconds for s in board.scenes) / 60, 2),
                'basis': 'estimated', 'method': 'sum_storyboard_learning_seconds_including_answer_time'},
            'media_duration': {'value_minutes': None, 'basis': 'unknown',
                               'method': 'no_verified_audio_duration'}}
