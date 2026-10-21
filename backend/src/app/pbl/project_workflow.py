"""Load the project Skill and check planning artifacts; never execute or publish code."""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from .runtime_config import ProjectRuntime

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identifier = Annotated[str, StringConstraints(pattern=r'^[a-z][a-z0-9-]*$')]
UiAssertion = Literal['visible','enabled','checked','text','value','count','above','not_overlapping','within_viewport']
SKILL_NAME = 'build-pbl-project'
# Versioned directory keeps running pre-split workers on their original prompt contract.
SKILL_ROOT = Path(__file__).parent / 'skills' / 'build-pbl-project-v5'
PHASE_REFERENCES = {
    'plan': 'planning.md', 'review_plan': 'planning.md',
    'build_step': 'step-unit.md', 'repair_step': 'step-unit.md',
    'build_checks': 'acceptance.md', 'repair_checks': 'acceptance.md',
    'validate': 'verification.md', 'publish': 'verification.md',
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Requirement(StrictModel):
    id: Identifier
    description: Text


class PlannedCheck(StrictModel):
    id: Identifier
    stepId: Identifier
    kind: Literal['function_case', 'ui_scenario', 'http_scenario'] = Field(description='计划场景类型：function_case 为浏览器纯函数，ui_scenario 为页面交互，http_scenario 为 Node 服务请求；不是后续检查引擎名称。')
    requirementIds: list[Identifier] = Field(min_length=1)
    setup: Text
    actions: list[Text] = Field(min_length=1)
    expected: list[Text] = Field(default_factory=list, description='Optional planning notes; executable step assertions carry the actual expectations.')
    requiredAssertions: list[UiAssertion] = Field(default_factory=list)
    viewport: Literal['desktop','mobile'] | None = None

    @field_validator('expected', mode='before')
    @classmethod
    def optional_notes(cls, value):
        if value is None: return []
        if isinstance(value,str): value=[value]
        if isinstance(value,list):
            return [item for item in value if not isinstance(item,str) or item.strip()]
        return value


class PlannedStep(StrictModel):
    id: Identifier
    title: Text
    objective: Text
    dependsOn: list[Identifier]
    entryCondition: Text
    deliverable: Text
    requirementIds: list[Identifier] = Field(min_length=1)
    focusFiles: list[Text] = Field(min_length=1)
    newCheckIds: list[Identifier] = Field(min_length=1)


class ProjectPlan(StrictModel):
    schemaVersion: Literal[1]
    title: Text
    goal: Text
    runtimeKind: Literal['js_function', 'react_app', 'sandpack_project']
    runtime: ProjectRuntime | None = None
    editableFiles: list[Text] = Field(min_length=1)
    requirements: list[Requirement] = Field(min_length=1)
    steps: list[PlannedStep] = Field(min_length=1)
    checks: list[PlannedCheck] = Field(min_length=1)

    @field_validator('editableFiles')
    @classmethod
    def normalized_file_paths(cls, paths):
        for path in paths:
            if (not path.startswith('/') or path.startswith('//') or '\\' in path
                    or '..' in path.split('/') or str(PurePosixPath(path)) != path
                    or path == '/'):
                raise ValueError('editableFiles 必须使用规范化工程绝对路径')
        return paths


class StepUnit(StrictModel):
    stepId: Identifier
    title: Text
    objective: Text
    instructionsMarkdown: Text
    explanationMarkdown: Text
    hints: list[Text] = Field(min_length=1)
    focusFiles: list[Text] = Field(min_length=1)
    checkIds: list[Identifier] = Field(min_length=1)


def unique(values, label):
    if len(values) != len(set(values)):
        raise ValueError(f'{label} 不能重复')
    return set(values)


def validate_project_plan(payload: dict) -> dict:
    """Validate a linear plan and derive cumulative checks, not completion status."""
    plan = ProjectPlan.model_validate(payload)
    requirements = unique([r.id for r in plan.requirements], 'requirement IDs')
    step_ids = unique([step.id for step in plan.steps], 'step IDs')
    check_ids = unique([check.id for check in plan.checks], 'check IDs')
    files = unique(plan.editableFiles, 'editableFiles')
    checks = {check.id: check for check in plan.checks}
    expected_kind = 'function_case' if plan.runtimeKind == 'js_function' else 'ui_scenario'
    covered = set()
    for check in plan.checks:
        refs = unique(check.requirementIds, f'{check.id} requirement IDs')
        if not refs <= requirements:
            raise ValueError(f'{check.id} 引用了未知需求')
        if check.stepId not in step_ids:
            raise ValueError(f'{check.id} 引用了未知步骤')
        if (plan.runtimeKind!='sandpack_project' and check.kind != expected_kind) or (plan.runtimeKind=='sandpack_project' and check.kind=='http_scenario' and (not plan.runtime or plan.runtime.template!='node')):
            raise ValueError(f'{check.id} 与声明的运行类型不匹配')
        covered.update(refs)
    if covered != requirements:
        raise ValueError(f'最终检查未覆盖全部项目需求，缺少检查的 requirement IDs: {sorted(requirements-covered)}；每项需求须由实际动作与断言验证，不能仅添加关联 ID 冒充覆盖')
    assigned = set()
    prior_coverage = set()
    cumulative = []
    derived = {}
    for index, step in enumerate(plan.steps):
        expected_dependencies = [] if index == 0 else [plan.steps[index - 1].id]
        if step.dependsOn != expected_dependencies:
            raise ValueError(f'{step.id} 必须沿顺序主线依赖前一步，首步无依赖')
        focus = unique(step.focusFiles, f'{step.id} focusFiles')
        if not focus <= files:
            raise ValueError(f'{step.id} 引用了未声明的编辑文件')
        targets = unique(step.requirementIds, f'{step.id} requirement IDs')
        if not targets <= requirements:
            raise ValueError(f'{step.id} 引用了未知需求')
        new_checks = unique(step.newCheckIds, f'{step.id} newCheckIds')
        if not new_checks <= check_ids or assigned & new_checks:
            raise ValueError(f'{step.id} 存在未知或重复归属的检查')
        step_coverage = set()
        for check_id in step.newCheckIds:
            check = checks[check_id]
            if check.stepId != step.id:
                raise ValueError(f'{check_id} 检查归属与步骤声明不同')
            step_coverage.update(check.requirementIds)
        # Earlier checks run on every later snapshot; inherited requirements need
        # not be duplicated in each new check package. Future checks cannot cover them.
        # A check may also observe a shared requirement's initial state without
        # claiming that all of its later behavior is implemented in this step.
        if not targets <= prior_coverage | step_coverage:
            raise ValueError(f'{step.id} 检查覆盖与本步需求不一致')
        prior_coverage.update(step_coverage)
        assigned.update(new_checks)
        cumulative.extend(step.newCheckIds)
        derived[step.id] = list(cumulative)
    if assigned != check_ids:
        raise ValueError('存在未分配给步骤的检查')
    return {'plan': plan.model_dump(), 'cumulativeCheckIds': derived,
            'structurallyValid': True, 'executionValidated': False, 'publishable': False}


def validate_step_unit(plan_payload: dict, payload: dict) -> dict:
    result = validate_project_plan(plan_payload)
    unit = StepUnit.model_validate(payload)
    step = next((step for step in result['plan']['steps'] if step['id'] == unit.stepId), None)
    if step is None:
        raise ValueError('单步材料引用了未知步骤')
    if not unique(unit.focusFiles, 'focusFiles') <= set(result['plan']['editableFiles']):
        raise ValueError('单步材料文件范围超出工程许可')
    if unique(unit.checkIds, 'checkIds') != set(step['newCheckIds']):
        raise ValueError('单步材料必须完整引用本步新增检查，不能混入未来或前序检查')
    return {'unit': unit.model_dump(), 'cumulativeCheckIds': result['cumulativeCheckIds'][unit.stepId],
            'executionValidated': False, 'publishable': False}


def load_project_skill(phase: str) -> dict:
    if phase not in PHASE_REFERENCES:
        raise ValueError('PBL_SKILL_PHASE_UNKNOWN')
    source = (SKILL_ROOT / 'SKILL.md').read_text(encoding='utf-8')
    if not source.startswith('---\n'):
        raise ValueError('PBL_SKILL_INVALID')
    _, header, body = source.split('---', 2)
    metadata = dict(line.split(':', 1) for line in header.splitlines() if ':' in line)
    metadata = {key.strip(): value.strip() for key, value in metadata.items()}
    if metadata.get('name') != SKILL_NAME or not metadata.get('description') or not body.strip():
        raise ValueError('PBL_SKILL_INVALID')
    reference_names = [PHASE_REFERENCES[phase], 'integration.md']
    references = [(name, (SKILL_ROOT / 'references' / name).read_text(encoding='utf-8').strip())
                  for name in reference_names]
    if any(not content for _, content in references):
        raise ValueError('PBL_SKILL_REFERENCE_EMPTY')
    content = '\n\n'.join([body.strip(), *(f'# {name}\n{content}' for name, content in references)])
    version = hashlib.sha256((source + '\n' + phase + '\n' + content).encode('utf-8')).hexdigest()
    return {'name': SKILL_NAME, 'phase': phase, 'version': version, 'references': reference_names,
            'instructions': f'<pbl_skill name="{SKILL_NAME}" phase="{phase}">\n{content}\n</pbl_skill>'}
