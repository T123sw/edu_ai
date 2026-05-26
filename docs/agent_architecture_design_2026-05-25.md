# Agent 架构设计文档

> 版本：2026-05-26 v4  
> 状态：Phase 2-A ✅ Phase 2-B ✅ Phase 2-C ✅ Phase 3 ✅ Phase 4（真实引擎接入）✅ | Phase 5（远期）待实现

---

## 一、背景与目标

### 当前问题

1. **规划隐式**：5步执行路径硬编码在 system prompt，agent 不输出计划，用户看不到过程
2. **自检不可靠**：工具结果审查仅靠 prompt 提示，LLM 指令遵从率不稳定，无强制执行
3. **代码臃肿**：所有逻辑集中在 `react_agent.py`（500+ 行），节点、状态、路由、工具混杂
4. **模型不分工**：规划和执行使用同一模型配置，无法独立优化

### 设计目标

- Agent 在复杂任务时**显式生成结构化计划**，用户可见，但计划初期仅展示，不强制约束执行
- 工具结果经过**独立 Reflect Pipeline** 审查，支持代码规则 → LLM → 视觉模型分层
- 模块化文件结构，每个文件职责单一
- Planner / Executor 独立配置，当前均指向 Qwen，后续可分别切换模型

---

## 二、整体架构图

```
每轮对话入口：ReActAgent.run_stream()
│
├─ 读 checkpoint（active_draft_outline, current_plan, pending_tasks）
├─ should_plan() → 判断是否需要规划
├─ 构建消息列表（工作记忆注入 system prompt）
└─ graph.stream(initial_input, config, stream_mode="custom")
         │
         ▼
  ┌─────────────────────┐
  │  _route_entry       │  should_plan() → planner
  │  首轮/replan 入口   │  已有 plan    → executor
  └──────┬──────────────┘
         │
    ┌────┴────┐
    ▼         ▼
planner    executor_node ◄──────────────────────┐
  node     (Executor LLM)                        │
    │       流式输出 delta                        │
    │       决定工具调用                         │ continue
    └──►         │                               │
         tool_calls?  → No → END                 │
                │                                │
                ▼                                │
          tools_node                             │
          并行执行（PARALLEL_SAFE_TOOLS）         │
                │                                │
                ▼                                │
          reflect_node                           │
          Reflector Pipeline:                    │
            1. CodeRule（代码规则，最先）         │
            2. LLMEval（内容相关性）             │
            3. Vision（图片质量）                │
                │                                │
          verdict: pass ──────────────────────────┘
          verdict: pass_with_warning ─────────────┘ (带 hint 继续)
          verdict: retry ────────────────────────── (注入 hint 重试)
          verdict: replan ──────────► planner_node
          verdict: abort ───────────► executor_node (通知用户)
```

---

## 三、文件结构

```
app/chat/runtime/
│
├── react_agent.py                  # 公共入口：ReActAgent 类，只暴露 run_stream()
│
├── graph/
│   ├── __init__.py
│   ├── state.py                    # AgentState TypedDict（唯一状态定义）
│   ├── builder.py                  # _build_graph()，图的装配
│   └── routes.py                   # 路由函数：_route_entry, _route_after_executor,
│                                   #           _route_after_reflect, should_plan()
│
├── nodes/
│   ├── __init__.py
│   ├── planner.py                  # planner_node：生成 / 更新 Plan
│   ├── executor.py                 # executor_node：LLM 工具决策 + 流式输出
│   ├── tools.py                    # tools_node：工具执行（支持并行白名单）
│   └── reflect.py                  # reflect_node：调用 ReflectorPipeline
│
├── reflection/
│   ├── __init__.py
│   ├── base.py                     # BaseReflector, ReflectVerdict
│   ├── rules.py                    # 代码规则：LengthReflector, SourcesReflector,
│   │                               #           ChapterCountReflector
│   ├── llm_eval.py                 # LLMReflector：内容相关性、结构合理性
│   └── vision.py                   # VisionReflector：图片质量（视觉模型）
│
├── planning/
│   ├── __init__.py
│   ├── schema.py                   # Plan, PlanStep dataclass
│   └── prompts.py                  # Planner 专用 system prompt 模板
│
└── agent_tools/                    # 已有，不改动
    ├── schemas.py
    ├── executor.py
    ├── context.py
    ├── constants.py
    └── handlers/
```

