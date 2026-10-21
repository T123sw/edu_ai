from __future__ import annotations

import hashlib
import json
import math
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

PROTOCOL = 'edu-experiment/1'
Phase = Literal['demonstrate', 'guided', 'explore']

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_default=True)

class Parameter(Contract):
    name: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_]*$')
    label: str = Field(min_length=1)
    type: Literal['number', 'integer', 'string', 'boolean']
    default: JsonValue
    minimum: float | None = None
    maximum: float | None = None
    options: list[JsonValue] = Field(default_factory=list)

class Action(Contract):
    id: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$')
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    phases: list[Phase] = Field(min_length=1)
    parameters: list[Parameter] = Field(default_factory=list)

class Command(Contract):
    action: str
    input: dict[str, JsonValue] = Field(default_factory=dict)

ConditionPath = Annotated[list[str | int], Field(
    min_length=1,
    description='首段必须是 after、before 或 input，例如 ["after", "comparisons"]；不能只写状态字段名',
    json_schema_extra={'prefixItems': [{'type': 'string', 'enum': ['before', 'after', 'input']}]},
)]

class Condition(Contract):
    path: ConditionPath
    op: Literal['eq', 'ne', 'lt', 'lte', 'gt', 'gte', 'contains', 'near']
    value: JsonValue = None
    right_path: ConditionPath | None = None
    tolerance: float = Field(default=0, ge=0)

    @field_validator('path', 'right_path')
    @classmethod
    def valid_path(cls, path):
        if path is not None:
            if path[0] not in ['before', 'after', 'input']:
                raise ValueError('判定路径首段必须为 before、after 或 input；检查操作后状态请写 ["after", "字段名"]')
            if any(x in ['__proto__', 'prototype', 'constructor'] for x in path):
                raise ValueError('判定路径含禁止访问的属性')
        return path

class DemoStep(Contract):
    id: str
    title: str
    before: str
    after: str
    commands: list[Command] = Field(description='初始状态观察步骤可以为空数组；实际操作步骤必须列出真实动作')
    assertions: list[Condition] = Field(min_length=1)

class Task(Contract):
    id: str
    title: str
    objective: str
    prompt: str
    checkpoint: str | None = None
    allowed_actions: list[str] = Field(min_length=1)
    submission: Literal['on_action', 'explicit_submit']
    submit_action: str | None = None
    assessment: Literal['deterministic', 'rubric'] = 'deterministic'
    checks: list[Condition] = Field(default_factory=list)
    rubric: list[str] = Field(default_factory=list)
    success: str
    retry: str
    recovery: Literal['rollback', 'keep'] = 'rollback'
    hints: list[str] = Field(min_length=1)

class ActionSubmissionTask(Task):
    submission: Literal['on_action'] = 'on_action'
    submit_action: str = Field(min_length=1, description='触发本次尝试判定的动作 ID，必须属于 allowed_actions')

class ExplicitSubmissionTask(Task):
    submission: Literal['explicit_submit'] = 'explicit_submit'
    submit_action: None = Field(default=None, description='手动提交由宿主按钮完成，此字段必须为 null 或省略')

TaskDefinition = Annotated[ActionSubmissionTask | ExplicitSubmissionTask, Field(discriminator='submission')]

class StateField(Contract):
    path: list[str | int] = Field(min_length=1)
    label: str
    description: str
    unit: str = ''

class ScientificModel(Contract):
    assumptions: list[str] = Field(min_length=1)
    rules: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)

class TeachingContext(Contract):
    background: str
    misconceptions: list[str]

class ValidationCase(Contract):
    id: str
    task_id: str
    commands: list[Command] = Field(min_length=1)
    expected: Literal['pass', 'fail', 'awaiting_review']
    assertions: list[Condition] = Field(default_factory=list)

