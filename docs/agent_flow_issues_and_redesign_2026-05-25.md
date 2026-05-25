# ReAct Agent 全流程问题分析与重设计方案

**日期**：2026-05-25  
**状态**：待实施  
**背景**：P4-A 已完成基础骨架，本文总结当前流程中所有不合理之处，并给出重设计方向。

---

## 一、当前流程全貌

```
用户输入
  └─ dispatch_stream()
       ├─ [action_hint] → WorkflowRuntime         【按钮路径，不动】
       └─ [自然对话]    → react_agent.run_stream()
            │
            ├─ ① _plan_task()   ← 独立 LLM 调用（Qwen，同步，~3s）
            │    └─ 返回步骤列表，注入 system prompt
            │
            ├─ ② _build_messages()
            │    └─ system_prompt + history + user_question
            │
            └─ ③ _react_loop()
                  while True:
                    a. list(stream_fn(...))   ← 全部收完再处理
                    b. yield delta
                    c. execute_tool()
                    d. 追加 [assistant(tool_calls) + tool_result] 到 messages
                    e. 无工具调用 → break
                  yield result
```

---

## 二、问题清单

### P0 — 必须修，严重影响功能

#### 问题 1：流式输出被完全阻断

**位置**：`react_agent.py` `_react_loop()` 第 247 行

```python
# 当前：先收集所有 event，再一起处理
events = list(stream_fn(messages, tool_schemas, ...))
for e in events:
    if e["type"] == "text_delta":
        yield {"type": "delta", ...}
```

**后果**：用户要等 LLM 把本轮整个回复生成完，才能看到第一个字。TTFT = 模型总耗时，流式的意义完全消失。

**正确做法**：逐个处理 event，`text_delta` 立即 yield，`tool_calls` 出现时再做工具调度。

---

#### 问题 2：历史消息丢失 tool_calls，用户确认流程无法闭环

**位置**：`react_agent.py` `_build_messages()` 第 372 行

```python
for msg in recent:
    content = str(... or "")
    if content:                  # ← content=None 的消息被丢弃
        history.append(...)
```

**后果**：
- 上一轮 assistant 调用了 `draft_outline`，消息的 `content=None`，被过滤掉
- 下一轮 agent 完全不知道"上轮已生成了大纲"
- 用户回复"满意"时，`_plan_task` 重新判断任务，agent 可能**再次调用 draft_outline**，陷入死循环
- **资源生成的三步流程（起草→确认→生成）在多轮对话中无法正确推进**

**正确做法**：历史消息应保留 `tool_calls` 和 `tool` 角色的消息，让 agent 有完整的上下文。

---

### P1 — 应修，影响核心体验

#### 问题 3：规划与执行完全脱节，_plan_task 是冗余的 LLM 调用

**位置**：`react_agent.py` `_plan_task()` + `_build_messages()`

**现状**：
- `_plan_task` 调用 Qwen 一次（~3s），生成 [步骤1, 步骤2, 步骤3]
- 步骤注入 system prompt，但标注永远是"**当前执行第一步**"
- 第 2、3 轮 LLM 调用看到的还是同一个提示，步骤追踪形同虚设
- `AGENT_SYSTEM_PROMPT` 里已经写死了同样的决策逻辑，两个 LLM 对同一件事重复描述

**更深层的问题**：用户真正需要的"规划"不是一个预先固定的步骤列表，而是**模型在每一步自主决定下一步调什么工具**。

**目标行为示例**（生成一份报告）：
```
第1轮：模型思考 → 调用 draft_outline
第2轮：模型看到大纲 → 自主决定调用 rag_search（检查知识库有无相关材料）
第3轮：模型看到检索结果 → 自主判断图片不足 → 调用 web_search（搜索配图）
第4轮：模型综合全部材料 → 展示大纲+材料摘要给用户，询问确认
第5轮（用户确认后）：调用 generate_report，传入 confirmed_outline
```

这才是真正的 ReAct（**Re**ason + **Act**）：每次工具执行后模型主动观察结果，决定下一步。

---

#### 问题 4：没有工具结果自检机制

**现状**：工具结果直接追加到 messages，模型进入下一轮时并不会被要求"先评估结果质量再决定行动"。

**后果**：
- `rag_search` 返回空结果，模型可能直接跳过，不去尝试 `web_search` 补充
- `draft_outline` 返回格式混乱的大纲，模型没有机会发现并重新生成

**目标行为**：工具结果追加到 context 时，附加一条 **Observe 提示**，让模型先评估再行动：

```
[工具结果]
知识库检索结果：[...内容...]

[观察与决策]
请先评估以上工具结果是否满足需求：
- 内容是否充分？是否需要补充检索？
- 是否存在缺失的图片或数据？
然后决定下一步行动。
```

---

#### 问题 5：max_tokens=1024 不够用

**位置**：`react_agent.py` `_react_loop()` 第 252 行

```python
events = list(stream_fn(..., max_tokens=1024))
```

**后果**：
- 大纲 600+ 字符，加上确认话语 + 思考过程，1024 token 非常容易截断
- 大纲不完整，用户体验差

**正确做法**：展示内容的轮次（如展示大纲）需要 2048～4096 token。

---

### P2 — 可改，影响性能/可维护性

#### 问题 6：工具执行同步阻塞 async endpoint