---

## 四、AgentState 完整定义

> 文件：`graph/state.py`

```python
from typing import TypedDict, Literal

class AgentState(TypedDict):
    # ── 每轮重置（initial_input 写入）────────────────────────────────────────
    messages: list          # 本轮完整消息列表（从 snapshot 重建）
    tool_exchange: list     # 本轮工具调用/结果消息，用于持久化
    fallback_reason: str    # 非空 → 触发降级

    # ── 跨轮 checkpoint 持久化 ─────────────────────────────────────────────
    active_draft_outline: dict | None   # 上轮展示给用户的大纲（L2 工作记忆）
    pending_tasks: list                 # 已提交的后台生成任务

    # ── 计划相关 ────────────────────────────────────────────────────────────
    current_plan: dict | None           # Plan 序列化 dict
    plan_step_index: int                # 当前执行到第几步（guided/strict 模式使用）
    plan_mode: str                      # "display_only" | "guided" | "strict"
                                        # Phase 2-B: display_only
                                        # Phase 3:   guided → strict

    # ── Reflect 结果（reflect_node → executor_node 传递，每轮清空）──────────
    reflect_verdict: str    # "pass"|"pass_with_warning"|"retry"|"replan"|"abort"
    reflect_hint: str       # 失败原因，注入给 executor 的上下文
    reflect_filtered: dict  # 过滤后的干净数据（如合格图片），executor 注入 LLM 时使用
    retry_counts: dict      # {"step_2:web_search": 1}，防止 reflect 死循环
```

**字段生命周期说明：**

| 字段 | 生命周期 | 说明 |
|---|---|---|
| `messages`, `tool_exchange`, `fallback_reason` | 每轮重置 | initial_input 覆盖 |
| `reflect_verdict`, `reflect_hint`, `reflect_filtered` | 节点间传递 | reflect_node 写，executor_node 读后清空 |
| `retry_counts` | 轮内累积，轮间保留 | 每轮开始时从 initial_input 传入（不重置，跨步骤计数） |
| `active_draft_outline`, `pending_tasks`, `current_plan` | 跨轮持久化 | LangGraph checkpoint（Phase 2-C 换 SqliteSaver） |
| `plan_step_index`, `plan_mode` | 跨轮持久化 | 计划模式升级时启用 |

---

## 五、Plan 数据结构

> 文件：`planning/schema.py`

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class PlanStep:
    index: int
    user_title: str           # 给用户展示：「检索课程资料与案例」
    internal_action: str      # executor/router 判断用：「retrieve_context」
    expected_tools: list[str] # 预期调用的工具，可多个
    constraints: dict         # reflect 节点读取的质量约束
    status: Literal["pending", "running", "done", "failed", "skipped"] = "pending"

    # 示例：
    # PlanStep(
    #     index=2,
    #     user_title="检索课程资料与案例",
    #     internal_action="retrieve_context",
    #     expected_tools=["rag_search", "web_search"],
    #     constraints={"min_answer_length": 200, "require_sources": True, "min_sources": 2}
    # )

@dataclass
class Plan:
    steps: list[PlanStep]
    global_constraints: dict    # 超时、最大总重试次数等全局约束
    resource_type: str          # "report" | "ppt" | "lesson_plan" | "quiz"
    subject: str
    can_replan: bool = True
```

**user_title vs internal_action 分离原因：**  
用户不关心调用了哪个工具，前端展示 `user_title`；  
路由和 executor 使用 `internal_action` 做逻辑判断；  
一个 step 可以对应多个 `expected_tools`（如 retrieve_context 可以是 rag + web）。

---

## 六、should_plan() 路由规则

> 文件：`graph/routes.py`

**触发 planner 的条件（满足任意一条）：**

```python
def should_plan(request, snapshot, state) -> bool:
    question = request.question or ""

    # 1. 生成类任务（报告、PPT、教案、练习题）
    if any(kw in question for kw in ["生成", "制作", "写", "创建", "报告", "PPT", "教案", "练习题"]):
        return True

    # 2. 多步骤或设计类请求
    if any(kw in question for kw in ["方案", "计划", "调研", "分析", "设计", "实现"]):
        return True

    # 3. 有未完成的工作记忆（说明是进行中的复杂任务）
    if state.get("active_draft_outline") or state.get("pending_tasks"):
        return True

    # 4. reflect 要求重规划
    if state.get("reflect_verdict") == "replan":
        return True

    # 5. 已有计划但需要更新
    if state.get("current_plan") and state.get("reflect_verdict") == "replan":
        return True

    return False
