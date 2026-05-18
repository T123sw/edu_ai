# P4-A ReAct Agent化 — 设计规格文档（修订版 v3）

**日期**：2026-05-18（最终修订）  
**状态**：待审查  
**依赖**：P0-A/B/C、P1-A/B/C、P2-A/B、P3-A（均已完成）  
**预计工期**：7~10天

---

## 1. 核心设计理念

**对话永远是对话。Agent 自己完成信息收集和大纲确认，Workflow 只负责生成。**

用户从不"进入工作流"。所有信息收集、大纲预览、修改确认，全部发生在自然对话里。当 Agent 判断条件成熟，调用生成工具触发后台任务，对话继续。

---

## 2. 两条路径并存

| 路径 | 触发方式 | 谁编排对话 | Workflow 做什么 |
|------|---------|-----------|----------------|
| **按钮路径**（保留） | 前端按钮设置 action_hint | Workflow 状态机（现有逻辑不变） | 完整：收集→大纲→确认→生成 |
| **Agent 路径**（新增） | 自然语言对话 | ReAct Agent | **仅生成**：跳过收集和大纲步骤 |

按钮路径完全不改动。Agent 路径是新增的，Workflow 新增 fast-path 跳过收集/大纲阶段。

---

## 3. Agent 路径的对话流程

### 示例 A：报告生成

```
用户：帮我写报告

Agent：您想写什么主题？大概多长？
  （缺少 subject，Agent 直接追问，不调任何工具）

用户：量子计算，综述类，5000字左右

Agent：好的，这是我规划的报告结构：

       一、量子计算基础原理
       二、量子比特与量子门
       三、当前主流技术路线
       四、应用场景与现状
       五、挑战与未来方向

       您想调整方向吗？
  （Agent 内联生成大纲作为普通对话回复，不调工具）

用户：在第三节后加一节量子纠错

Agent：已调整。现在开始后台生成报告...
  （Agent 看到对话历史中有大纲+用户确认，调用 generate_report）
  [调用 generate_report(subject="量子计算", focus="综述",
                        confirmed_outline="...", length_hint="5000字")]
  → 返回 task_id → 前端开始轮询
```

### 示例 B：练习题（无大纲步骤）

```
用户：出 10 道 Python 基础题，中等难度，选择题为主

Agent：好的，正在后台生成...
  （信息已足够，直接调用 generate_quiz，无需大纲）
  [调用 generate_quiz(subject="Python基础", question_count=10,
                      difficulty="medium", question_types=["choice"])]
```

### 示例 C：信息不足时追问

```
用户：帮我做个课件

Agent：您想做什么主题的课件？面向哪个年级的学生？
  （Agent 追问，不调工具）

用户：高中物理，波动光学

Agent：这是课件大纲：
       第1页：波动光学概述
       第2页：光的干涉现象
       ...（共12页）
       需要调整吗？

用户：可以

Agent：开始后台生成 PPT...
  [调用 generate_ppt(topic="高中物理波动光学",
                     confirmed_outline="...", slide_count=12)]
```

---

## 4. 架构变化

### 4.1 整体数据流

```
用户消息
    │
    └─ MainOrchestrator.dispatch_stream()
           │
           ├─ [Level 1] action_hint 确定路由 → Workflow 完整路径（不变）
           │
           └─ [Level 2] ReActAgent.run_stream(request, snapshot)
                  │
                  └─ DeepSeek v4-flash（stream_chat_with_tools）
                         │
                         ├─ 无工具调用：直接流式输出
                         │   （追问、大纲展示、普通回答）
                         │
                         └─ 调用 generate_* 工具：
                                克隆 request + 注入 confirmed_outline
                                → submit_workflow_task（Workflow fast-path）
                                → task_id → task_submitted 事件
```

### 4.2 Agent 系统提示（关键）

Agent 的行为由系统提示指导，不需要代码实现：