class ExperimentSpec(Contract):
    protocol: Literal['edu-experiment/1'] = PROTOCOL
    title: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    overview: str = Field(min_length=1)
    objectives: list[str] = Field(min_length=1)
    scientific_model: ScientificModel
    state_fields: list[StateField] = Field(min_length=1)
    actions: list[Action] = Field(min_length=1)
    checkpoints: dict[str, dict[str, JsonValue]]
    demo_checkpoint: str
    demo_steps: list[DemoStep] = Field(min_length=1, max_length=16)
    guided_checkpoint: str
    tasks: list[TaskDefinition] = Field(min_length=1, max_length=8)
    explore_checkpoint: str
    exploration_prompts: list[str] = Field(min_length=1)
    teaching_context: TeachingContext
    validation_cases: list[ValidationCase] = Field(min_length=1, max_length=24)

    @model_validator(mode='after')
    def references(self):
        def unique(items):
            if len(items) != len(set(items)): raise ValueError('重复标识')
        unique([a.id for a in self.actions]); unique([s.id for s in self.demo_steps]); unique([t.id for t in self.tasks]); unique([v.id for v in self.validation_cases])
        for t in self.tasks[:-1]:
            if t.assessment == 'rubric': raise ValueError('教学评价未接入，开放评价只能放在最后一个任务')
        for a in self.actions:
            unique([p.name for p in a.parameters])
            for p in a.parameters:
                validate_input_parameter(p, p.default)
        actions = {a.id: a for a in self.actions}
        for checkpoint in [self.demo_checkpoint, self.guided_checkpoint, self.explore_checkpoint] + [t.checkpoint for t in self.tasks if t.checkpoint]:
            if checkpoint not in self.checkpoints: raise ValueError('检查点不存在')
        if not any('explore' in a.phases for a in self.actions): raise ValueError('自由探索需要动作')
        for s in self.demo_steps:
            for c in s.commands: validate_command(c, actions, 'demonstrate')
        for t in self.tasks:
            if t.objective not in self.objectives: raise ValueError('任务目标不存在')
            if t.assessment == 'deterministic' and not t.checks: raise ValueError('客观任务必须有可执行判定')
            if t.assessment == 'rubric' and not t.rubric: raise ValueError('模型评价必须有评价依据')
            if t.submission == 'on_action' and t.submit_action not in t.allowed_actions: raise ValueError('提交动作必须已开放')
            for a in t.allowed_actions:
                if a not in actions or 'guided' not in actions[a].phases: raise ValueError('任务引用不可用动作')
        tasks = {t.id: t for t in self.tasks}
        for v in self.validation_cases:
            if v.task_id not in tasks: raise ValueError('验收任务不存在')
            if (tasks[v.task_id].assessment == 'rubric') != (v.expected == 'awaiting_review'): raise ValueError('开放评价只能期待待评价状态')
            for c in v.commands:
                validate_command(c, actions, 'guided')
                if c.action not in tasks[v.task_id].allowed_actions: raise ValueError('验收使用任务未开放动作')
        for t in self.tasks:
            if t.assessment == 'rubric' and not any(v.task_id == t.id for v in self.validation_cases): raise ValueError('开放评价需要待评价验收样例')
            if t.assessment == 'deterministic' and {v.expected for v in self.validation_cases if v.task_id == t.id} != {'pass', 'fail'}:
                raise ValueError('每个客观任务必须提供成功和失败样例')
        text = json.dumps(self.model_dump(), ensure_ascii=False, allow_nan=False)
        if len(text.encode()) > 180000: raise ValueError('实验规格过大')
        return self


def validate_input_parameter(p, value):
    if p.type in ['number','integer']:
        if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value): raise ValueError('数值参数类型错误')
        if p.type == 'integer' and value != int(value): raise ValueError('需要整数')
        if p.minimum is not None and value < p.minimum or p.maximum is not None and value > p.maximum: raise ValueError('参数超出范围')
    elif p.type == 'boolean' and not isinstance(value,bool): raise ValueError('需要布尔值')
    elif p.type == 'string' and not isinstance(value,str): raise ValueError('需要字符串')
    if p.options and value not in p.options: raise ValueError('参数不在可选范围')


def validate_command(command, actions, phase):
    if command.action not in actions or phase not in actions[command.action].phases: raise ValueError('动作或阶段不存在')
    parameters = {p.name:p for p in actions[command.action].parameters}
    if set(command.input) != set(parameters): raise ValueError('动作参数缺失或多余')
    for name,p in parameters.items(): validate_input_parameter(p,command.input[name])


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