```

**不触发 planner 的典型场景：**

- 普通知识问答（「RAG 是什么」）
- 用户确认类回复（「好的」「可以」「继续」）
- 闲聊
- 单句解释
- 局部文案修改请求

---

## 七、planner_node 设计

> 文件：`nodes/planner.py`

### 触发条件

```python
def _route_entry(state):
    if state["current_plan"] is None or state["reflect_verdict"] == "replan":
        return "planner"
    return "executor"
```

### 节点行为

```python
def planner_node(state: AgentState) -> dict:
    writer = get_stream_writer()
    rt = get_config()["configurable"]["runtime"]
    planner_gateway = rt["planner_gateway"]   # Config.AGENT_PLANNER_* 配置

    replan_hint = state.get("reflect_hint", "")
    existing_plan = state.get("current_plan")

    # 已有计划 + 失败原因 → 只修改受影响的 steps，保留其余
    plan = _call_planner_llm(planner_gateway, state, replan_hint, existing_plan)

    writer({"type": "plan", "payload": plan.to_dict()})  # 用户可见

    return {
        "current_plan": plan.to_dict(),
        "plan_step_index": 0,
        "plan_mode": "display_only",   # Phase 2-B 固定，Phase 3 升级
        "reflect_verdict": "",         # 清空 replan 信号
        "reflect_hint": "",
    }
```

### plan_mode 三个阶段

| 值 | 含义 | 实现时机 |
|---|---|---|
| `display_only` | 计划仅展示给用户，executor 仍按自身判断执行工具 | Phase 2-B |
| `guided` | executor 必须参考当前 plan_step，但可灵活调整 | Phase 3 |
| `strict` | 路由层强制按 step 顺序执行，不允许跳步 | Phase 3+ |

---

## 八、executor_node 设计

> 文件：`nodes/executor.py`

### 与旧 agent_node 的区别

| | 旧 agent_node | 新 executor_node |
|---|---|---|
| 模型配置 | `REACT_AGENT_*` | `AGENT_EXECUTOR_*`（独立） |
| plan 意识 | 无 | display_only: 知道当前 plan；guided: 按 step 执行 |
| reflect hint | 无 | 有 hint → 追加 system 消息告知原因 |
| 工具结果注入 | 原始 tool result | 如有 reflect_filtered，优先使用过滤后版本 |

### reflect_filtered 注入逻辑

```python
# executor_node 构建消息时：
# tool_exchange 里保存原始结果（用于 trace/审计）
# 注入 LLM 的 messages 使用 filtered 版本（如果 reflect 过滤了图片）

if state.get("reflect_filtered"):
    # 用过滤后数据替换最近一条 tool 消息的内容
    # 确保 LLM 不会引用不合格图片
    ...
```

---

## 九、tools_node 设计

> 文件：`nodes/tools.py`

### 并行执行白名单

不是所有工具都可以并行。使用简单白名单，Phase 3 再升级为 ToolMeta：

```python
# Phase 2 用简单白名单
PARALLEL_SAFE_TOOLS = {"rag_search", "web_search"}

# Phase 3 升级为 ToolMeta（含 depends_on, mutates_state, writes, reads）
```

**不可并行的工具（顺序依赖或状态写入冲突）：**
- `draft_outline` → 写入 `active_draft_outline`，后续工具依赖它
- `generate_*` → 依赖 `active_draft_outline`，提交后台任务
- 任何 `mutates_state=True` 的工具

---

## 十、Reflect Pipeline 设计

> 文件：`reflection/`

### 接口定义

```python
# base.py

@dataclass
class ReflectVerdict:
    verdict: Literal["pass", "pass_with_warning", "retry", "replan", "abort"]
    hint: str = ""                          # 失败/警告原因，注入给 executor
    severity: Literal["info", "warning", "blocking"] = "info"
    filtered_data: dict = field(default_factory=dict)  # 过滤后的干净数据

