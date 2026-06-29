# Agent 架构设计文档

> 版本：2026-06-11 v7  
> 状态：Phase 2-A ✅ Phase 2-B ✅ Phase 2-C ✅ Phase 3 ✅ Phase 4 ✅ Phase 5（strict + ToolMeta + 并行执行）✅ | Phase 6（Planner 子图 + 双轨规划 + HITL + Polisher）待实现
> 
> **配套实施文档**：
> - Phase 6-A（image_search 工具）：[`docs/Phase6A_image_search_实施计划_2026-06-11.md`](./Phase6A_image_search_实施计划_2026-06-11.md) — 含 SearXNG 部署、Provider 抽象、10 处接线 diff、4 天工作分解
> - Phase 6-B/6-C 实施文档：**待编写**（6-A 落地稳定后启动）
> 
> v7：新增 Phase 6-A 实施计划文档指针；本文档保持设计层定位，实施细节移至专项计划。
> 
> v6 重写第十六章：
> - Planner 由单节点升级为子图（skeleton / research / synthesize）
> - 新增 SectionEvidence 完整数据结构（claim + key_findings + snippets + confidence）
> - 视觉资产与文本证据双轨规划（visual_need 与 evidence 同 Planner 阶段产出，但 image_search 留给 Executor）
> - HITL 大纲编辑模型（stale 标记 + 显式重检触发 + 大纲树展开显示证据）
> - 节级（`###`）检索粒度 + 节级并发 + plan_progress 流式 SSE
> - Polisher 含 `[ref:sn_id]` → `[N]` 编号化与参考文献节生成
> - Phase 6 路线图细化为 6-A / 6-B-{1..5} / 6-C / 6-D
> 
> v5：第十六章首版「TVIR 启发的视觉证据增强」（轻量版 evidence 设计，已被 v6 替换为完整版）。

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

### Phase 5：strict 模式 + ToolMeta + 并行执行 ✅

- [x] `plan_mode="strict"`：executor 只看到当前 step 的 expected_tools（schema 过滤）
- [x] tools_node 强制校验：越界调用被替换为 strict_violation 错误（LLM 会自我纠正）
- [x] `ToolMeta`：parallel_safe / mutates_state / depends_on
- [x] 并行执行：parallel_safe 的工具组使用 ThreadPoolExecutor 并发
- [x] 17 个 Phase 5 测试覆盖

### Phase 6（视觉证据增强 + 文本证据接地 — 详见第十六章）

> 设计依据：TVIR（Text-Visual Interleaved Report Generation）论文 + 项目内 `docs/agent架构设计` / `docs/tvir总结` 启发文档。  
> 核心思想：**图片和事实证据都不是写完报告后再补，而是大纲阶段就规划好"哪节需要什么视觉证据、哪节用哪些事实片段做依据"。**  
> Phase 6 不再是单一"加图片"任务，而是 **Planner 节点形态升级（单节点 → 子图）+ 视觉与证据双轨规划 + HITL 大纲编辑 + Polisher 全局收口** 的一次集中演进。

#### 6-A：底层视觉资产工具（独立可上线）

> **实施详情见** [`Phase6A_image_search_实施计划_2026-06-11.md`](./Phase6A_image_search_实施计划_2026-06-11.md)（SearXNG 部署、Provider 抽象、10 处接线 diff、测试矩阵、4 天工作分解）。本节仅保留路线图层信息。

- [ ] 新增 `agent_tools/handlers/image_search.py`：外部图片搜索 API 封装
  - 输入：`query`, `count`, `style?`（real/diagram/chart/any）, `license?`, `safe?`
  - 输出：`{images: [{url, source_page, title, width, height, thumbnail, license?}], trace: {...}}`
  - provider 抽象（SearXNG / Bing v7 / SerpApi / Pexels），默认走 `IMAGE_SEARCH_PROVIDER`
- [ ] 启发式过滤在工具内执行（尺寸/格式/域名黑名单/source_page 去重）
- [ ] 新增 `agent_tools/handlers/diagram_gen.py`：Mermaid 文本图生成
  - 输入：`title`, `kind`（flowchart/sequence/class/state/er）, `intent`
  - 输出：`{mermaid: "...", svg_url?: "..."}`
  - 由 Executor LLM 直接生成 Mermaid DSL，前端渲染或后端 mermaid-cli 转 SVG
- [ ] schema/ToolMeta 注册（`parallel_safe=True, mutates_state=False`）
- [ ] **激活已有 `VisionReflector`**：`_APPLIES_TO` 增加 `image_search`（diagram_gen 不需 VLM 审，结构正确即合格）
- [ ] `web_search_tool` 的 payload 不再塞 `images`，图片彻底走独立工具
- [ ] 验收：报告生成出现真实搜索图 + 至少一张 Mermaid 流程/结构图

#### 6-B-1：Planner 子图骨架（单节点 → 三节点）

- [ ] 拆分 `planner_node` 为三节点子图：`planner_skeleton_node` → `planner_research_node` → `planner_synthesize_node`
- [ ] `graph/builder.py` 更新连边，三节点独立 checkpoint
- [ ] 路由：`_route_entry` 行为不变（首轮 / replan 进入 skeleton），子图内部串行
- [ ] 先空跑：research/synthesize 节点先实现壳，不接证据，验证子图可恢复、可单步重试
- [ ] AgentState 新增字段：
  ```python
  planner_stage: Literal["", "skeleton", "research", "synthesize", "done"]
  planner_progress: dict   # {sections_total: 15, sections_research_done: 7, ...}
  ```

#### 6-B-2：SectionEvidence 数据结构 + 节级检索（节级 = `###` 粒度）

