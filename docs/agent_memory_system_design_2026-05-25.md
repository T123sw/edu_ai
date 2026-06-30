# Agent 记忆系统设计文档

**日期**：2026-05-25  
**状态**：设计阶段  
**背景**：基于 P4-A ReAct Agent 化完成后的全流程分析，提炼 Agent 记忆系统的需求与设计方向。

---

## 一、当前 Agent 全流程

### 1.1 请求入口与路由

```
HTTP 请求
  → ReplyServiceV2.reply_stream()
  → MainOrchestrator.dispatch_stream()
       ├─ action_hint 存在（按钮触发）→ WorkflowRuntime（不变）
       ├─ USE_REACT_AGENT=True        → ReActAgent.run_stream()  ← 当前路径
       └─ 兜底                        → FastChatRuntime / legacy WorkflowRuntime
```

### 1.2 Agent 启动（run_stream）

1. `build_tool_schemas(capability)` 按权限动态生成工具列表
   - `allow_rag=True` → 加 `rag_search`
   - `allow_web=True` → 加 `web_search`
   - 无条件加 `draft_outline`、`generate_report/ppt/lesson_plan/quiz`
2. 构建 `ToolExecutionContext`（携带 capability、检索器、workflow_registry、agent_gateway 等）
3. 调 `_build_messages(request, snapshot)` 构建消息列表
4. yield `{type:"status", stage:"thinking"}`
5. 进入 `_react_loop`

### 1.3 消息构建（_build_messages）

从 `snapshot.recent_messages`（最近 20 条）还原历史，支持三种格式：

```
role=assistant + tool_calls  →  {"role":"assistant","content":null,"tool_calls":[...]}
role=tool + tool_call_id     →  {"role":"tool","tool_call_id":"...","content":"..."}
有 content 的消息             →  {"role":"user/assistant","content":"..."}
```

最终消息列表：`[ SYSTEM_PROMPT, *history, user_question ]`

**当前缺陷**：`snapshot.summary` 和 `snapshot.conversation_memory` **未注入**，agent 看不到跨轮摘要。

### 1.4 ReAct 主循环（_react_loop）

```
while True:
  检查超时（默认 180s）
  ↓
  LLM 调用（Qwen3.5-plus / Dashscope，max_tokens=2048，temperature=0.1）
  ↓
  逐 event 处理（真正流式）：
    text_delta  → 立即 yield {type:"delta"}    ← TTFT 正常
    tool_calls  → 暂存，等流结束后处理
    error       → 降级 fallback
  ↓
  无 tool_calls → break（直接回答完毕）
  有 tool_calls → 依次 execute_tool()：
    - yield {type:"tool_call"}
    - 同步执行工具（阻塞！）
    - yield {type:"tool_result"}
    - generate_* 成功 → yield {type:"task_submitted"}
    - 格式化结果 + 追加 Observe 提示
    追加 tool_exchange_messages，更新 messages
  ↑（回到顶部，发起下一轮 LLM 调用）
```

### 1.5 工具层

| 工具 | 实现 | 耗时 | 特点 |
|------|------|------|------|
| `rag_search` | `ctx.rag_retriever()` | ~1-3s 同步 | 阻塞事件循环 |
| `web_search` | `ctx.web_retriever()` | ~2-5s 同步 | 阻塞事件循环 |
| `draft_outline` | `ctx.agent_gateway.chat()` 再调一次 Qwen | ~3-5s 同步 | 同一 key，阻塞，无流式反馈 |
| `generate_*` | `submit_callable_task()` 提交线程池 | 立即返回 task_id | 后台生成，无推送 |

**execute_tool 前置守卫**：
- `step_count >= max_steps` → 拒绝
- `!capability_allows()` → 拒绝（无权限）
- `already_called(name, args)` → 返回缓存（去重）

### 1.6 Observe 提示（工具结果自检）

每个工具结果追加引导提示，强制模型评估再决策：

