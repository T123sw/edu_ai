"""Versioned Sandpack projects with UI, browser Jest, and Node HTTP checks."""
from typing import Literal
from uuid import UUID
import hashlib
import json
from pydantic import Field, model_validator, field_validator
from .schemas import StrictModel, ExerciseArtifact
from .runtime_config import ProjectRuntime, MULTI_TEMPLATE, validate_files, runtime_for
from .project_workflow import ProjectPlan, StepUnit, UiAssertion, validate_project_plan, validate_step_unit

PROJECT_TEMPLATE = 'react-app-v1'
PROJECT_FILES = {'/src/App.jsx', '/src/styles.css'}
STARTER_FILES = {'/src/App.jsx': '''import React from 'react';
import './styles.css';
export default function App() {
  // TODO: 按左侧步骤逐步完成你的项目。
  return <main><h1>我的项目</h1><p>从第一步开始实现。</p></main>;
}
''', '/src/styles.css': 'body { margin: 0; font-family: sans-serif; }\nmain { padding: 24px; }\n'}

def bounded_files(files):
    if not files or len(files)>8 or any(not isinstance(k,str) or not isinstance(v,str) for k,v in files.items()):
        raise ValueError('工程文件无效')
    if sum(len(k.encode())+len(v.encode()) for k,v in files.items())>131072:
        raise ValueError('工程超过 128KiB 运行限制')
    return files

def project_files(files):
    bounded_files(files)
    if set(files)!=PROJECT_FILES: raise ValueError('工程必须只包含 App.jsx 和 styles.css')
    return files