```
你是一个教学资源助手。当用户请求生成报告/PPT/教案/练习题时：

【信息收集】
1. 如果缺少必要信息（主题/课题），先通过自然对话追问，不要调用工具
2. 一次最多问 2 个问题，不要列清单式追问

【大纲展示】（报告/PPT/教案需要，练习题不需要）
3. 信息充足后，先以普通对话方式展示大纲，询问是否需要调整
4. 大纲以 markdown 格式输出，清晰易读
5. 用户确认后（说"可以"/"好"/"开始"等），调用对应 generate_* 工具

【工具调用】
6. 调用 generate_* 时，将对话中已确认的大纲通过 confirmed_outline 参数传入
7. 用户明确要求生成时才调用工具，讨论话题时不调用
8. 调用完成后，告知用户任务已提交，正在后台处理
```

### 4.3 Workflow 新增 fast-path

每个 Workflow runtime 入口处新增判断：

```python
def run(self, request, snapshot, decision):
    gathered = dict(getattr(request, "gathered_context", {}) or {})
    confirmed_outline = gathered.get("confirmed_outline", "")
    subject_or_topic = gathered.get("subject") or gathered.get("topic", "")

    # fast-path：agent 已完成收集和确认，跳过 workflow 内部的收集/大纲阶段
    if confirmed_outline and subject_or_topic:
        return self._run_generating_fast(
            request=request,
            snapshot=snapshot,
            subject=subject_or_topic,
            confirmed_outline=confirmed_outline,
            extra=gathered,
        )

    # 原有完整路径（按钮触发时走这里）
    return self._run_full_interactive(request, snapshot, decision)
```

**`_run_generating_fast()` 各 workflow 的含义：**

| Workflow | fast-path 做什么 |
|----------|----------------|
| report | 跳过 context_organizer / readiness_judge / soft_confirm / outlining，直接用 confirmed_outline 生成正文 |
| ppt | 跳过收集/大纲确认，将 confirmed_outline 转为 PptOutline 结构，提交 html2ppt job |
| lesson_plan | 跳过收集/大纲确认，直接用 confirmed_outline 生成教案正文 |
| quiz | 无大纲步骤，直接生成（不需要 confirmed_outline） |

---

## 5. 工具集（最终版，7个）

### 5.1 工具清单

| # | 工具名 | 类型 | 调用时机 | 必填参数 | 可选参数 |
|---|--------|------|---------|---------|---------|
| 1 | `rag_search` | 同步检索 | 用户引用知识库时 | `query` | `top_k=5` |
| 2 | `web_search` | 同步检索 | 需要实时信息时 | `query` | — |
| 3 | `draft_outline` | 同步 LLM | 信息充足后、生成前 | `resource_type`, `subject` | `focus`, `constraints`, `slide_count`, `grade`, `duration_minutes` |
| 4 | `generate_report` | 异步后台 | 用户确认大纲后 | `subject`, `confirmed_outline` | `focus`, `length_hint` |
| 5 | `generate_ppt` | 异步后台 | 用户确认大纲后 | `topic`, `confirmed_outline` | `slide_count=10` |
| 6 | `generate_lesson_plan` | 异步后台 | 用户确认大纲后 | `subject`, `confirmed_outline` | `grade`, `duration_minutes=45` |
| 7 | `generate_quiz` | 异步后台 | 用户明确要求时（无大纲步骤） | `subject` | `question_count=10`, `difficulty="medium"`, `question_types=[]` |

### 5.2 draft_outline 详细设计

`draft_outline` 是 P4-A 新增的关键工具，承担"大纲生成"职责，从 generate_* 工具中拆出来，让 agent 可以独立控制这一步：

```python
draft_outline(
    resource_type: str,    # "report" | "ppt" | "lesson_plan"
    subject: str,          # 主题/课题
    focus: str = "",       # 报告重点方向
    constraints: str = "", # 用户的补充约束（如"加一节量子纠错"）
    slide_count: int = 10, # PPT 页数
    grade: str = "",       # 教案年级
    duration_minutes: int = 45,  # 教案课时
) -> {"outline_markdown": str}
```

**实现**：调用 `agent_gateway`（DeepSeek v4-flash）同步 LLM 生成，按 resource_type 选择不同的 outline prompt。返回 Markdown 格式大纲文字，agent 将其直接插入对话回复展示给用户。