```
rag_search  → "【自检】请评估以上检索结果：内容是否充分？是否有图片/图表？若不足，继续调用 web_search。"
web_search  → "【自检】请评估以上联网结果是否满足需求。若已充分，进行下一步。"
draft_outline → "大纲已生成，请在回复中将以下大纲内容完整逐字输出给用户..."
```

### 1.7 持久化链

```
write_v2_result：
  ① user 消息
  ② tool_exchange 中每条消息（assistant tool_calls + tool 结果）  ← 2026-05-25 新增
  ③ 最终 assistant 回答
  → 存入 JSON 文件 → 下次 get_messages(limit=20) 读出
  → snapshot.recent_messages → _build_messages 还原完整上下文
```

### 1.8 报告生成完整示例

> 用户第一轮："帮我生成一份关于量子计算的报告"

```
[第1步 LLM] 决策 → 调 draft_outline(resource_type="report", subject="量子计算")
  → Qwen 内部再调用生成大纲文本 ~4s（同步阻塞，前端无反馈）
  → 返回大纲 Markdown ~500字

[第2步 LLM] 看到大纲 → 按系统提示第2步 → 调 rag_search(query="量子计算相关材料")
  → RAG 检索 ~2s
  → 返回知识库片段

[第3步 LLM] 评估 rag 结果充分 → 输出大纲+摘要+询问（真正流式推送给用户）
  → 前端看到逐字输出："以下是为您准备的量子计算报告大纲：\n# 量子计算报告大纲\n..."
  → 结束语："如果满意，我将开始生成完整报告，是否需要调整？"

持久化：6 条消息（user + assistant_tool_calls×2 + tool_result×2 + final_assistant）
```

> 用户第二轮："好的，可以生成了"

```
_build_messages 读出 6 条历史 → agent 看到完整上下文（含大纲工具结果）

[LLM] 识别"用户确认" → 从历史 tool 消息中找大纲 → 调 generate_report(confirmed_outline="...")
  → submit_callable_task → 立即返回 task_id
  → yield {type:"task_submitted"}

[LLM] 看到任务提交 → 输出："已提交报告生成任务，task_id=xxx，约 2-3 分钟完成。"
```

---

## 二、当前记忆系统现状与问题

### 2.1 现有机制

每次对话结束，`ConversationMemoryExtractor.build_state_patch()` 对 `(question, answer)` 做规则提取，结果写入 `conversation_state`：

| 字段 | 提取方式 | 用途设计 |
|------|----------|----------|
| `conversation_summary.summary_text` | 模板拼接 | 对话摘要 |
| `current_topics` | 去前缀词后切句 | 当前讨论主题 |
| `user_goals` | 关键词匹配 | 用户意图 |
| `explicit_user_constraints` | 正则（字数/年级/科目） | 生成约束 |
| `teaching_issues` | 关键词表匹配 | 教学问题（domain 专用） |
| `student_signals` | 关键词表匹配 | 学生行为观察（domain 专用） |
| `user_claims` / `confirmed_facts` | 去疑问词后提取陈述 | 事实追踪 |

另有 `LLMEnhancementRouter`（设计了 LLM 增强提取），当前 `enabled=False`。

### 2.2 核心问题：记忆存了，但 agent 看不到

```python
# _build_messages 当前实现 —— 记忆完全未注入
return [
    {"role": "system", "content": AGENT_SYSTEM_PROMPT},  # ← 静态 prompt，无上下文
    *history,
    {"role": "user", "content": question},
]
# snapshot.summary       → 丢弃
# snapshot.conversation_memory → 丢弃
```

### 2.3 其他问题

1. **无 Agent 工作状态追踪**：`draft_outline` 成功后大纲内容没有存入 state，下一轮 agent 靠从消息历史里自己找（不稳定）。
2. **`confirmed_outline` 无结构化存储**：用户确认这个关键事件，在 state 里没有对应记录。
3. **`recent_messages` 上限 20 太小**：tool_calls 持久化后一轮写 6 条，两轮后历史开始截断。
4. **记忆是 teaching 领域专用的**：`teaching_issues`、`student_signals` 与资源生成的 ReAct 流程无关。
5. **没有跨会话记忆**：用户偏好、常用主题、历史生成内容，在新对话中全部丢失。