class BaseReflector(ABC):
    priority: int = 0    # 同工具多个 reflector 的执行顺序（小的先执行）

    @abstractmethod
    def applies_to(self, tool_name: str) -> bool: ...

    @abstractmethod
    def evaluate(
        self,
        tool_name: str,
        result: dict,
        state: AgentState,
        step_constraints: dict,
    ) -> ReflectVerdict: ...
```

**severity 说明：**

| severity | verdict | 行为 |
|---|---|---|
| `info` | `pass_with_warning` | 继续执行，hint 追加到 executor 消息 |
| `warning` | `pass_with_warning` 或 `retry` | 视 retry_count 决定重试还是继续 |
| `blocking` | `retry` / `replan` / `abort` | 必须处理，不允许透传给用户 |

### retry 死循环保护

```python
# reflect_node 执行前检查
def _check_retry_limit(state, tool_name, step_index) -> bool:
    key = f"step_{step_index}:{tool_name}"
    count = state.get("retry_counts", {}).get(key, 0)
    max_per_step = state.get("current_plan", {}).get(
        "global_constraints", {}
    ).get("max_retries_per_step", 2)
    max_total = state.get("current_plan", {}).get(
        "global_constraints", {}
    ).get("max_total_reflect_retries", 4)
    total = sum(state.get("retry_counts", {}).values())

    if count >= max_per_step or total >= max_total:
        return False   # 超限，不允许再 retry
    return True

# 超限时降级处理：
# 原 verdict=retry → 改为 pass_with_warning（severity=warning）
# 原 verdict=replan → 改为 abort（告知用户）
```

### Reflector 注册表

| Reflector | 适用工具 | 类型 | priority | Phase |
|---|---|---|---|---|
| `LengthReflector` | rag_search, web_search | 代码规则 | 0 | 2-C |
| `SourcesReflector` | rag_search, web_search | 代码规则 | 1 | 2-C |
| `ChapterCountReflector` | draft_outline | 代码规则 | 0 | 2-C |
| `ContentRelevanceReflector` | web_search | LLM | 10 | 3 |
| `OutlineCoherenceReflector` | draft_outline | LLM | 10 | 3 |
| `VisionReflector` | rag_search, web_search | 视觉模型 | 20 | 3 |

### VisionReflector 工作流程

```
web_search 返回含图片的结果
  ↓
VisionReflector.evaluate()
  ↓
  for each image_url in payload["images"]:
      prompt = f"这张图片是否适合用于《{subject}》的{resource_type}？
                 评估：1.内容相关性 2.清晰度 3.教育适用性
                 回答：合格/不合格 + 一句理由"
      verdict = vision_gateway.chat([image_url, prompt])
  ↓
  合格图片 > 0 → verdict="pass", filtered_data={"images": good_images}
  合格图片 = 0 且未超 retry 限制 → verdict="retry", severity="blocking"
  合格图片 = 0 且已超 retry 限制 → verdict="pass_with_warning", severity="warning"
                                     hint="未能找到高质量配图，已跳过图片"
```

### filtered_data 流转说明

```
tools_node 执行工具
    └─ 原始 result → 写入 tool_exchange（审计用，不修改）

reflect_node 审查
    └─ filtered_data → 写入 AgentState.reflect_filtered

executor_node 下一轮
    └─ 构建 messages 时：
       有 reflect_filtered → 用过滤数据格式化 tool result 注入 LLM
       无 reflect_filtered → 使用原始 tool result
       SSE tool_result 事件 → 只发 summary（不变）
```

---

## 十一、模型配置分层

> 文件：`core/config.py`

```python
# Agent Planner 模型（推理规划，当前指向 Qwen，后续可换为更强的推理模型）
AGENT_PLANNER_MODEL     = os.getenv("AGENT_PLANNER_MODEL",    LLM_MODEL_DEEP)
AGENT_PLANNER_API_BASE  = os.getenv("AGENT_PLANNER_API_BASE", DEEP_MODEL_API_BASE)
AGENT_PLANNER_API_KEY   = os.getenv("AGENT_PLANNER_API_KEY",  DEEP_MODEL_API_KEY)