- [ ] `planning/schema.py` 新增 `EvidenceSnippet` / `EvidenceNote` / `SectionEvidence`
- [ ] `planner_research_node` 并发执行：每个节级单元跑 RAG + web_search（Planner 阶段不调 image_search）
  - 节级单元来自 skeleton 输出的 `sections[*]`（`###` 层）
  - 并发度由 `AGENT_PLANNER_RESEARCH_CONCURRENCY` 控制（默认 4）
- [ ] 检索结果写入 `SectionEvidence.source_pool`（不抽 claim，留给 synthesize）
- [ ] 每节完成后 emit `plan_progress` SSE 事件（见 6-B-3）

#### 6-B-3：synthesize 抽 claim + 流式 plan_progress

- [ ] `planner_synthesize_node` 对每节 source_pool 调 LLM 抽 `EvidenceNote`（claim + key_findings + snippets 绑定）
- [ ] 每节 visual_need 终稿同时在本节产出（type / purpose / query_candidates / insert_position / max_count）
- [ ] LLM 自评 `EvidenceNote.confidence ∈ [0, 1]`，低置信节标记 fallback 检索意图
- [ ] 新增 SSE 事件：
  - `plan_skeleton`（payload: 章节树骨架，先发给前端）
  - `plan_progress`（payload: `{section_id, stage, done, total}`）
  - `plan`（payload: 完整 Plan，含 evidence + visual_need）

#### 6-B-4：HITL 编辑模型（核心新能力）

- [ ] AgentState 新增：`plan_pending_edits: list`（待应用的用户编辑），`pending_research_sections: list[section_id]`（stale 列表）
- [ ] 前端编辑动作 → 后端 API：
  - `edit_section_title` / `edit_section_summary` → 标 `is_stale=True`
  - `add_section` → 创建空 evidence + 自动派生 retrieval_queries
  - `delete_section` → 移除该 evidence，其他节引用的 snippet 保留
  - `reorder_sections` → 不影响 evidence
  - `edit_evidence_directly` → 用户改 source/query → 锁定该节，后续不自动覆盖
- [ ] 用户点【开始生成】触发：planner 子图按 stale 列表只重跑 research + synthesize 节
- [ ] 大纲树展开显示 evidence 摘要（选项 A）：默认显示 URL 列表 + claim 数；点开见详细 EvidenceNote

#### 6-B-5：Writer 与证据契约

- [ ] `generate_report` prompt 改造：
  - 输入：`section_id`、`visual_assets[section_id]`、`evidence_notes[section_id]`、`source_pool[section_id]`
  - 硬约束：每个事实陈述后必须标 `[ref:snippet_id]`；不允许引用 source_pool 外内容
- [ ] 引用编号占位：Writer 输出 `[ref:sn_a12]`，Polisher 阶段统一替换为 `[1]/[2]/...`
- [ ] 图片插入位置由 Writer LLM 决定，参考 `visual_need.insert_position` 作 hint

#### 6-C：Polisher 节点（含 ref 校验）

- [ ] 新增 `nodes/polisher.py`，在 generate_report 完成后、END 前触发
- [ ] 全局图号重排（图1/图2/图3）
- [ ] 引用 `[ref:snippet_id]` → `[N]` 编号化 + 去重
- [ ] 删除未被引用的 source_pool 条目（不进最终参考文献）
- [ ] 校验：
  - 正文每个 ref 必须在某节 source_pool 中
  - 每张图都有对应正文引用（或正文 visual_need.insert_position 命中段）
  - 图号 / ref 编号无重复
- [ ] SSE 事件：`polish`（payload: `{adjusted_figures, dedup_refs, dropped_refs, issues}`）
- [ ] 不调 LLM，纯代码规则

#### 6-D：Visual Asset Agent（最远期，可选）

- [ ] 仅当 6-A/6-B/6-C 全部稳定后再评估
- [ ] 把 `image_search + diagram_gen + vlm_review + caption_gen + license_check` 组合为一个 sub-agent
- [ ] 触发条件：image_search 单 query 命中率持续低于阈值，需要多轮 query 改写策略

#### 其他原 Phase 6 项目（不变）

- [ ] Supervisor + 多 Agent（并行生成多种资源，如 PPT + 配套教案）
- [ ] L3 长期用户记忆（跨会话偏好学习）
- [ ] 前端展示 step 状态（pending / running / done / failed）— 前端任务

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
| Phase 6 起点 | image_search 工具 | 单文件可上线、激活已有 VisionReflector、风险低、解锁报告/PPT/教案三端 |
| 视觉规划位置 | 大纲（PlanStep.visual_need） | TVIR 核心思想：视觉证据必须在规划阶段就被纳入，避免事后硬塞 |
| Polisher 独立于 Reflect | 是 | reflect 是 per-tool 质量门，polisher 是 per-run 全局收口，两者目标不同 |
| Visual Asset Agent 是否做 | 后置（Phase 6-D） | 先有稳定工具再考虑包装；不在没数据的情况下预先抽象 |
| Planner 形态升级 | 单节点 → 子图（skeleton / research / synthesize） | evidence 完整版需要"检索 → 综合"两段 LLM 调用 + 多次工具调用，单节点无法承载；子图天然可恢复、可单步重试、可流式 |
| Evidence 完整性 | 完整版（claim + snippets + key_findings + confidence） | RAG 数据稀薄、web 是主要数据源 → 没有事实接地容易跑题；用户改大纲是核心需求 → 必须有结构化 evidence 才能局部重做 |
| Evidence 检索粒度 | 节级（`###`） | grounding 更准；用 plan_progress 流式 + 并发缓解耗时；用户可手动展开"深度证据"维持心智可控性 |
| Evidence 展示位置 | 大纲树展开（选项 A） | 大纲简洁，证据按需查看；与 HITL 编辑同一界面，编辑与审计闭环 |
| 视觉资产实例化时机 | 先集中搜，不边写边搜 | 与现有单次长生成的 `generate_report` 兼容；与 strict mode plan 兼容；HITL 重做粒度清晰 |
| image_search 是否进 Planner | 否，留给 Executor | Planner 已经要跑节级 RAG/web 检索 + LLM 综合，再加图片审查会突破可接受耗时；图属于"素材"非"前提" |
| HITL 重检触发 | 显式（用户点【开始生成】），非自动 | 用户编辑大纲过程中无延迟；重搜统一发生在确认点，心智模型清晰 |
| Planner 模型选择 | 同一模型（Qwen，沿用 `AGENT_PLANNER_*`） | 先验证整体形态，再决定 skeleton/synthesize 是否拆分模型；env 可单独切换 |
| 章节 id 策略 | `section_id` 稳定 id（如 `s_2_1`） | 大纲编辑时标题字符串会变；id 不变才能稳定关联 evidence / visual_assets |
| diagram_gen 是否纳入 6-A | 是，与 image_search 并列 | TVIR 消融数据显示图表/示意图比真实图片对最终质量影响更大；Mermaid 零外部依赖，工程成本极低 |
| Writer 引用机制 | `[ref:snippet_id]` 占位符，Polisher 阶段编号化 | Writer 不需要全局视野，只需引对 snippet；编号合并/去重交给 Polisher |
| Chart Generator（数据沙盒绘图） | 暂不做（不在 Phase 6 范围） | 工程量大、教育报告中纯数据图表占比低；6-D 之后视使用率再评估 |