**Agent 使用模式**：
```
agent 调用 draft_outline(resource_type="report", subject="量子计算")
  → 得到 outline_markdown: "# 一、量子计算基础\n# 二、..."
  → agent 把大纲嵌入自己的回复文字中展示给用户
  → 用户确认后下一轮 agent 调用 generate_report(confirmed_outline=outline_markdown)
```

### 5.3 工具调用次数（典型场景）

| 场景 | 工具调用序列 | 次数 |
|------|------------|------|
| 练习题直接生成 | `generate_quiz` | 1 |
| 报告/PPT/教案生成（信息充足） | `draft_outline` → `generate_*` | 2 |
| 先检索再生成 | `rag_search` → `draft_outline` → `generate_*` | 3 |
| 用户修改大纲再生成 | `draft_outline` → （用户修改）→ `draft_outline` → `generate_*` | 3 |
| 检索 + 修改大纲 | `rag_search` → `draft_outline` → `draft_outline` → `generate_*` | 4 |

**`REACT_MAX_STEPS` 调整为 4**（原 3）以覆盖检索+修改大纲的场景。

### 5.4 工具描述（驱动 LLM 决策）

精确的工具描述是 agent 行为正确性的核心（已通过 DeepSeek 实测验证）：

```python
draft_outline:
  "当你已收集到足够信息（主题明确），需要生成结构化大纲供用户确认时调用。
   调用后将返回的大纲展示给用户，询问是否需要调整。
   resource_type 填写 'report'/'ppt'/'lesson_plan'。"

generate_report:
  "仅在用户已确认大纲内容后调用（必须传入 confirmed_outline）。
   这会触发后台报告生成任务，不可中断，确认前不要调用。"

generate_ppt:
  "仅在用户已确认PPT大纲后调用（必须传入 confirmed_outline）。
   会触发后台PPT生成任务。"

generate_lesson_plan:
  "仅在用户已确认教案大纲后调用（必须传入 confirmed_outline）。"

generate_quiz:
  "当用户明确要求生成练习题/习题/测试题时直接调用（无需大纲步骤）。
   从对话中提取主题、题量、难度后调用。"

rag_search:
  "当用户提到'我的资料/知识库/上传的文件'时调用。通用知识不调用。"

web_search:
  "当用户需要实时/最新信息时调用（'今天/最新/当前'为典型信号）。"
```

### 5.5 capability 门控

- `capability.allow_rag = False` → `rag_search` 不加入 TOOL_SCHEMAS（模型看不见）
- `capability.allow_web = False` → `web_search` 不加入 TOOL_SCHEMAS

---

## 6. 新增 / 修改文件清单

### 6.1 新增文件

#### `app/chat/runtime/agent_tools.py`

```python
TOOL_SCHEMAS: list[dict]  # 6 个工具的 JSON Schema

def build_tool_schemas(capability) -> list[dict]:
    # 根据 capability 动态决定是否包含 rag_search / web_search
    ...

def execute_tool(name, args, *, rag_retriever, web_retriever,
                 workflow_registry, background_runner, request, snapshot) -> dict:
    # rag_search / web_search → 返回检索结果
    # generate_* → _execute_generate_tool()
    ...

def _execute_generate_tool(tool_name, args, *, workflow_registry,
                            background_runner, request, snapshot) -> dict:
    aug_request = _clone_request(request)
    aug_request.gathered_context = {
        **(getattr(request, "gathered_context", {}) or {}),
        **args,  # 包含 subject/topic/confirmed_outline 等
    }
    aug_request.action_hint = _TOOL_TO_ACTION_HINT[tool_name]
    task_id = background_runner.submit_workflow_task(
        workflow=workflow_registry[_TOOL_TO_WORKFLOW[tool_name]],
        request=aug_request,
        snapshot=snapshot,
        workflow_type=_TOOL_TO_WORKFLOW[tool_name],
    )
    return {"task_id": task_id, "workflow_type": _TOOL_TO_WORKFLOW[tool_name]}
```

#### `app/chat/runtime/react_agent.py`

```python
class ReActAgent:
    def __init__(self, *, agent_gateway, fast_runtime, rag_retriever, web_retriever,
                 workflow_registry, background_runner,
                 max_steps=3, timeout_seconds=25.0): ...

    def run_stream(self, *, request, snapshot) -> Iterator[dict]:
        # 1. build_tool_schemas(capability)
        # 2. stream_chat_with_tools()
        # 3. text_delta → 直接 yield（追问/大纲/普通回答全走这里）
        # 4. tool_calls → execute_tool → 注入结果 → 继续
        # 5. 超时/超步数 → fast_runtime fallback
```