# Agent Executor 模型（工具调用决策，当前指向 Qwen，后续可换为更快的模型）
AGENT_EXECUTOR_MODEL    = os.getenv("AGENT_EXECUTOR_MODEL",    LLM_MODEL_DEEP)
AGENT_EXECUTOR_API_BASE = os.getenv("AGENT_EXECUTOR_API_BASE", DEEP_MODEL_API_BASE)
AGENT_EXECUTOR_API_KEY  = os.getenv("AGENT_EXECUTOR_API_KEY",  DEEP_MODEL_API_KEY)

# VisionReflector 复用已有视觉模型配置（VISION_MODEL_ID / QWEN_BASE_URL / QWEN_API_KEY）
```

**.env 独立切换示例：**
```bash
# 当需要更强的规划模型时
AGENT_PLANNER_MODEL=qwen-max
# 当需要更快的执行模型时
AGENT_EXECUTOR_MODEL=qwen-turbo
```

---

## 十二、SSE 事件全集

| 事件类型 | 触发节点 | payload 主要字段 | 状态 |
|---|---|---|---|
| `status` | run_stream() | `stage`, `label` | 已实现 |
| `plan` | planner_node | `steps[]`, `constraints`, `resource_type`, `subject` | Phase 2-B |
| `delta` | executor_node | `content` | 已实现 |
| `tool_call` | executor_node | `tool`, `args` | 已实现 |
| `tool_result` | tools_node | `tool`, `summary`, `ok` | 已实现 |
| `reflect` | reflect_node | `tool`, `verdict`, `severity`, `issue` | Phase 2-C |
| `task_submitted` | tools_node | `task_id`, `workflow_type`, `message` | 已实现 |
| `result` | executor_node | `message`, `tool_exchange`, `trace` | 已实现 |

---

## 十三、实施路线图（重排后）

### Phase 1（已完成）✅

- [x] LangGraph StateGraph 基础架构（executor_node + tools_node）
- [x] MemorySaver checkpoint（active_draft_outline 跨轮持久化）
- [x] 工作记忆注入 system prompt
- [x] tool_calls 持久化到 DB
- [x] AGENT_PLANNER_* / AGENT_EXECUTOR_* 配置分层

### Phase 2-A：稳住 Agent 正确性 ✅

**目标：不让 agent 忘记上一步，不让明显坏结果进入下一步**

- [x] 文件结构拆分（`graph/` + `nodes/` + `reflection/` + `planning/`）
- [x] 现有逻辑迁移到新文件，不改功能
- [x] 验收：现有 3 个 test 全部通过

### Phase 2-B：Plan 可见化 ✅

**目标：用户看见计划，执行链路不被计划绑死**

- [x] `planning/schema.py`（PlanStep 含 user_title / internal_action）
- [x] `nodes/planner.py`（planner_node + Planner LLM 调用 + fallback plan）
- [x] `should_plan()` 路由函数（generation keywords + confirm + replan signal）
- [x] `plan_mode="display_only"` 写入 AgentState
- [x] `plan` SSE 事件
- [x] 新增 T3 验收测试通过
- [ ] SqliteSaver 替换 MemorySaver（待安装 langgraph-checkpoint-sqlite）

### Phase 2-C：Reflect Pipeline 基础 ✅

**目标：代码规则自检稳定，防止循环**

- [x] `reflection/base.py`（BaseReflector + ReflectVerdict 含 severity）
- [x] `reflection/rules.py`（LengthReflector, SourcesReflector, ChapterCountReflector + ReflectorPipeline）
- [x] `nodes/reflect.py`（reflect_node，tools→reflect→executor/planner 图连线）
- [x] `retry_counts` 写入 AgentState，超限降级为 pass_with_warning
- [x] `reflect` SSE 事件
- [x] reflect_filtered 流转基础设施（executor 已有 _inject_reflect_hint）
- [x] 16个单元测试全部通过（T2 代码规则 + T4 反死循环）

### Phase 3：Reflect 完整化 + Plan 驱动执行 ✅

- [x] `plan_mode` 升级为 `guided`（executor 参考当前 plan step）
- [x] `plan_step_index` 驱动执行顺序（reflect_node 通过时自动推进）
- [x] `reflect/llm_eval.py`（ContentRelevanceReflector, OutlineCoherenceReflector）
- [x] `reflect/vision.py`（VisionReflector，接入视觉模型）
- [x] `plan_step_update` SSE 事件（running/done）
- [ ] 前端展示 step 状态（pending / running / done / failed）— 前端任务

### Phase 4：真实引擎全接入 ✅

- [x] `build_vision_gateway()` 工厂函数
- [x] `ReActAgent` 接入 vision_gateway / rag_retriever / web_retriever
- [x] 反模式检查通过（无 WorkflowRuntime / stub-* / _agent_params 引用）

### Phase 5（远期）

- [ ] `plan_mode="strict"`（路由层强制按 step 顺序）
- [ ] ToolMeta（parallel_safe, depends_on, mutates_state 完整元信息）
- [ ] Supervisor + 多 Agent（并行生成多种资源）
- [ ] L3 长期用户记忆（跨会话偏好学习）

---

## 十四、Phase 2 验收测试标准

### T1 工作记忆测试

```
轮1：用户「帮我生成量子计算报告大纲」
     → agent 调用 draft_outline
     → active_draft_outline 写入 checkpoint