---

## 十六、TVIR 启发的视觉证据 + 文本接地增强（Phase 6 详细设计）

> 设计来源：`docs/agent架构设计` + `docs/tvir总结` + TVIR 论文（nju-link.github.io/TVIR）  
> 核心定位：把"图片"和"事实证据"都从写完报告后的补救物，**升级为大纲阶段就规划好的报告组件**。  
> 关键变化：Planner 由"单节点产 JSON"升级为"三节点子图（skeleton → research → synthesize）"，承载视觉与文本双轨规划。

---

### 16.1 设计来源与核心理念

TVIR 论文 + `docs/tvir总结` 提供了三条原则，全部纳入 Phase 6：

1. **视觉内容前置规划**——大纲阶段就决定"哪节要图、要什么图、支撑什么观点、用什么 query 搜"，写完正文再补图必然位置错乱、图文不对齐。
2. **每节挂事实证据三元组**——`claim + source_url + key_findings`，Writer 在写本节时不能引入证据池外的事实，从源头消除幻觉。
3. **生成 ≠ 整理**——一次性长生成无法兼顾图号、引用编号、跨节去重，必须有独立的 Polisher 阶段做全局收口。

适配项目的两条本地化决策（区别于 TVIR 原始版）：

- **图片不在 Planner 阶段爬取**——只规划"要图的需求"，实际搜图由 Executor 跑 `image_search` step 完成。Planner 阶段已经要节级跑 RAG + web 检索 + LLM 抽 claim，再加 VLM 审图会突破耗时上限。
- **先集中搜后写作，不边写边搜**——与现有单次长生成的 `generate_report` 兼容；与 strict mode plan 兼容；与 HITL 重做粒度对齐。

---

### 16.2 当前状态盘点

| 维度 | 当前状态 | 问题 |
|---|---|---|
| `web_search_tool` 返回 | `links / imported / summary / sources` | 不返回 `images`，下游无图可用 |
| `VisionReflector.evaluate` | 读 `payload["images"]` 决定 retry | **死代码**——上游永远不给 images，恒走 "未找到图片" 的 `pass_with_warning` 分支 |
| `image_injector.inject_report_images_from_rag` | 仅注入 RAG 文档里嵌入的图 | 无外部图源；RAG 数据稀薄、课程资料几乎没图 |
| 大纲生成（`draft_outline`） | 只有 `chapters/sections` | 没有"哪节需要图"、"用什么事实做依据"的字段 |
| 报告写作 | 一次性长文，引用全靠 LLM 自觉 | 没有 polish 节点，图号 / 引用可能错乱；无证据池约束，易跑题 |
| 知识库现状 | RAG 数据稀薄 | **web 是主要数据源**，更需要结构化 evidence 防止幻觉 |
| HITL（用户改大纲） | 未实现，是核心需求之一 | 没有 stale 标记 + 局部重检机制 → 用户改完整个流程要从头跑 |
| Planner | 单节点一次 LLM 调用 | 无法承载"节级检索 + 综合"两段工作；无 checkpoint 中断/恢复粒度 |

**结论**：现有视觉链路有"半成品"（VisionReflector 已写好），证据链路完全空白；Planner 形态也需要升级才能承载新职责。

---

### 16.3 双轨规划：视觉资产 vs 文本证据

Phase 6 把"规划"明确拆成两条独立但同时执行的轨道：

| | 文本证据轨（evidence） | 视觉资产轨（visual） |
|---|---|---|
| Planner 阶段 | **检索 + 综合**（RAG + web → claim 抽取） | **只规划需求**（type / query_candidates / insert_position） |
| Executor 阶段 | 直接进入 Writer 使用 | 跑 `image_search` / `diagram_gen` 实例化 + VisionReflector 过滤 |
| Writer 阶段 | 硬约束：只用 evidence pool 的事实 | 软参考：按 visual_need.insert_position hint 决定位置 |
| Polisher 阶段 | `[ref:sn_id]` → `[N]` 编号化 + 删 orphan | 图号重排 + 校验"图与正文相互引用" |
| HITL 编辑响应 | 标 stale，用户点确认后局部重检 | 同上，但不重跑 `image_search`（用户可手动点"刷新配图"） |