`draft_outline` 内部调 `ctx.agent_gateway.chat()`（`requests.post`，同步），在 FastAPI `async def` 路由里直接调用会阻塞整个事件循环，影响并发性能。

**正确做法**：用 `asyncio.get_event_loop().run_in_executor()` 或 `run_in_threadpool()` 包裹同步调用。

---

#### 问题 7：任务提交后用户无感知进度

`generate_report` 提交后台任务后 agent 立即结束，用户拿到 task_id 只能自己轮询，没有主动推送机制。（这是长期问题，单独排期）

---

## 三、重设计方案

### 核心思路：移除 _plan_task，让 ReAct 循环自带规划能力

**真正的 ReAct 应该是**：

```
┌─────────────────────────────────────────────────┐
│  每一轮 LLM 调用 = Reason（思考）+ Act（决策）   │
│                                                  │
│  工具结果回来后 = Observe（观察）                 │
│  下一轮 LLM 调用 = Reason（基于观察再思考）       │
└─────────────────────────────────────────────────┘
```

去掉独立的 `_plan_task`，让模型在 ReAct 循环的每一轮**自主推理下一步**，系统只提供：
1. 清晰的工具描述（schemas）
2. 每次工具结果后追加"观察提示"引导模型评估
3. 对话历史完整透传（含 tool_calls）

---

### 改动清单

#### 改动 A：`_react_loop` 改为真正流式

```python
# 修改前
events = list(stream_fn(...))
for e in events: ...

# 修改后
answer_chunks = []
tool_calls_acc = {}    # 边流式边积累 tool_calls
for e in stream_fn(...):
    if e["type"] == "text_delta":
        answer_chunks.append(e["content"])
        yield {"type": "delta", "payload": {"content": e["content"]}}  # 立即 yield
    elif e["type"] == "tool_calls":
        tool_calls_event = e
    elif e["type"] == "done":
        break
```

#### 改动 B：`_build_messages` 保留完整历史（含 tool_calls）

```python
for msg in recent:
    role = msg.get("role")
    content = msg.get("content")     # 可以为 None
    tool_calls = msg.get("tool_calls")

    if role == "assistant" and tool_calls:
        # 保留工具调用轮次
        history.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
    elif role == "tool":
        # 保留工具结果
        history.append({"role": "tool", "tool_call_id": msg.get("tool_call_id"), "content": content})
    elif content:
        history.append({"role": role, "content": content})
```

但前提是：**对话存储层也需要保存 tool_calls 格式的消息**（目前可能只保存 content）。

#### 改动 C：移除 _plan_task，改写 AGENT_SYSTEM_PROMPT

去掉独立的规划 LLM 调用，将规划能力内化到 system prompt：

```
【自主规划规则】
接到任务后，在第一轮先规划完整的执行路径，然后逐步执行：

资源生成任务的标准路径：
  1. draft_outline  → 起草大纲
  2. rag_search     → 检索知识库，获取相关材料
  3. （如 rag_search 结果不足）web_search → 补充联网资料
  4. 向用户展示大纲 + 材料摘要，询问是否满意
  5. 用户确认后 → generate_*（传入 confirmed_outline）

执行原则：
  - 每次工具返回后，先评估结果质量，再决定下一步
  - 不要跳过检索步骤（除非用户明确不需要）
  - 若某步工具失败，说明原因并询问用户是否跳过该步
```

#### 改动 D：工具结果追加 Observe 提示

```python
def _format_tool_result_for_context(tool_name, result):
    content = ...  # 原有格式化逻辑

    # 追加观察引导
    observe_hint = _OBSERVE_HINTS.get(tool_name, "")
    if observe_hint:
        content += f"\n\n{observe_hint}"
    return content

_OBSERVE_HINTS = {
    "rag_search": (
        "【请评估】以上检索结果是否充分？"
        "如内容不足或缺少图片，请继续调用 web_search 补充。"
    ),
    "web_search": (
        "【请评估】以上联网结果是否满足需求？"
        "如已充分，请进行下一步。"
    ),
    "draft_outline": (
        "大纲已生成，请在回复中完整展示给用户，"
        "询问是否满意，同时告知用户你接下来会检索相关材料。"
    ),
}
```

#### 改动 E：max_tokens 按轮次动态调整

```python
# 展示内容的轮次（有 text_delta）用更大的 token 限制
max_tokens = 4096 if step == 1 else 2048
```

或者统一改为 2048，保证不截断。

---

## 四、优先级与排期建议

| 优先级 | 改动 | 预估工时 | 说明 |
|--------|------|----------|------|
| P0 | 改动 A：流式不阻断 | 1h | 改一处循环逻辑 |
| P0 | 改动 B：历史消息完整 | 2h | 需同步确认存储层格式 |
| P1 | 改动 C：移除 _plan_task + 新 prompt | 2h | 需测试多轮行为 |
| P1 | 改动 D：Observe 提示 | 1h | 纯文本修改 |
| P2 | 改动 E：max_tokens | 0.5h | 一行改动 |
| P2 | 问题 6：异步化工具执行 | 3h | 影响范围较广 |

**建议顺序**：A → E → C+D → B（B 需要联动存储层，单独评估）

---

## 五、不动的部分

- `WorkflowRuntime`（按钮路径）：完全独立，不受影响
- `execute_tool` / `build_tool_schemas`：接口稳定，不改
- `model_gateway.stream_chat_with_tools`：已正确实现，不改
- `_fallback`：降级逻辑保留