轮2：用户「可以，开始生成」
     → executor 从 system prompt 的工作记忆中获取大纲
     → 调用 generate_report，confirmed_outline 来自工作记忆
     → 不重新调用 draft_outline
```

### T2 Reflect 代码规则测试

```
场景：rag_search 返回 answer=""，sources=[]
期望：SourcesReflector.evaluate() → verdict="retry", severity="blocking"

场景：draft_outline 返回只有 2 个 ## 标题，constraints.min_chapters=5
期望：ChapterCountReflector.evaluate() → verdict="retry", severity="blocking"
```

### T3 Plan 可见化测试

```
用户请求「生成 PPT」且 should_plan() = True
期望：
  1. graph 先到 planner_node
  2. 发出 "plan" SSE 事件
  3. plan.steps 包含 user_title（不是 tool 名）
  4. 后续进入 executor_node 正常执行
```

### T4 反死循环测试

```
场景：web_search 连续 max_retries_per_step=2 次结果不合格
期望：
  第1次 reflect → verdict="retry"
  第2次 reflect → verdict="retry"
  第3次 reflect → verdict 降级为 "pass_with_warning"，severity="warning"
  executor 收到 hint 告知用户当前资料不足，继续执行而不是死循环
```

### T5 Checkpoint 持久化测试（Phase 2-B 换 SqliteSaver 后）

```
步骤：
  1. 完成一轮大纲生成（active_draft_outline 写入 checkpoint）
  2. 重启服务
  3. 发送「好的，开始生成」

期望：
  active_draft_outline 从 SqliteSaver 恢复
  executor 正确调用 generate_report，confirmed_outline 非空
```

---

## 十五、关键设计决策记录

| 决策 | 选择 | 理由 |
|---|---|---|
| plan 是否驱动循环 | 否（display_only），Phase 3 升级 | 避免过早约束执行链路 |
| plan_mode 显式化 | 是，三级枚举 | 让当前弱约束的语义明确，不产生歧义 |
| Reflect retry 上限 | 是，超限降级为 pass_with_warning | 防止死循环，保证流程完整性 |
| Reflect 扩展方式 | BaseReflector + priority + Pipeline | 新增审查逻辑不改现有代码 |
| filtered_data 流转 | tool_exchange 存 raw，messages 注入 filtered | 审计和执行分离，LLM 不引用不合格数据 |
| PlanStep 双字段 | user_title + internal_action 分离 | 用户展示与内部路由解耦 |
| should_plan 路由 | 代码规则白名单 | 简单对话不启动重型 planner |
| 并行工具 | PARALLEL_SAFE_TOOLS 白名单，Phase 3 升级 ToolMeta | 先简单可用，复杂依赖关系后置 |
| Checkpoint 持久化 | Phase 2-B 换 SqliteSaver | MemorySaver 先验证功能，再换持久化方案 |
| 模型分层 | AGENT_PLANNER_* / AGENT_EXECUTOR_* 独立配置 | 当前同指 Qwen，env 单独设置即可切换 |
| VisionReflector 时机 | Phase 3 | 代码规则先稳住，视觉模型后置 |