**为什么 visual 不在 Planner 阶段实例化？**
- Planner 已经要跑节级 RAG/web 检索 + 综合 LLM 调用，耗时已经在 30-50s 量级，再加 VLM 审图会超过 1 分钟
- 图是"素材"，evidence 是"前提"——前者可在大纲展示后补，后者必须在 Writer 启动前到位
- HITL 编辑时：evidence 必须重做（因为它绑定 Writer 输入），图可以让用户决定要不要刷新

---

### 16.4 Phase 6-A：底层视觉资产工具

> **实施详情见** [`Phase6A_image_search_实施计划_2026-06-11.md`](./Phase6A_image_search_实施计划_2026-06-11.md)。本节为设计层视图（工具签名、provider 选项、与 reflect 集成）；实施层视图（具体代码 / 配置 / 测试 / 部署）见专项计划。
>
> 已锁定的实施决策（详见专项计划"二、关键决策"）：
> - Provider = SearXNG 自托管（需新部署）
> - image_search 不进 `_call_cache`（NEVER_CACHE 白名单，HITL 刷新可重搜）
> - `allow_image_search` capability 默认 False + step 级覆盖
> - `ImageAsset.proxy_url` 字段预留占位（6-A 不实现 proxy 后端）
> - 不支持 batch query（靠 ThreadPool 多 step 并发）

#### 16.4.1 image_search 工具

```python
# agent_tools/handlers/image_search.py

def handle_image_search(name: str, args: dict, ctx) -> dict:
    """
    args:
        query: str                # 搜索关键词
        count: int = 6            # 返回候选数量
        style: str = "any"        # "real" | "diagram" | "chart" | "any"（hint provider）
        license: str = "any"      # "any" | "free" | "cc"
        safe: bool = True         # 安全过滤

    returns payload:
        images: [
          {
            url: str,
            source_page: str,
            title: str,
            width: int, height: int,
            thumbnail: str,
            license: str | None,
            provenance: {
              provider: str,      # "searxng" | "bing" | "serpapi" | ...
              fetched_at: str,    # ISO timestamp
            }
          }
        ]
        trace: {provider, raw_count, filtered_count}
    """
```

**provider 优先级**：

1. **SearXNG**（自托管，零额度成本，无 API key 也能跑）
2. **Bing Image Search v7**（商用接入快，但需 API key 和额度）
3. **SerpApi Google Images**（最佳质量，成本最高）
4. **Pexels / Unsplash**（仅 "real" 风格高质量，覆盖面窄）

抽象层 `IMAGE_SEARCH_PROVIDER` env 切换，默认 SearXNG。

**工具内启发式过滤**（不到 reflect，工具自己拒绝低质量数据）：
- 宽 < 200 或高 < 200 丢弃
- URL 后缀非 `jpg/jpeg/png/webp` 丢弃
- 域名黑名单（pinterest / facebook 等需登录页）
- 同一 `source_page` 去重，每页最多 1 张
- thumbnail 缺失但主图 > 1MB 丢弃（带宽保护）

#### 16.4.2 diagram_gen 工具

```python
# agent_tools/handlers/diagram_gen.py

def handle_diagram_gen(name: str, args: dict, ctx) -> dict:
    """
    args:
        title: str            # 图标题
        kind: str = "flowchart"  # flowchart | sequence | class | state | er | mindmap
        intent: str           # 描述要表达的逻辑，LLM 据此生成 Mermaid DSL
        nodes_hint: list[str] | None  # 可选关键节点提示

    returns payload:
        mermaid: str          # Mermaid DSL 源码
        kind: str
        svg_url: str | None   # 后端 mermaid-cli 渲染得到的 SVG（若可用）
        provenance: {generated_at: str}
    """
```

- 内部用 Executor LLM（小型推理任务）生成 Mermaid DSL
- 若后端集成 mermaid-cli，可同步渲染 SVG 并存到 `storage/diagrams/`，返回 URL
- 没集成时返回纯 DSL，前端用 mermaid.js 渲染（教师页已有 mermaid 支持）

**为什么把 diagram_gen 拉进 Phase 6-A**：
- `docs/tvir总结` §8 消融数据：去掉 Chart Gen 模块导致 Overall -10 分，去掉 Image Searcher 只 -1.4 分——视觉影响主要来自结构化图
- 教育场景里"流程图 / 结构图 / 知识树"远比"真实摄影图"高频
- Mermaid 零外部依赖、可编辑、版权干净，工程成本仅 image_search 的 1/3

#### 16.4.3 ToolMeta 与 Reflect 接入

```python
# agent_tools/tool_meta.py
"image_search": ToolMeta(parallel_safe=True, mutates_state=False, depends_on=[]),
"diagram_gen":  ToolMeta(parallel_safe=True, mutates_state=False, depends_on=[]),

# reflection/vision.py
_APPLIES_TO = {"image_search", "web_search", "rag_search"}  # diagram_gen 不审，结构正确即可

# web_search payload 不再塞 "images"
```

#### 16.4.4 验收

- 端到端生成一份报告，正文出现至少 1 张外部搜索图 + 1 张 Mermaid 流程图
- 报告完成后 `tool_exchange` 中 `image_search` step 的 raw vs filtered 比例可见（如 6→3 张）
- VisionReflector 实际触发并 emit `reflect` SSE（不再恒 pass）

---

### 16.5 Phase 6-B-1：Planner 子图骨架

#### 16.5.1 子图结构

```
原 Planner（单节点）：
   planner_node ──► graph 主流

新 Planner（子图）：
   planner_skeleton_node            （1 次 LLM，~3s）
        ↓ skeleton SSE
   planner_research_node            （N 节并发 RAG + web，~10-20s）
        ↓ plan_progress SSE × N
   planner_synthesize_node          （N 节并发 claim 抽取，~15-25s）
        ↓ plan SSE（完整 plan）
   出口 ──► 主流 executor_node
```