### 6.2 修改文件

#### `app/chat/model_gateway.py`

新增 `stream_chat_with_tools()`：

```python
def stream_chat_with_tools(self, messages, tools, tool_choice="auto",
                            temperature=0.1, max_tokens=1024) -> Iterator[dict]:
    # yield {"type": "text_delta", "content": "..."}  ← 立即 yield，保证流式
    # yield {"type": "tool_calls", "calls": [...]}     ← 积累后 yield
    # yield {"type": "done"}
    # yield {"type": "unsupported"}                    ← fallback 信号
```

#### `app/chat/orchestrator/main_orchestrator.py`

`dispatch_stream()` 新增 agent 分支（与 Level 1 并存）：

```python
def dispatch_stream(self, request, *, on_workflow_complete=None):
    snapshot = self.context_builder.build(request)
    action_hint = getattr(request, "action_hint", "") or ""

    # Level 1：action_hint 确定路由（不变）
    if action_hint and action_hint in _HINT_TO_WORKFLOW:
        yield from self._dispatch_workflow(request, snapshot, action_hint, on_workflow_complete)
        return

    # Level 2：Agent 路径
    if self.react_agent is not None and Config.USE_REACT_AGENT:
        yield from self.react_agent.run_stream(request=request, snapshot=snapshot)
        return

    # Fallback：旧 route_rules（USE_REACT_AGENT=false 时）
    decision = decide_route(request=request, snapshot=snapshot,
                            workflow_state=getattr(snapshot, "workflow_state", None))
    ...
```

#### 各 Workflow Runtime（4个文件）

每个 workflow 新增 fast-path 检查（约 10~20 行）：

- `app/chat/workflows/report/runtime.py`
- `app/chat/workflows/ppt/runtime.py`（需将 confirmed_outline 转为 PptOutline 结构）
- `app/chat/workflows/lesson_plan/runtime.py`
- `app/chat/workflows/quiz/runtime.py`（无大纲，fast-path = 跳过收集）

#### `app/chat/domain/route_decision.py`

```python
path: Literal["fast", "workflow", "agent"]
```

---

## 7. 流式 SSE 事件

| 事件 type | 来源 | 说明 |
|-----------|------|------|
| `delta` | agent 流式文字 | 追问、大纲展示、普通回答全用此事件 |
| `status` | agent 调工具前 | `{stage:"thinking", label:"正在分析..."}` |
| `tool_call` | agent 调工具 | `{tool:"generate_report", args:{...}}` |
| `tool_result` | 工具执行完 | `{summary:"任务已提交 task_id=xxx"}` |
| `task_submitted` | generate_* 成功 | 前端开始轮询（已有） |
| `result` | 流结束 | 已有格式 |

前端已有 `delta` 和 `task_submitted` 处理逻辑，**不需要修改前端代码**。

---

## 8. 模型配置

| 角色 | 模型 | 配置来源 |
|------|------|---------|
| Agent（全程） | `deepseek-v4-flash` | `Config.get_agent_model()`（已添加） |
| 报告/教案正文生成 | 各 workflow 自有模型 | 不改动 |
| PPT 内容生成 | Gemini 3.1 Pro | 不改动 |

**已验证**：DeepSeek v4-flash function calling 工作正常（2026-05-18 实测）。

**`core/config.py` 已更新**：
- `REACT_AGENT_MODEL_NAME`（读取 `REACT_AGENT_MODEL` → 回落 `LLM_MODEL_DEEP` → 默认 `deepseek-v4-flash`）
- `REACT_AGENT_API_BASE` / `REACT_AGENT_API_KEY`（读取 DEEPSEEK_* 配置）
- `USE_REACT_AGENT`、`REACT_MAX_STEPS`、`REACT_TIMEOUT_SECONDS`（均可通过 .env 动态调整）

---

## 9. 降级策略