---

## 三、Agent 需要的记忆系统

### 3.1 三层记忆模型

```
┌─────────────────────────────────────────────────────────────────┐
│  L1  短期记忆（Short-term Memory）                               │
│  载体：recent_messages（消息历史）                                │
│  内容：最近 N 条原始消息，含 tool_calls / tool results            │
│  生命周期：单次会话，窗口滑动                                     │
│  当前状态：✅ 已实现，但 limit=20 不够用                          │
├─────────────────────────────────────────────────────────────────┤
│  L2  工作记忆（Working Memory）                                  │
│  载体：conversation_state（JSON key-value）                      │
│  内容：当前任务执行状态                                           │
│    - active_draft_outline: {content, resource_type, subject}   │
│    - pending_tasks: [{task_id, workflow_type, submitted_at}]   │
│    - user_confirmed_at: ISO 时间                                │
│    - session_goal: 当前任务类型（"生成报告"/"生成PPT"等）         │
│  生命周期：单次任务完成后清除或归档                               │
│  当前状态：❌ 未实现，是最紧迫的缺口                              │
├─────────────────────────────────────────────────────────────────┤
│  L3  长期记忆（Long-term Memory）                                │
│  载体：用户画像存储（独立于对话，按 user_id 存储）                 │
│  内容：跨会话沉淀                                                │
│    - user_preferences: {tone, outline_format, length_style}    │
│    - frequent_topics: ["量子计算", "深度学习"]                   │
│    - generated_artifact_index: [{type, title, created_at}]     │
│    - teaching_context: {grade, subject, school_type}           │
│  生命周期：永久，按用户维度管理                                   │
│  当前状态：❌ 未实现，中期需求                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 每层的具体作用

#### L1 短期记忆——现在怎么用，要怎么改

**当前行为**：`_build_messages` 从 `recent_messages` 还原消息历史，注入 LLM context。

**需要改进**：
- `limit=20` → 调整为 `40`（tool_calls 持久化后，每轮约 6 条）
- 消息过多时需要摘要压缩策略（超过阈值时，把旧消息压缩为一段文字，保留最近 N 条）

#### L2 工作记忆——最紧迫，影响多轮任务正确性

工作记忆解决的核心问题是：**多轮任务中 agent 知道"上一步做了什么"**。

典型失败场景（无工作记忆）：
```
第1轮：agent 生成大纲并展示
第2轮：用户说"好的"
        → agent 从消息历史搜索大纲（依赖 LLM 记忆力，不稳定）
        → 或者 agent 忘记了，重新调 draft_outline（死循环）
```

有工作记忆后：
```
第2轮：_build_messages 注入：
        "【已生成待确认大纲】资源类型：report  主题：量子计算
         内容：# 量子计算报告大纲\n## 一、量子计算基础..."
        → agent 直接拿到大纲，调 generate_report，传入 confirmed_outline
```

**工作记忆的数据结构**：

```json
{
  "active_draft_outline": {
    "resource_type": "report",
    "subject": "量子计算",
    "content": "# 量子计算报告大纲\n## 一、量子计算基础\n...",
    "created_at": "2026-05-25T10:30:00Z",
    "turn_id": 3
  },
  "pending_tasks": [
    {
      "task_id": "task_abc123",
      "workflow_type": "report",
      "subject": "量子计算",
      "submitted_at": "2026-05-25T10:35:00Z",
      "status": "running"
    }
  ],
  "session_goal": "generate_report",
  "user_confirmed_at": null
}
```

**工作记忆的写入时机**：

| 事件 | 写入内容 |
|------|----------|
| `draft_outline` 工具成功 | `active_draft_outline = {content, resource_type, subject}` |
| 用户发出确认信号 | `user_confirmed_at = now()` |
| `generate_*` 工具成功 | `pending_tasks.append({task_id, ...})`，清空 `active_draft_outline` |
| 任务查询返回 completed | `pending_tasks` 中对应记录标记 completed |

**工作记忆的注入方式**：在 `_build_messages` 的 system prompt 末尾追加：

```
【当前任务状态】
- 已起草大纲（量子计算报告）：[大纲内容...]
  → 若用户表示满意，调用 generate_report 并传入上述大纲