每个子节点都是独立 LangGraph 节点，享受 checkpoint：
- 用户中途打断可恢复
- HITL 编辑后只重跑 stale 节，无需重跑 skeleton
- 失败可单步重试（如某节 web_search 超时不影响其他节）

#### 16.5.2 文件结构变化

```
app/chat/runtime/
├── nodes/
│   ├── planner.py            # 旧：单节点；新：保留 planner_node 作为子图入口
│   ├── planner_skeleton.py   # 新增
│   ├── planner_research.py   # 新增
│   ├── planner_synthesize.py # 新增
│   └── ...
├── planning/
│   ├── schema.py             # 扩展 EvidenceSnippet / EvidenceNote / SectionEvidence / VisualNeed
│   ├── prompts.py            # 拆分为 skeleton_prompt / synthesize_prompt
│   └── retrieval.py          # 新增：节级并发检索调度器
```

#### 16.5.3 路由策略

```python
def _route_entry(state):
    if state.get("planner_stage") == "skeleton":
        return "planner_skeleton"
    if state.get("planner_stage") == "research":
        return "planner_research"
    if state.get("planner_stage") == "synthesize":
        return "planner_synthesize"
    if state["current_plan"] is None or state["reflect_verdict"] == "replan":
        return "planner_skeleton"  # 首轮入口
    if state.get("pending_research_sections"):
        return "planner_research"  # HITL 编辑后局部重做入口
    return "executor"
```

#### 16.5.4 6-B-1 验收

- 不接证据时三节点串行可跑通
- AgentState.planner_stage 在 SqliteSaver 中持久化
- 模拟"skeleton 后中断重启" → 从 research 恢复，不重跑 skeleton

---

### 16.6 Phase 6-B-2：SectionEvidence 数据结构与节级检索

#### 16.6.1 完整数据结构

```python
# planning/schema.py

@dataclass
class EvidenceSnippet:
    snippet_id: str           # 稳定 id（hash 或自增），Writer 引用用
    source_url: str
    source_type: Literal["rag", "web"]
    chunk_id: str | None      # RAG 命中时填
    title: str | None
    text: str                 # 200-500 字原文片段，证据可追溯
    retrieved_at: str         # ISO timestamp
    retrieval_query: str      # 用过的 query，调试和重检用

@dataclass
class EvidenceNote:
    note_id: str
    claim: str                # Planner 抽取的命题
    key_findings: str         # 一两句要点提炼
    snippets: list[str]       # 支撑这条 claim 的 snippet_id 列表
    confidence: float = 1.0   # Planner LLM 自评，<0.6 标记 fallback

@dataclass
class SectionEvidence:
    section_id: str           # 稳定 id（如 "s_2_1"）
    retrieval_queries: list[str]    # skeleton 阶段产出的初始 query 集合
    source_pool: list[EvidenceSnippet]   # research 阶段填
    notes: list[EvidenceNote]            # synthesize 阶段填
    is_stale: bool = False    # HITL 编辑后置 True
    locked: bool = False      # 用户直接编辑过 evidence → 锁定，不被自动覆盖

@dataclass
class VisualNeed:
    required: bool
    type: Literal["real", "diagram", "chart", "any"] = "any"
    purpose: str = ""                # "帮助理解 RAG 管线"
    query_candidates: list[str] = field(default_factory=list)
    insert_position: str = ""        # "本节流程介绍之后"
    max_count: int = 1

@dataclass
class PlanStep:
    # 原有字段...
    section_id: str | None = None    # **新增稳定 id**，与 Evidence 关联
    visual_need: VisualNeed | None = None
    evidence: SectionEvidence | None = None
```

#### 16.6.2 检索粒度：节级（`###`）

skeleton 阶段输出的章节树：

```
## 一、RAG 是什么
   ### 1.1 定义
   ### 1.2 与传统 LLM 对比
## 二、技术流程
   ### 2.1 检索阶段
   ### 2.2 重排阶段
   ### 2.3 生成阶段
## 三、应用案例
   ### 3.1 教育领域
   ### 3.2 客服领域
```

`planner_research_node` 对**每个 `###`**（含没有子节的 `##`）独立跑：
```python
for section in skeleton.flatten_sections():       # 节级展开
    queries = section.retrieval_queries          # skeleton 给出 2-3 个 query
    rag_results = await rag_search_concurrent(queries, top_k=5)
    web_results = await web_search_concurrent(queries)
    snippets = _normalize_to_snippets(rag_results + web_results)
    section.evidence.source_pool = snippets
    emit("plan_progress", {section_id, stage: "research", done: ++i, total: N})
```

并发度：`AGENT_PLANNER_RESEARCH_CONCURRENCY=4`（env 可调）。

#### 16.6.3 检索结果归一化

无论 RAG 还是 web，统一转 `EvidenceSnippet`：
- RAG chunk → `source_type="rag", chunk_id=..., text=chunk.text`
- web 结果 → `source_type="web", chunk_id=None, source_url=link, text=excerpt`
- 文本超 500 字截断；< 50 字丢弃（噪声）

#### 16.6.4 6-B-2 验收

- 跑一份 5 章 15 节的报告规划，每节 source_pool 不空（除非真无资料）
- 总 Planner 耗时 < 50s（节级并发到位）
- AgentState.planner_progress.sections_research_done 流式可见

---

### 16.7 Phase 6-B-3：synthesize 抽 claim + 流式 SSE

#### 16.7.1 synthesize 节点行为