| 场景 | 行为 |
|------|------|
| `USE_REACT_AGENT=false` | 走旧 route_rules + workflow 完整路径 |
| action_hint 已设置 | Level 1 直接走 workflow（不进 agent） |
| DeepSeek 不可用 | fallback → fast_runtime（纯回答，不触发生成） |
| function calling 不支持 | fallback → fast_runtime |
| 超时 / 超 max_steps | fallback → fast_runtime |

---

## 9.5 HITL 与中间件设计

### Human-in-the-Loop

P4-A 采用**软 HITL**，无需额外机制：

- 每次 agent 输出文字（追问、大纲展示），对话轮次自然结束，用户接管
- `draft_outline` 调用后，agent 把大纲嵌入回复——这本身就是"不可逆操作前的人工确认点"
- 用户说"可以"触发新一轮 agent，agent 看到确认信号，调用 `generate_*`

**唯一的"硬"约束**：`generate_*` 工具的描述明确要求 `confirmed_outline` 必须来自用户已确认的大纲，这在工具调用约束层面强制了人工确认。

### 中间件

P4-A 不引入单独中间件层。所有横切关注点内联在 `execute_tool()` 入口：

```python
def execute_tool(name, args, *, ctx: ToolExecutionContext) -> dict:
    # ── Pre-checks ──────────────────────────────────────
    if ctx.step_count >= ctx.max_steps:
        raise ToolBudgetExceeded()
    if not _capability_allows(name, ctx.capability):
        raise ToolPermissionDenied(name)
    if ctx.already_called(name, args):          # 防止同参数重复调用
        return ctx.get_cached_result(name, args)

    # ── 执行 ────────────────────────────────────────────
    t0 = time.perf_counter()
    result = _dispatch(name, args, ctx)
    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    # ── Observability ────────────────────────────────────
    ctx.trace["agent_steps"].append({
        "step": ctx.step_count,
        "tool": name,
        "args": args,
        "result_summary": _summarize(result),
        "duration_ms": elapsed_ms,
    })
    ctx.step_count += 1
    return result
```

**P4-B 时机**：若需要外部服务调用、跨进程审计、或工具热插拔，再抽象为正式中间件链。

---

## 10. 实施步骤（分两阶段）

### Phase 1：ReAct 循环验证（3~4天，先跑通 agent 行为）

**目标**：验证 agent 对话流程自然、工具调用时机准确，与真实后台任务无关。

#### Step 1.1：stub 工具层（0.5天）

`app/chat/runtime/agent_tools.py`：
- `rag_search` / `web_search`：接真实检索器（或 mock，可选）
- `draft_outline`：**真实 LLM 调用**（这是 agent 体验的核心，必须真实）
- `generate_report/ppt/lesson_plan/quiz`：全部 stub，立即返回 `{"task_id": "stub-xxx", "workflow_type": "..."}`
- `build_tool_schemas(capability)`：动态构建，capability 门控生效

#### Step 1.2：Gateway stream_chat_with_tools（1天）

`app/chat/model_gateway.py`：
- `stream_chat_with_tools()` 实现
- `delta.content` → 立即 yield text_delta（保证 TTFT）
- `delta.tool_calls` → 积累，finish_reason="tool_calls" 后 yield
- unsupported 降级信号

#### Step 1.3：ReActAgent（1天）

`app/chat/runtime/react_agent.py`：
- `run_stream()` 循环：text_delta 直传 / tool_calls 执行 / fallback
- **Agent 系统提示调优**（重点，影响所有 agent 行为）
- 内联预检查（budget / capability / 去重）

#### Step 1.4：Orchestrator 集成（0.5天）

`main_orchestrator.py`：Level 1 / Level 2 / fallback 三路分发。

#### Step 1.5：Phase 1 验证

手动对话测试所有 §11 中"对话类"测试用例（1~10 条），重点检查：
- 大纲质量和格式
- Agent 追问自然度
- 工具调用时机（不该调时不调）
- TTFT 不回退

---

### Phase 2：接真实后台任务（3~4天）

**目标**：stub 替换为真实 workflow 触发，端到端生成可用。

#### Step 2.1：Workflow fast-path（1.5天）

4 个 workflow runtime 各新增入口检查：

