from pydantic import BaseModel, ConfigDict, Field

PROTOCOL = 'edu-experiment/2'

class TextModel(BaseModel):
    model_config = ConfigDict(extra='ignore')

class Demonstration(TextModel):
    title: str = Field(min_length=1)
    before: str = Field(min_length=1, description='执行前提示')
    operation: str = Field(min_length=1, description='复用基础实验的哪个操作，如何演示')
    after: str = Field(min_length=1, description='操作后显示的预生成讲解')

class Exercise(TextModel):
    title: str = Field(min_length=1)
    initial: str = Field(min_length=1, description='任务开始时的数据和状态；任务中连续操作保留进度')
    prompt: str = Field(min_length=1)
    interaction: str = Field(min_length=1, description='每次开放哪些真实操作、中间操作反馈及继续方式，不给自动完成按钮')
    completion: str = Field(min_length=1, description='整个任务真实完成的本地判据；一次正确的中间操作不代表任务完成')
    success: str = Field(min_length=1)
    retry: str = Field(min_length=1)
    hints: list[str] = Field(min_length=1)

class TeachingPlan(TextModel):
    title: str = Field(min_length=1)
    overview: str = Field(min_length=1)
    demo_initial: str = Field(min_length=1)
    demo_steps: list[Demonstration] = Field(min_length=1)
    tasks: list[Exercise] = Field(min_length=1)
    exploration_prompts: list[str] = Field(min_length=1)

def package_spec(plan, science):
    """IDs are owned by the host, not cross-references invented by the model."""
    return {**plan, 'protocol': PROTOCOL,
            'demo_steps': [{**s, 'id': f'demo-{i+1}'} for i,s in enumerate(plan['demo_steps'])],
            'tasks': [{**s, 'id': f'task-{i+1}'} for i,s in enumerate(plan['tasks'])],
            'scientific_model': science,
            'teaching_context': {'background': plan['overview'], 'misconceptions': []},
            'state_fields': [], 'actions': []}

def page_spec(spec, phase):
    """Exploration owns its inputs; teaching descriptions are never its data."""
    if phase != 'explore':
        return spec
    return {**{k: v for k, v in spec.items() if k not in ('demo_initial', 'demo_result')},
            'demo_steps': [], 'tasks': []}