```python
def planner_synthesize_node(state):
    skeleton = state["current_plan_draft"]
    for section in skeleton.flatten_sections():
        pool = section.evidence.source_pool
        # 单节级 LLM 调用：输入 source_pool + section.summary，输出 N 个 EvidenceNote + visual_need 终稿
        result = synthesize_llm(SECTION_SYNTHESIZE_PROMPT.format(
            section_title=section.title,
            section_summary=section.summary,
            source_pool=pool,
        ))
        section.evidence.notes = result.notes
        section.visual_need = result.visual_need
        emit("plan_progress", {section_id, stage: "synthesize", done: ++i, total: N})

    plan = _materialize_plan(skeleton)            # 转 PlanStep 列表
    emit("plan", plan.to_dict())
    return {"current_plan": plan.to_dict(), "planner_stage": "done", ...}
```

#### 16.7.2 synthesize prompt 模板（要点）

```
你正在为以下章节抽取事实证据并规划视觉需求：
  章节标题：{section_title}
  章节摘要：{section_summary}

可用素材池（source_pool，编号 [sn_a]、[sn_b]...）：
  [sn_a] 来源: ..., 节选: "..."
  [sn_b] 来源: ..., 节选: "..."
  ...

任务 1：抽取 2-5 个事实 claim，每个 claim 必须能在素材池中找到至少 1 条直接支撑
        每个 claim 输出 {claim, key_findings, snippet_ids: [...], confidence: 0-1}
        confidence 反映"素材是否充分、清晰、跨源一致"

任务 2：判断本节是否需要视觉资产
        - 概念定义类 → required=false
        - 流程/结构/对比类 → type="diagram"
        - 数据趋势类 → type="chart"
        - 人物/场景/历史 → type="real"
        若 required=true，给 2-3 个 query_candidates 和 insert_position

严格输出 JSON：
{
  "notes": [...],
  "visual_need": {...}
}
```

#### 16.7.3 SSE 事件新集

| 事件 | 触发 | payload | 用途 |
|---|---|---|---|
| `plan_skeleton` | skeleton 完成 | `{sections: [{section_id, title, summary, children}]}` | 前端立即渲染章节树骨架 |
| `plan_progress` | research / synthesize 每节完成 | `{section_id, stage, done, total}` | 进度条 |
| `plan` | synthesize 完成 | 完整 Plan（含 evidence + visual_need） | 前端激活 HITL 编辑 |
| `plan_research_done` | 单节 research 完成 | `{section_id, snippets_count}` | 大纲树该节展开时显示证据数 |
| `plan_synthesize_done` | 单节 synthesize 完成 | `{section_id, notes_count, visual_required}` | 同上 |

#### 16.7.4 6-B-3 验收

- 5 章 15 节场景下，前端在 5s 内收到 plan_skeleton，10-15s 后开始有 plan_progress 流入
- 完整 plan 事件携带 evidence_notes 非空，confidence 字段存在
- LLM 拒绝引用 source_pool 外内容（prompt 工作正常）

---

### 16.8 Phase 6-B-4：HITL 编辑模型

#### 16.8.1 AgentState 新增

```python
plan_pending_edits: list[dict]          # 用户提交但未应用的编辑动作
pending_research_sections: list[str]    # is_stale=True 的 section_id
locked_sections: list[str]              # 用户手动编辑过 evidence 的节
```

#### 16.8.2 用户编辑动作 → 后端响应矩阵

| 用户动作 | 路由 | 对 evidence 的影响 | 是否等待 |
|---|---|---|---|
| 改 section_title（措辞） | `PATCH /plan/section/{id}` | 不重检 | 否 |
| 改 section_summary（范围变） | 同上 | `is_stale=True` | 否（延迟到确认） |
| 改 retrieval_queries | 同上 | `is_stale=True` | 否 |
| 拖动顺序 | `PATCH /plan/reorder` | 不变 | 否 |
| 删除章节 | `DELETE /plan/section/{id}` | 该节 evidence 丢弃；snippets 若被他节引用则保留在共享 pool | 否 |
| 新增章节 | `POST /plan/section` | 创建空 evidence + 自动派生 query | 否（标 stale） |
| 直接改 evidence（删 source / 加 URL / 改 claim） | `PATCH /plan/section/{id}/evidence` | 该节 `locked=True` | 否 |
| 用户点【刷新该节证据】 | `POST /plan/section/{id}/research` | 强制 stale 即使 locked | **是**（同步等待） |
| 用户点【开始生成】 | `POST /plan/confirm` | 触发对所有 stale 节并发重 research + synthesize | **是** |

#### 16.8.3 确认重检流程

```
用户点【开始生成】
    ↓
后端检查 pending_research_sections
    ├─ 为空 → 直接进入主流 executor
    └─ 非空 → planner_research_node(限定 sections=stale 列表)
                ↓
              planner_synthesize_node(同样限定)
                ↓
              清空 pending_research_sections
                ↓
              进入主流 executor
```

#### 16.8.4 大纲树展开显示 evidence（选项 A）

前端 UI 设计要点：
- 大纲树默认折叠状态：只显示 `## / ###` 标题
- 节点右侧角标：`📎 3` 表示有 3 条 evidence note；`🖼️ ✓` 表示视觉资产已规划
- 点击节点 → 抽屉面板展开，显示：
  - claim 列表（可编辑）
  - source_pool（URL + 来源标题 + 摘要，可删除）
  - visual_need（type + purpose + query_candidates，可编辑）
  - 操作按钮：【刷新本节证据】【锁定本节（不被自动覆盖）】

#### 16.8.5 6-B-4 验收

- 用户改 3 节摘要 → 3 节角标显示"⚠ 已变更，待刷新"
- 用户点【开始生成】→ 后端只对这 3 节并发重跑，其他节不动
- 锁定节即使 is_stale 也不被自动覆盖，除非用户显式点【刷新】

---

### 16.9 Phase 6-B-5：Writer 与证据契约

#### 16.9.1 generate_report 输入扩展