```python
# 入口处
gathered = dict(getattr(request, "gathered_context", {}) or {})
confirmed_outline = gathered.get("confirmed_outline", "")
subject = gathered.get("subject") or gathered.get("topic", "")

if confirmed_outline and subject:
    return self._run_generating_fast(subject, confirmed_outline, gathered)
# else: 原有完整路径
```

**PPT 专项**：`_run_generating_fast()` 需要将 Markdown 大纲解析为 `PptOutline` 结构。使用宽松 Markdown 解析（`#` 标题 → slide，`-` → bullet），解析失败则降级到 workflow 自己生成大纲。

#### Step 2.2：generate_* 工具接真实 background_runner（0.5天）

`agent_tools.py`：将 stub 替换为 `_execute_generate_tool()`（见 §6.1 伪代码）。

#### Step 2.3：端到端验证（1天）

全部 20 条测试用例，重点验证：
- workflow fast-path 正常跳过收集/大纲阶段
- confirmed_outline 正确传递到生成阶段
- PPT Markdown → PptOutline 解析正确
- 生成结果质量（与原有 workflow 对比）

**总工期**：Phase 1（3.5天）+ Phase 2（3.5天）= 7天


---

## 11. 测试用例（20条）

### 普通对话（无工具调用）
1. "量子纠缠是什么意思"
2. "Python 列表和元组的区别"
3. "帮我翻译：The quick brown fox"
4. "你好"

### 信息不足 → 追问 → 大纲 → 生成
5. "帮我写报告" → agent 追问主题 → "量子计算，综述" → agent 展示大纲 → "可以" → generate_report
6. "帮我做课件" → agent 追问主题年级 → 回答 → 大纲 → 确认 → generate_ppt
7. "帮我做教案" → agent 追问课题 → 回答 → 大纲 → 确认 → generate_lesson_plan

### 信息充足 → 大纲 → 生成
8. "帮我写一份量子计算综述报告，5000字" → agent 展示大纲 → "好的" → generate_report
9. "做一个高中物理波动光学PPT，12张" → agent 展示大纲 → "确认" → generate_ppt

### 用户修改大纲
10. 大纲展示后，用户说"第三节改成量子纠错" → agent 回复修改后大纲 → 用户确认 → generate_*

### 直接生成（Quiz，无大纲）
11. "出 10 道 Python 基础选择题，中等难度" → 直接 generate_quiz
12. "生成 5 道高中数学填空题" → 直接 generate_quiz

### RAG/Web 检索
13. "根据我的知识库写一份报告" → rag_search → 展示大纲 → 确认 → generate_report
14. "查一下最新的量子计算研究进展" → web_search → 普通回答（不生成报告）
15. "根据资料解释一下核心概念" → rag_search → 普通回答

### 检索 + 生成
16. "根据我上传的课件内容出 10 道选择题" → rag_search → generate_quiz

### 边界情况
17. "帮我写量子计算报告" → agent 展示大纲 → 用户说"不，改成写AI应用的" → agent 重新展示新大纲 → 确认 → generate_report
18. "继续" (active workflow 但无 action_hint) → agent 从历史推断 → 合理响应
19. "帮我生成教案" + action_hint="generate.lesson_plan"（按钮触发）→ Level 1 → 完整 workflow 路径（不进 agent）
20. 连续多条消息后触发生成 → workflow fast-path 正常执行

---

## 12. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| PPT confirmed_outline 解析不准确 | PPT 结构错乱 | 用宽松解析（能识别标题即可），容错降级到 workflow 自己生成大纲 |
| Agent 判断"确认"时机错误（未确认就调工具） | 不符合用户意图的生成任务被提交 | 工具描述明确要求 confirmed_outline 参数存在；generate_quiz 无此约束 |
| DeepSeek 内联生成大纲质量不稳定 | 大纲可读性差 | 系统提示要求 Markdown 格式；用户可修改后再确认 |
| Workflow fast-path 跳过安全校验 | 参数不全导致生成失败 | fast-path 入口校验 subject + confirmed_outline 非空才启用 |
| 按钮路径和 agent 路径并存的行为一致性 | 用户困惑 | 明确规则：有 action_hint = 按钮路径；无 action_hint = agent 路径 |