def hash_files(files):
    return hashlib.sha256(json.dumps(files,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

# Standard roles supported by the installed Playwright runtime.
AriaRole = Literal[
    'alert','alertdialog','application','article','banner','blockquote','button','caption',
    'cell','checkbox','code','columnheader','combobox','complementary','contentinfo','definition',
    'deletion','dialog','directory','document','emphasis','feed','figure','form',
    'generic','grid','gridcell','group','heading','img','insertion','link',
    'list','listbox','listitem','log','main','marquee','math','meter',
    'menu','menubar','menuitem','menuitemcheckbox','menuitemradio','navigation','none','note',
    'option','paragraph','presentation','progressbar','radio','radiogroup','region','row',
    'rowgroup','rowheader','scrollbar','search','searchbox','separator','slider','spinbutton',
    'status','strong','subscript','superscript','switch','tab','table','tablist',
    'tabpanel','term','textbox','time','timer','toolbar','tooltip','tree',
    'treegrid','treeitem',
    'output',  # Legacy artifact compatibility; new material uses the native status role.
]

class UiLocator(StrictModel):
    # Accept an explicitly empty optional scope emitted by schema-driven models;
    # a non-null nested scope is still rejected.
    within: None = None
    index: int | None = Field(default=None,ge=0,le=1000,description='可选，按 DOM 顺序取匹配集合中从 0 开始的一个元素，例如 index=0 取第一项；越界会失败。仅当场景已确定顺序时使用；统计整个集合数量时不填 index。')
    role: AriaRole | None = Field(default=None, description="按浏览器语义角色定位元素，例如 list 是容器，listitem 是条目；与 testId 二选一。多个元素可匹配同一角色，name 可缩小集合。")
    name: str | None = Field(default=None,max_length=1000,description="与 role 一起按可访问名称精确匹配，不是 CSS 选择器或任意文本搜索；仅 testId 定位时不可填写。")
    testId: str | None = Field(default=None,min_length=1,max_length=200,description="精确匹配元素的 data-testid 属性，不会自动定位其子元素。标记在容器上就定位容器；统计条目时定位条目集合。与 role/name 二选一。")
    @model_validator(mode='after')
    def valid(self):
        if bool(self.testId)==bool(self.role) or (self.testId and self.name is not None):
            raise ValueError('目标必须为 testId 或 role/name')
        return self

class UiTarget(UiLocator):
    within: UiLocator | None = Field(default=None,description='可选祖先容器定位：先用 within 的 role/name 或 testId（以及可选 index）选定容器，再在其后代中定位本 target。文本标签与按钮是兄弟时，不能把文本标签作为按钮的 within；可直接对重复按钮用 target.index 选择。重复容器也可用 within.index 取顺序确定的某一项。不指定 index 时容器须唯一；容器缺失或重复会失败，包括 count=0。不支持嵌套 within，不必改动旧名称或 testId。')

class UiAction(StrictModel):
    @model_validator(mode='before')
    @classmethod
    def normalize_locator_options(cls, value):
        # Accept the equivalent action-level spelling from model output, then
        # store only the canonical target shape. Never guess between conflicts.
        if isinstance(value,dict) and isinstance(value.get('target'),dict):
            value={**value,'target':dict(value['target'])}
            for key in ('within','index'):
                if key not in value: continue
                option=value.pop(key)
                if option is None: continue
                current=value['target'].get(key)
                if current is not None and current!=option:
                    raise ValueError(f'{key} 定位选项冲突')
                value['target'][key]=option
        return value

    type: Literal['click','fill','press','assert'] = Field(description='click 点击；fill 填写输入框；press 向目标发送按键；assert 读取页面状态并比较。每项检查从全新页面开始，动作按顺序执行。')
    target: UiTarget = Field(description="本动作真正操作或观察的元素。单目标操作与 visible/enabled/text/value 要唯一；count 和集合布局检查可匹配多个元素。")
    value: str | None = Field(default=None,max_length=4000,description="fill 要填写的字符串或 press 的按键名；不是断言预期值。")
    assertion: UiAssertion | None = Field(default=None,description=(
        '仅 assert 使用。count=target 匹配的 DOM 元素个数，不是容器子元素数量、文字中的数字或数据数组长度；'
        '空容器仍计为 1，检查集合为空应定位条目集合并期望 0。'
        'text=目标全部后代 textContent 去除首尾空白后的精确文字；value=表单控件当前 inputValue 精确值。'
        'visible=目标可见；enabled=目标可见且可操作；checked=复选框或单选框选中，默认期望 true，可用 expected=false 检查反向状态。'
        'above=唯一 target 底边不低于 relativeTo 所有目标顶边；'
        'not_overlapping=至少两个可见目标互不重叠；within_viewport=所有目标完整位于当前窗口；布局检查不自动滚动。'))
    expected: str | int | bool | None = Field(default=None,description="count 填非负整数，表示匹配元素个数；text/value 填精确字符串。visible/enabled/checked 可填布尔值，省略为 true；布局断言省略 expected。预期从需求推导，不能为了通过而迁就错误代码。")
    relativeTo: UiTarget | None = Field(default=None,description="仅 above 使用：位于 target 下方的参照目标集合。其他断言不填写。")
    @model_validator(mode='after')
    def valid(self):
        if self.type=='assert':
            if not self.assertion: raise ValueError('缺少断言')
            if self.assertion in {'visible','enabled','checked'} and self.expected is not None and type(self.expected) is not bool: raise ValueError('状态断言需要布尔值')
            if self.assertion=='count' and (type(self.expected) is not int or self.expected<0): raise ValueError('count 必须为非负整数')
            if self.assertion in {'text','value'} and not isinstance(self.expected,str): raise ValueError('精确断言必须提供字符串')
        elif self.assertion is not None or self.expected is not None: raise ValueError('动作不能附带断言')
        if self.type in {'fill','press'} and self.value is None: raise ValueError('动作缺少 value')
        if self.assertion == 'above':
            if self.relativeTo is None or self.expected is not None:
                raise ValueError('above 必须提供 relativeTo，不接受 expected')
        elif self.relativeTo is not None:
            raise ValueError('只有 above 可以指定 relativeTo')
        if self.assertion in {'not_overlapping','within_viewport'} and self.expected is not None:
            raise ValueError('布局断言不接受 expected')
        return self

class UiCheck(StrictModel):
    @model_validator(mode='before')
    @classmethod
    def canonical_ui_engine(cls, value):
        # Older UI checks have no discriminator. An explicit, unambiguous
        # spelling from a model is equivalent; preserve the stored wire shape.
        if isinstance(value, dict) and value.get('engine') == 'ui':
            return {key: item for key, item in value.items() if key != 'engine'}
        return value

    id: str = Field(pattern=r'^[a-z][a-z0-9-]*$')
    label: str = Field(min_length=1,max_length=1000)
    actions: list[UiAction] = Field(min_length=1,max_length=100)
    viewport: Literal['desktop','mobile'] | None = Field(default=None,description='desktop 为 1280×800，mobile 为 390×844；布局验收按计划窗口执行，每项使用独立新页面。')
    @model_validator(mode='after')
    def assertions(self):
        if not any(a.type=='assert' for a in self.actions): raise ValueError('检查必须包含断言')
        return self

class JestCheck(StrictModel):
    id: str = Field(pattern=r'^[a-z][a-z0-9-]*$')
    label: str = Field(min_length=1,max_length=1000,description='面向学习者的验收行为说明。')
    engine: Literal['sandpack-jest']
    source: str = Field(min_length=1,max_length=32000,description=(
        '完整标准 Jest 测试文件源码，宿主保存为 /__checks__/<id>.test.js。'
        '从 ../ 加工程实际路径导入被测模块；React 工程可导入组件。测试环境提供 React 18.3.1、'
        '@testing-library/react 14.3.1（render/screen/fireEvent/within/waitFor）已安装。'
        '使用 test/it、describe、expect 等 Jest 全局；宿主自动 cleanup 并要求每项测试执行断言。'
        '可断言 disabled/checked/集合长度/空值等任意可观察状态；只有浏览器支持的 API，无 Node/后端/外部网络。'
        '没有 jest-dom 和 user-event，不使用未安装库的 matcher；用原生属性及 toBe/toEqual/toHaveLength/toBeNull 等。'
        '每个测试自行 render 与准备，不依赖其他测试；不使用 skip/only 或 mock 被测业务代码。'
        '预期由需求决定，不能根据错误参考输出改写预期。布局几何检查使用 UiCheck。'))
    viewport: Literal['desktop','mobile'] | None = Field(default=None,description='标准组件测试不保证预览布局，几何或视口要求使用 UiCheck。')

class HttpRequest(StrictModel):
    method: Literal['GET','POST','PUT','PATCH','DELETE','HEAD'] = 'GET'
    path: str = Field(pattern=r'^/',max_length=2000,description='当前 Node 服务的相对 URL，不能使用主机地址或外部服务。')
    body: None = Field(default=None,description='当前 Nodebox 的请求体传输存在上游缺陷，只支持无请求体接口。需要 JSON POST/PUT/PATCH、表单或上传的目标必须说明不支持，不能悄悄改成查询参数。')
    status: int = Field(ge=100,le=599,description='预期 HTTP 状态码。')
    jsonBody: dict | list | str | int | float | bool | None = Field(default=None,description='可选：精确比较返回 JSON；为 null 时只比较状态码或 text。')
    text: str | None = Field(default=None,max_length=8000,description='可选：精确比较响应文本。')

    @field_validator('path')
    @classmethod
    def local_path(cls,value):
        if value.startswith('//') or '\\' in value or any(ord(c)<32 for c in value):raise ValueError('HTTP 路径无效')
        return value

class HttpCheck(StrictModel):
    id: str = Field(pattern=r'^[a-z][a-z0-9-]*$')
    label: str = Field(min_length=1,max_length=1000)
    engine: Literal['http']
    requests: list[HttpRequest] = Field(min_length=1,max_length=20,description='在一个全新 Node 服务内顺序执行；可先创建数据再查询/修改。不同检查不共享状态，静态期望使用请求内明确指定的数据和 ID。')
    viewport: Literal['desktop','mobile'] | None = None

ProjectCheck = UiCheck | JestCheck | HttpCheck

class ProjectTask(StepUnit):
    id: str
    cumulativeCheckIds: list[str]

class ProjectArtifact(StrictModel):
    schemaVersion: Literal[2] = 2
    runtimeKind: Literal['react_app','sandpack_project'] = 'react_app'
    runtime: ProjectRuntime | None = None
    templateVersion: Literal['react-app-v1','sandpack-project-v1'] = PROJECT_TEMPLATE
    exerciseId: str
    artifactVersion: int = Field(ge=1)
    topic: str
    title: str
    summary: str
    plan: ProjectPlan
    starterFiles: dict[str,str]
    tasks: list[ProjectTask]
    checks: list[ProjectCheck] = Field(min_length=1,max_length=64)
    validationSummary: dict
    @model_validator(mode='after')
    def consistent(self):
        derived=validate_runtime_plan(self.plan.model_dump())
        if self.runtimeKind=='sandpack_project':
            if self.runtime is None or self.runtime!=self.plan.runtime or self.templateVersion!=MULTI_TEMPLATE: raise ValueError('项目运行配置不一致')
            validate_files(self.starterFiles,self.plan.editableFiles)
        else:
            if self.runtime is not None or self.plan.runtime is not None or self.templateVersion!=PROJECT_TEMPLATE: raise ValueError('旧项目运行配置不一致')
            project_files(self.starterFiles)
        if [t.id for t in self.tasks]!=[s.id for s in self.plan.steps]: raise ValueError('任务顺序不匹配')
        if [c.id for c in self.checks]!=[cid for s in self.plan.steps for cid in s.newCheckIds]: raise ValueError('检查集合不匹配')
        validate_planned_checks(self.plan.model_dump(),[c.model_dump(exclude_none=True) for c in self.checks])
        for task in self.tasks:
            unit={k:v for k,v in task.model_dump().items() if k not in {'id','cumulativeCheckIds'}}
            validate_step_unit(self.plan.model_dump(),unit)
            if task.id!=task.stepId or task.cumulativeCheckIds!=derived['cumulativeCheckIds'][task.id]: raise ValueError('累计检查不匹配')
        return self

def validate_runtime_plan(payload, *, require_check_contract=False):
    result=validate_project_plan(payload)
    plan=result['plan']
    runtime=runtime_for(plan)
    if plan['runtimeKind']=='sandpack_project':
        if runtime is None: raise ValueError('项目缺少 Sandpack 运行配置')
        validate_files({path:'' for path in plan['editableFiles']})
        if runtime['entry'] not in plan['editableFiles']: raise ValueError('入口不在工程文件清单中')
    elif plan['runtimeKind']!='react_app' or runtime is not None or set(plan['editableFiles'])!=PROJECT_FILES:
        raise ValueError('旧项目需使用 React 双文件协议；新工程使用 sandpack_project 与 runtime 配置')
    if len(plan['checks'])>64: raise ValueError('工程检查超过 64 项运行限制')
    if require_check_contract:
        for check in plan['checks']:
            kinds=check['requiredAssertions']
            check['requiredAssertions']=list(dict.fromkeys(kinds))
            if set(kinds)&{'above','not_overlapping','within_viewport'} and not check['viewport']:
                check['viewport']='desktop'
    return result

def validate_planned_checks(plan, checks):
    planned={check['id']:check for check in plan['checks']}
    for check in checks:
        spec=planned[check['id']]
        required=set(spec.get('requiredAssertions') or [])
        runtime=runtime_for(plan)
        if check.get('engine')=='http':
            if not runtime or runtime['template']!='node': raise ValueError('HTTP 验收仅用于 Node 服务')
            continue
        if check.get('engine')=='sandpack-jest' and runtime and runtime['template'] in {'node','static','vue','svelte'}: raise ValueError('该模板使用页面或 HTTP 验收，不支持浏览器 Jest')
        if check.get('engine')=='sandpack-jest':
            if runtime and runtime['template'] in {'vanilla','vanilla-ts'} and spec['kind']!='function_case':
                raise ValueError('原生 JS/TS 的页面场景使用 UiCheck 操作实际预览；函数检查不能代替页面点击与显示结果')
            if required & {'above','not_overlapping','within_viewport'}:
                raise ValueError(f"{check['id']} 的几何验收需要使用页面布局检查")
            continue
        actual={action['assertion'] for action in check['actions'] if action['type']=='assert'}
        proven=set(actual)
        if actual & {'text','value','enabled'}: proven.add('visible')
        if any(action['type'] in {'click','fill','press'} for action in check['actions']):
            proven.update({'visible','enabled'})
        # Planning hints are not a second acceptance gate. Only geometry needs
        # a specific executor/viewport; normal behavior is proved by execution.
        geometry=required & {'above','not_overlapping','within_viewport'}
        if geometry and not geometry<=proven:
            raise ValueError(f"{check['id']} 缺少计划中的布局验收")
        if required and check.get('viewport')!=spec.get('viewport'):
            raise ValueError(f"{check['id']} 的检查窗口与计划不一致")

def parse_artifact(value):
    if hasattr(value,'model_dump'): value=value.model_dump(mode='json')
    return ProjectArtifact.model_validate(value) if value.get('schemaVersion')==2 else ExerciseArtifact.model_validate(value)

class ProjectCheckRequest(StrictModel):
    artifactVersion: int = Field(ge=1)
    taskId: str = Field(min_length=1,max_length=200)
    runId: UUID
    files: dict[str,str]
    _files = field_validator('files')(validate_files)

class ProjectCaseResult(StrictModel):
    caseId: str
    status: Literal['passed','failed']
    message: str = Field(max_length=2000)

class ProjectRun(StrictModel):
    runId: UUID
    exerciseId: str
    artifactVersion: int
    templateVersion: Literal['react-app-v1','sandpack-project-v1'] = PROJECT_TEMPLATE
    taskId: str
    codeHash: str = Field(pattern=r'^[a-f0-9]{64}$')
    status: Literal['passed','failed']
    results: list[ProjectCaseResult]
    durationMs: float = Field(ge=0,allow_inf_nan=False)
    evidenceSource: Literal['server_verified'] = 'server_verified'