```python
generate_report(
    confirmed_outline: dict,
    evidence_by_section: dict[str, SectionEvidence],   # section_id → evidence
    visual_assets_by_section: dict[str, list[ImageAsset]],  # section_id → 已通过 reflect 的图
    style_guide: str,
)
```

#### 16.9.2 Writer prompt 契约（每节）

```
当前节：{section_title}
节摘要：{section_summary}

【可用事实】（必须只用这些，编号引用）
  [sn_a] (来源 ..., 节选 "...")
  [sn_b] (...)
  ...

【核心 claims】（围绕这些展开）
  - {claim_1}（支撑：sn_a, sn_b）
  - {claim_2}（支撑：sn_c）

【可用视觉资产】（按需选择并插入 Markdown 图片语法）
  - 图 A: {url_1}, 类型 diagram, 建议位置"流程介绍之后"
  - 图 B: {url_2}, 类型 real

【输出要求】
1. 每个事实陈述后必须标注 [ref:sn_a] 类引用占位符
2. 不允许出现 source_pool 之外的事实陈述
3. 图片用 `![alt](url) <!-- visual_id=A -->` 格式插入，alt 为图注
4. 若 claim 无足够素材支撑，明确写"目前可查资料有限"，不要编造
```

#### 16.9.3 输出后处理（Polisher 前）

- Writer 输出含 `[ref:sn_id]` 和 `<!-- visual_id=X -->` 标记的 Markdown
- 后处理把这些标记保留交给 Polisher 阶段统一编号化

#### 16.9.4 6-B-5 验收

- 生成一份报告：grep `[ref:sn_` 所有引用都能在 evidence_by_section 中找到对应 snippet
- 强制错误测试：往 Writer prompt 注入"不存在"的事实要求，Writer 拒绝或明确标"资料有限"

---

### 16.10 Phase 6-C：Polisher 节点（含 ref 校验）

#### 16.10.1 触发时机

```
executor_node 判断"无 tool_calls + 内容产物已完成 + resource_type=report"
   ↓
polisher_node
   ↓
END
```

#### 16.10.2 节点职责（纯规则，不调 LLM）

```python
def polisher_node(state):
    md = _extract_final_markdown(state)
    evidence_index = _build_evidence_index(state["current_plan"])  # snippet_id → SnippetMeta
    visual_index   = _build_visual_index(state["current_plan"])    # visual_id → ImageAsset

    md, ref_stats = _normalize_refs(md, evidence_index)
    # [ref:sn_a] → [1]; 全局去重，按首次出现排序；删未被引用 snippet
    md, fig_stats = _normalize_figures(md, visual_index)
    # <!-- visual_id=A --> → 图N，按首次出现排序
    refs_section  = _build_references_section(md, evidence_index)  # 末尾参考文献
    md += "\n\n## 参考文献\n" + refs_section

    issues = _consistency_check(md, evidence_index, visual_index)
    # 1. 正文 ref 在 evidence_index 必须存在（理论上不可能失败，是 sanity check）
    # 2. 每个 visual_id 都在正文出现至少 1 次
    # 3. 图号 / ref 编号无重复无跳号

    writer({"type": "polish", "payload": {
        "adjusted_figures": fig_stats,
        "normalized_refs": ref_stats,
        "issues": issues,
    }})
    return {"messages": [_replace_final_message(state, md)]}
```

#### 16.10.3 与 Reflect 的边界（更新）

| 维度 | Reflect | Polisher |
|---|---|---|
| 触发粒度 | 每个 tool 执行后 | 整轮产物完成后 |
| 可返回的 verdict | pass / retry / replan / abort | 无（仅整理） |
| 修改对象 | filtered_data（中间结果） | 最终 markdown + 引用 / 图号 |
| 是否调 LLM | 可能（LLMReflector） | 否 |
| 处理 evidence | 否（evidence 由 Planner 产） | 是（normalize refs + 生成参考文献节） |
| Phase | 2-C / 3 完成 | 6-C 新增 |

#### 16.10.4 6-C 验收

- 一份报告内 `[ref:xxx]` 全部被替换为 `[N]`，且与文末参考文献编号一致
- 图号顺序与正文出现顺序一致，无重复
- 故意删除某图的 `<!-- visual_id=X -->` 标记 → issues 中出现 "visual_id X never cited"

---

### 16.11 AgentState 完整变更清单

```python
# graph/state.py 变更

class AgentState(TypedDict):
    # ── 原有字段 ──
    messages: list
    tool_exchange: list
    fallback_reason: str
    active_draft_outline: dict | None
    pending_tasks: list
    current_plan: dict | None
    plan_step_index: int
    plan_mode: str
    reflect_verdict: str
    reflect_hint: str
    reflect_filtered: dict
    retry_counts: dict

    # ── Phase 6 新增 ──

    # Planner 子图状态
    planner_stage: Literal["", "skeleton", "research", "synthesize", "done"]
    planner_progress: dict       # {sections_total: N, research_done: K, synthesize_done: M}
    current_plan_draft: dict | None  # skeleton 阶段中间产物

    # HITL 编辑状态
    plan_pending_edits: list             # [{action, section_id, payload, ts}]
    pending_research_sections: list[str] # is_stale 节列表
    locked_sections: list[str]           # 用户手动编辑过 evidence 的节

    # 视觉资产累积（跨 step 流转）
    visual_assets: dict[str, list]       # section_id → [ImageAsset]
```

---

### 16.12 SSE 事件完整变更清单

