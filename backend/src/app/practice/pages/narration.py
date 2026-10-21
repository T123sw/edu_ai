"""Action-first planning and narration bound to executed actions, never predicted indices."""
import json
import re
from pydantic import Field
from .contracts import TextModel, package_spec

ACTION_PROTOCOL = 'edu-actions/1'
TWO_STAGE_PIPELINE = 'edu-two-stage/1'

class PlannedAction(TextModel):
    title: str = Field(min_length=1)
    operation: str = Field(min_length=1, description='动作与边界，不写执行前后讲解或预测结果')

class DemonstrationPlan(TextModel):
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    demo_initial: str = Field(min_length=1)
    demo_actions: list[PlannedAction] = Field(min_length=1)

class PlannedTask(TextModel):
    title: str = Field(min_length=1)
    initial: str = Field(min_length=1)
    interaction: str = Field(min_length=1, description='开放的真实动作与判定规则，不写教学讲解')
    completion: str = Field(min_length=1)

class ActionPlan(TextModel):
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    demo_initial: str = Field(min_length=1)
    demo_actions: list[PlannedAction] = Field(min_length=1)
    tasks: list[PlannedTask] = Field(min_length=1)

class DemoNarration(TextModel):
    id: str
    title: str = Field(min_length=1)
    before: str = Field(min_length=1)
    after: str = Field(min_length=1)

class ExplorationNarration(TextModel):
    overview: str
    demo_steps: list[DemoNarration]
    exploration_prompts: list[str] = Field(min_length=1, max_length=3, description='基于已实现控件的可选探索建议；说清改哪个条件、保持什么、观察什么，不要求完成任务')

class TaskNarration(TextModel):
    id: str
    prompt: str = Field(min_length=1)
    hints: list[str] = Field(default_factory=list)

class ActionNarration(TextModel):
    action_id: str
    pending: str = Field(default='', description='适用于此动作所有pending分支的讲解。只允许普通字段占位符{{facts.left}}，禁止if/else/条件块/计算；后续分支不唯一时不指定下一动作。')
    fail: str = Field(default='', description='错误原因与重试方法，只允许普通字段占位符，禁止条件块。')
    passed: str = Field(default='', description='当前任务完成反馈，只有实际算法结束才说算法完成。只允许普通字段占位符。')

class Narration(TextModel):
    overview: str
    demo_steps: list[DemoNarration]
    tasks: list[TaskNarration]
    action_feedback: list[ActionNarration]
    exploration_prompts: list[str] = Field(default_factory=list)

def action_spec(plan, science):
    return {**package_spec({
        'title': plan['title'], 'overview': plan['objective'], 'demo_initial': plan['demo_initial'],
        'demo_steps': [{**s, 'before': '', 'after': ''} for s in plan['demo_actions']],
        'tasks': [{**t, 'prompt': '', 'success': '任务已完成。', 'retry': '本次操作不正确，请重试。', 'hints': []} for t in plan.get('tasks', [])],
        'exploration_prompts': [],
    }, science), 'action_protocol': ACTION_PROTOCOL, 'capture_actions': True}

def trace_text(text, row, fallback):
    """Tolerate plain field placeholders in fixed narration, never execute expressions."""
    if not text:
        return fallback
    def replace(match):
        path = match.group(1).strip()
        if not re.fullmatch(r'\w+(?:\.\w+)*', path):
            raise ValueError('unsupported placeholder')
        value = row
        for key in path.split('.'):
            value = value[int(key)] if isinstance(value, list) and key.isdigit() else value[key]
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    try:
        rendered = re.sub(r'\{\{(.*?)\}\}', replace, text)
        return fallback if '{{' in rendered or '}}' in rendered else rendered
    except (KeyError, IndexError, TypeError, ValueError):
        return fallback

def bind_narration(spec, trace, catalog, narrative):
    """Bind by keys; response ordering and omitted optional prose never move actions."""
    demos = {item['id']: item for item in narrative['demo_steps']}
    tasks = {item['id']: item for item in narrative.get('tasks', [])}
    feedback = {item['action_id']: item for item in narrative.get('action_feedback', [])}
    # Missing prose falls back to recorded facts, not to another step's explanation.
    steps = []
    for row in trace:
        prose = demos.get(row['id'], {})
        steps.append({'id': row['id'], 'action_id': row['action_id'], 'title': trace_text(prose.get('title'), row, row['action_id']),
                      'operation': row['action_id'], 'before': trace_text(prose.get('before'), row, '执行下一项操作，观察实验状态。'),
                      'after': trace_text(prose.get('after'), row, '操作已执行，请观察状态变化。')})
    return {**spec, 'capture_actions': False, 'overview': narrative['overview'], 'demo_steps': steps,
            'action_catalog': catalog,
            'tasks': [{**t, 'prompt': tasks.get(t['id'], {}).get('prompt') or t['completion'],
                       'hints': tasks.get(t['id'], {}).get('hints', [])} for t in spec['tasks']],
            'action_feedback': {a['id']: feedback[a['id']] for a in catalog if a['id'] in feedback},
            'exploration_prompts': narrative['exploration_prompts'],
            'teaching_context': {**spec['teaching_context'], 'background': narrative['overview']}}