- 进行中任务：report / task_abc123（2026-05-25 10:35 提交）
```

#### L3 长期记忆——中期实现，跨会话沉淀

长期记忆的价值：
- **减少重复追问**：用户第一次说过"我是高中物理老师"，后续不再问
- **个性化生成**：记住用户偏好"报告要正式，约5000字"
- **历史引用**："基于上次生成的量子计算报告，再做一个PPT版本"

数据存储位置：独立于对话，按 `user_id` 存储，跨会话持久化。

### 3.3 记忆的写入与读取流程

```
【写入时机】
  每轮对话结束 → write_v2_result：
    ① 规则提取（现有 ConversationMemoryExtractor）→ 更新 conversation_memory
    ② 工作状态提取（新增）→ 更新 active_draft_outline / pending_tasks
    ③ tool_exchange 持久化（已实现）→ 更新 recent_messages

【读取时机】
  每次请求开始 → context_builder.build() → ConversationSnapshot：
    ① recent_messages（L1）
    ② active_context（L2 工作状态）  ← 目前这个字段存在但未填充
    ③ conversation_memory（现有记忆字段）
    ④ (未来) user_long_term_profile（L3）

【注入方式】
  _build_messages() 根据以上字段动态构建 system prompt 的上下文段落
```

### 3.4 对现有 ConversationMemoryExtractor 的评价

| 能力 | 评价 |
|------|------|
| 主题/目标提取 | 可用，但精度一般（regex 切句容易误分） |
| 约束提取（字数/年级） | 有用，需保留 |
| teaching_issues / student_signals | 教学观察专用，不适合通用 agent |
| 摘要生成 | 模板拼接，太简单，遗漏工具调用信息 |
| 工作状态追踪 | 完全没有 |
| 跨会话记忆 | 完全没有 |

**结论**：现有 Extractor 做的是"教学域的规则提取"，对 ReAct agent 的多步任务状态追踪完全无效，需要新增工作记忆层，现有代码可以保留做辅助提取。

---

## 四、当前问题全表

| 优先级 | 问题 | 影响 | 位置 |
|--------|------|------|------|
| P0 | `recent_messages` limit=20，tool_calls 持久化后迅速截断 | 历史断裂，agent 失忆 | `conversation_store_adapter.py` |
| P0 | 工作记忆（active_draft_outline）未实现 | 多轮确认流程不可靠 | 需新增 |
| P0 | summary / conversation_memory 未注入 system prompt | agent 看不到对话摘要 | `react_agent._build_messages` |
| P1 | `draft_outline` 同步调 Qwen ~4s，期间无任何流式反馈 | 用户体验差 | `handlers/outline.py` |
| P1 | `rag_search` / `web_search` 同步阻塞 async 事件循环 | 高并发性能问题 | `handlers/retrieval.py` |
| P1 | 工具串行执行（rag + web 不能并行） | 延迟加倍 | `_react_loop` |
| P2 | `generate_*` 后台任务无主动推送 | 用户需自行轮询 | 需新增推送机制 |
| P2 | 所有工具 schema 始终全量传给模型 | 纯闲聊场景多余 token | `build_tool_schemas` |
| P3 | 长期记忆（跨会话用户画像）未实现 | 每次对话重头开始 | 需新增 |
| P3 | `confirmed_outline` 靠 LLM 从历史找，偶发错误 | 工作记忆实现后可彻底解决 | — |

---

## 五、开源技术参考方向

以下是评估开源记忆系统时需要对照的核心能力点：

### 5.1 需要参考的能力维度

**工作记忆（Session State）**
- 在一次多工具调用链路中，如何结构化保存中间状态？
- 是否支持自定义 key-value 存储，能被 system prompt 注入？

**短期记忆压缩（Context Compression）**
- 消息历史过长时，如何智能压缩老消息？
- 压缩后是否保留 tool_calls / tool_results 的结构？

**长期记忆（Persistent Memory）**
- 跨会话的用户画像如何存储和更新？
- 是否支持按相关性检索记忆（而不是全量注入）？

**记忆写入时机（Memory Trigger）**
- 是在每轮对话后提取？还是由模型主动决定何时记忆？
- 是否支持"模型调用 remember() 工具"的主动写入模式？

### 5.2 值得调研的开源项目

以下项目覆盖了上述能力的不同维度，可按需评估：

| 项目 | 核心能力 | 与本系统的关联 |
|------|----------|----------------|
| **mem0** (github.com/mem0ai/mem0) | 自动提取+向量存储的长期记忆，支持 user/session/agent 三层 | L3 长期记忆实现的直接参考 |
| **LangChain Memory** | ConversationBufferMemory / SummaryMemory / VectorStoreRetrieverMemory | 短期记忆压缩 + 向量检索的经典实现 |
| **MemGPT / Letta** | 分层内存（core/archival/recall），模型自主决定写入 | 工作记忆 + 主动记忆写入的参考 |
| **Zep** | 对话历史的自动摘要 + 实体追踪 + 向量检索 | 摘要压缩 + 实体记忆（confirmed_outline 类似场景） |
| **CrewAI Memory** | 短期/长期/实体/上下文四层内存 | 多 Agent 场景的记忆架构参考 |
| **AutoGen + TeachableAgent** | 通过对话学习用户偏好，持久化到向量 DB | L3 用户偏好学习的参考 |

### 5.3 评估时的关键问题

调研以上项目时，需要重点确认：

1. **是否支持结构化工作状态**（key-value，非纯文本）？本系统的 `active_draft_outline` 需要结构化，不能只是文本摘要。

2. **写入时机是否可控**？本系统需要在特定工具执行成功后写入，而不是每轮都提取。

3. **注入方式是否灵活**？需要能把记忆以结构化方式注入 system prompt，而不只是追加到 messages 末尾。

4. **是否依赖外部向量 DB**？当前系统是本地 JSON 存储，引入向量 DB 需要评估运维成本。

5. **中文支持是否可靠**？提取和检索是否对中文文本有针对性优化？

---

## 六、实施建议（分阶段）

### 阶段一（本周，P0 问题，影响当前功能正确性）

1. **扩大 `recent_messages` limit**：`load_snapshot(limit=20)` → `limit=40`，`write_v2_result` 后的 `get_messages(limit=8)` 保持不变（仅用于状态提取，不需要太多）
2. **实现工作记忆写入**：`draft_outline` 成功后写入 `state["active_draft_outline"]`，`generate_*` 成功后清除
3. **注入工作状态 + 摘要**：`_build_messages` 读取并注入 `snapshot.active_context` 和 `snapshot.summary`

### 阶段二（中期，P1，性能与体验）

4. **异步化工具执行**：用 `run_in_executor` 包裹 `rag_search`/`web_search`/`draft_outline`
5. **draft_outline 流式化**：改为流式调用，在等待期间向前端推送进度提示

### 阶段三（中长期，P3，长期记忆）

6. **调研开源记忆系统**（mem0 / Zep 优先），评估是否可以无缝替代现有 `ConversationMemoryExtractor`
7. **用户画像层**：按 `user_id` 存储偏好，跨会话注入

---

*文档版本：1.0 | 作者：AI 助手 | 下次更新：实施阶段一后*