| 事件类型 | 触发节点 | payload | Phase |
|---|---|---|---|
| `plan_skeleton` | planner_skeleton_node | `{sections: [...]}` | 6-B-1 |
| `plan_progress` | research / synthesize | `{section_id, stage, done, total}` | 6-B-3 |
| `plan_research_done` | planner_research_node | `{section_id, snippets_count}` | 6-B-3 |
| `plan_synthesize_done` | planner_synthesize_node | `{section_id, notes_count, visual_required}` | 6-B-3 |
| `plan` | planner_synthesize_node | 完整 Plan（含 evidence + visual_need） | 6-B-3（替换原 plan） |
| `plan_edit_applied` | HITL API | `{action, section_id, is_stale}` | 6-B-4 |
| `polish` | polisher_node | `{adjusted_figures, normalized_refs, issues}` | 6-C |

---

### 16.13 端到端示例（生成"RAG 技术发展"教学报告）

```
用户：「帮我生成一份 RAG 技术发展的教学报告，要配图」
  ↓ should_plan() = True
planner_skeleton_node：
  emit plan_skeleton SSE
  ── 章节树：3 章 9 节，每节带 summary + retrieval_queries + 初步 visual_need
  ↓ planner_stage = "research"
planner_research_node：（并发度 4）
  for s in 9 sections:
    rag + web_search(queries) → snippets
    emit plan_progress {stage:"research", done:1..9, total:9}
    emit plan_research_done {section_id, snippets_count}
  ↓ planner_stage = "synthesize"
planner_synthesize_node：（并发度 4）
  for s in 9 sections:
    LLM 抽 claim + key_findings + 终稿 visual_need
    emit plan_progress {stage:"synthesize", done:1..9, total:9}
  emit plan SSE（完整 plan，evidence + visual_need 全员就位）
  ↓ planner_stage = "done"

【前端展示完整大纲 + evidence 摘要（角标 📎 N）】
【HITL 阶段：用户改了第 2.2 节的 summary】
  ↓ POST /plan/section/s_2_2 with new summary
  ↓ pending_research_sections = ["s_2_2"]
  ↓ section.is_stale = True，前端显示 ⚠

用户点【开始生成】
  ↓ planner_research_node（仅 s_2_2）
  ↓ planner_synthesize_node（仅 s_2_2）
  ↓ pending_research_sections = []
  ↓ executor_node

executor 按 plan 推进：
  step_image_1: image_search(query="RAG architecture diagram", style="diagram")
    → reflect: VisionReflector 6→3 张过滤
    → state.visual_assets["s_2_1"] = [3 张]
  step_diagram_1: diagram_gen(title="RAG 工作流程", kind="flowchart", ...)
    → state.visual_assets["s_2_1"].append({mermaid: "...", svg_url: "..."})
  step_image_2: image_search(query="vector database", ...)
    → state.visual_assets["s_3_1"] = [2 张]
  step_generate_report: generate_report(
      confirmed_outline=...,
      evidence_by_section=...,
      visual_assets_by_section=state.visual_assets,
    )
    → 输出 Markdown 含 [ref:sn_a]、<!-- visual_id=A --> 标记

polisher_node：
  [ref:sn_*] → [1]/[2]/[3]... 编号化
  <!-- visual_id=* --> → 图1/图2/图3...
  生成 ## 参考文献 节
  consistency_check 通过
  emit polish SSE
  ↓
END
前端：完整报告 + plan 状态全 done + polish 总结徽章
```

---

### 16.14 实施顺序与工作量

| 阶段 | 内容 | 工作量 | 依赖 |
|---|---|---|---|
| 6-A-1 | image_search 工具 + provider 抽象 + 启发式过滤 | 1.5 天 | — |
| 6-A-2 | diagram_gen 工具（Mermaid DSL） + 后端渲染（可选） | 1 天 | — |
| 6-A-3 | VisionReflector applies_to 扩展 + 端到端冒烟 | 0.5 天 | 6-A-1 |
| 6-B-1 | Planner 子图骨架（skeleton/research/synthesize 空跑） | 2 天 | — |
| 6-B-2 | SectionEvidence + 节级并发 RAG/web 检索 | 2 天 | 6-B-1 |
| 6-B-3 | synthesize claim 抽取 + 流式 plan_progress SSE | 2 天 | 6-B-2 |
| 6-B-4 | HITL API + stale 标记 + 大纲树展开 + 重检触发（含前端） | 3-4 天 | 6-B-3 |
| 6-B-5 | Writer prompt 改造 + 引用占位符 + visual_assets 注入 | 2 天 | 6-B-3, 6-A-3 |
| 6-C | Polisher 节点（refs 编号化 + 图号 + 参考文献节 + consistency） | 2 天 | 6-B-5 |

**总计**：约 16-17 工程日（含前端 HITL 部分）。
**最小可上线切片**（先体验视觉证据效果）：6-A 全 + 6-B-5 简化版（暂不改 Writer 强约束，仅注入 visual_assets）= 4 天。
**完整 evidence 接地**：再 +12 天。

---

### 16.15 关键非目标

- ❌ **不要在 Planner 阶段调 image_search**——图属于素材，evidence 才是前提；混入会让 Planner 超过 1 分钟
- ❌ **不要做 Chart Generator（数据搜索 + Python 沙盒绘图）**——教育报告中纯数据图占比低，工程量大，留到 6-D 之后视使用率再评估
- ❌ **不要为了"看起来像 Agent"把 image_search 拆 sub-agent**——Planner 已经做了规划决策，再嵌一层是重复
- ❌ **不要让 polisher 调 LLM**——和 reflect 职责重叠，纯规则才能稳定收口
- ❌ **不要做"边写边搜"流式生成**——和现有 `generate_report` 单次生成不兼容，HITL 重做粒度也乱
- ❌ **不要让 Planner 子图自动重检所有 stale**——必须用户显式点确认，否则编辑过程频繁触发后端 LLM 调用
- ❌ **不要在 evidence 之外做事实校验**——Writer 已被 prompt 约束只用 source_pool，Polisher 只做 sanity check 不做语义验证
