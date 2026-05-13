# Report 先行承接方案
**状态：** 草案，可作为 report 链路改造设计依据  
**日期：** 2026-04-02  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`  
**依赖文档：**
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-conversation-memory-generation-context-design-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-conversation-memory-merge-spec-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-generation-context-field-matrix-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-state-writeback-event-flow-cn.md`

## 1. 文档目的

本文档聚焦一个明确目标：

**不一次性改造所有资源工作流，而是优先让 report 链路先消费统一的 `GenerationContext`，验证这套对话沉淀体系在现有代码中的承接方式。**

它不是实施计划，但它必须回答以下问题：

- 当前 report 链路到底怎么拿上下文
- 现状中哪些地方已经能复用，哪些地方还是缺口
- `GenerationContextBuilder` 应该插在哪一层
- `ReportAssembler` 应该承担什么职责
- 哪些旧逻辑应该保留，哪些应该逐步下沉

---

## 2. 为什么先做 report

优先选择 report 作为第一条承接链路，原因有三：

### 2.1 report 是当前系统里最明确的 workflow 主线

当前代码已经有完整 report 入口和 runtime：

- `/api/chat/v2/reply`
- `/api/chat/v2/report`
- `ReportWorkflowRuntime`
- `universal_report_engine`

说明它不是未来设想，而是现有主路径。

### 2.2 report 对上下文稳定性最敏感

报告生成天然依赖：

- 已确认事实
- 问题点
- 证据点
- 当前课程
- 相关文档
- 最近讨论主线

如果 `GenerationContext` 对 report 都无法稳定服务，那么对后续 lesson_plan / quiz 的价值也不成立。

### 2.3 report 已经有“上下文槽位”

当前 report engine 的 state 中已经存在：

```py
gathered_context: Dict[str, Any]
```

这意味着 report 不是完全没有位置承接新结构，而是已经有一个自然扩展点。

---

## 3. 当前 report 链路现状

### 3.1 当前入口链路

当前 report 链路可以概括为：

`routes_v2.py -> ReportServiceV2 -> ContextBuilder.build -> ReportWorkflowRuntime.run -> report engine.invoke`

其中：

- [routes_v2.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py)
- [report_service_v2.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py)
- [context_builder.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/orchestrator/context_builder.py)
- [runtime.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/workflows/report/runtime.py)

### 3.2 当前 `ContextBuilder` 提供的内容

当前 `ContextBuilder.build()` 主要提供：

- `recent_messages`
- `summary`
- `active_task`
- `active_artifact`
- `workflow_state`
- `capability`

这意味着当前 snapshot 更像“最近会话快照”，还不是“面向生成的结构化上下文”。

### 3.3 当前 `ReportWorkflowRuntime` 传给引擎的 state

当前 runtime 会构建如下输入骨架：

```py
state = {
    "user_input": request.question,
    "report_state": snapshot.workflow_state,
    "conversation_id": request.conversation_id,
    "owner": request.owner,
    "allow_rag": capability.allow_rag,
    "allow_web": capability.allow_web,
    "selected_doc_ids": capability.selected_doc_ids,
    "gathered_context": {
        "summary": snapshot.summary,
        "recent_messages": snapshot.recent_messages,
        "active_task": snapshot.active_task,
        "active_artifact": snapshot.active_artifact,
    },
}
```

这说明当前 report engine 依赖的是：

- 用户本轮输入
- 轻量 summary
- 最近消息窗口
- 当前 active 对象
- workflow_state

### 3.4 当前结构的优点

当前实现并不是坏起点，反而已经具备几个很重要的支点：

- report 有独立 runtime
- runtime 已经隔离出 `gathered_context`
- report engine 已经能消费结构化 `state`
- `selected_doc_ids` 已经被稳定传入

### 3.5 当前结构的核心问题

当前最主要的问题不是没有上下文，而是上下文来源过薄：

- `summary` 目前没有稳定结构来源
- `recent_messages` 容易带来噪音
- `active_task / active_artifact` 只有对象状态，没有内容骨架
- 缺少：
  - `confirmed_facts`
  - `teaching_issues`
  - `evidence_points`
  - `constraints`
  - `current_topics`
  - `current_course_id`

也就是说，当前 runtime 已经有“收口位置”，但缺少“真正有价值的材料层”。

---

## 4. 目标链路

report 先行方案的目标链路应调整为：

**`ContextBuilder` -> `GenerationContextBuilder` -> `ReportAssembler` -> `ReportWorkflowRuntime` -> `universal_report_engine`**

其中职责边界如下：

### 4.1 `ContextBuilder`

继续负责读取会话级基础状态，例如：

- 原始消息窗口
- workflow_state
- active_artifact
- active_task
- capability

它仍然是通用入口，但不再承担 report 专属上下文组装职责。

### 4.2 `GenerationContextBuilder`

新增的核心层，负责把：

- `ConversationSummary`
- `ConversationMemory`
- `ActiveContext`
- 最近相关消息
- selected docs
- referenced artifacts

组合成通用 `GenerationContext`。

### 4.3 `ReportAssembler`

负责把通用 `GenerationContext` 变成 report 专用输入，重点是：

- 压缩成 report engine 真的关心的字段
- 决定哪些字段进入 `gathered_context`
- 让 runtime 不需要理解 memory 细节

### 4.4 `ReportWorkflowRuntime`

负责：

- 拼接 engine state
- 调用引擎
- 规范化 workflow 返回结构

它不应继续自己理解聊天历史。

---

## 5. 推荐的 report 承接结构

### 5.1 先引入 `GenerationContext`

对 report，推荐的最小 `GenerationContextMVP` 为：

```ts
type GenerationContextMVP = {
  conversation_id: string
  resource_type: "report"

  summary_text: string
  current_topics: string[]
  user_goals: string[]
  confirmed_facts: string[]
  constraints: ConstraintState

  teaching_issues?: string[]
  student_signals?: string[]
  evidence_points?: EvidencePoint[]

  selected_doc_ids: string[]
  referenced_artifact_ids: string[]
  current_course_id?: string
  active_artifact_id?: string
  active_artifact_type?: string

  recent_relevant_messages: MessageRecord[]
  source_scope: {
    from_summary: boolean
    from_memory: boolean
    from_recent_messages: boolean
    from_docs: boolean
    from_artifacts: boolean
  }
}
```

### 5.2 再引入 `ReportInput`

`ReportAssembler` 的产物建议不是直接复用 `GenerationContext`，而是压成 report 专用输入：

```ts
type ReportInput = {
  user_input: string
  conversation_id: string

  source_summary: string
  current_topics: string[]
  confirmed_facts: string[]
  teaching_issues: string[]
  student_signals: string[]
  evidence_points: EvidencePoint[]

  constraints: ConstraintState
  selected_doc_ids: string[]
  referenced_artifact_ids: string[]

  current_course_id?: string
  active_artifact_id?: string
  active_artifact_type?: string

  recent_relevant_messages: MessageRecord[]
  source_scope: {
    from_summary: boolean
    from_memory: boolean
    from_recent_messages: boolean
    from_docs: boolean
    from_artifacts: boolean
  }
}
```

这样可以让 report runtime 不需要知道：

- 哪些字段来自 memory
- 哪些字段来自 active_context
- 哪些字段只是 builder 内部逻辑

---

## 6. `gathered_context` 的演进建议

当前 `gathered_context` 只有：

- `summary`
- `recent_messages`
- `active_task`
- `active_artifact`

对 report 先行方案，建议不要直接删除这层，而是升级它的内容。

### 6.1 第一阶段升级方式

建议将 `gathered_context` 演进为：

```py
gathered_context = {
    "summary": report_input["source_summary"],
    "current_topics": report_input["current_topics"],
    "confirmed_facts": report_input["confirmed_facts"],
    "teaching_issues": report_input["teaching_issues"],
    "student_signals": report_input["student_signals"],
    "evidence_points": report_input["evidence_points"],
    "constraints": report_input["constraints"],
    "recent_messages": report_input["recent_relevant_messages"],
    "active_artifact": {
        "artifact_id": report_input.get("active_artifact_id"),
        "artifact_type": report_input.get("active_artifact_type"),
    },
    "current_course_id": report_input.get("current_course_id"),
    "referenced_artifact_ids": report_input["referenced_artifact_ids"],
    "source_scope": report_input["source_scope"],
}
```

### 6.2 为什么不直接把这些字段提到顶层

因为当前 report engine 已经显式依赖 `gathered_context` 这个槽位。

先把结构化内容放进 `gathered_context`，是对现有链路侵入最小的做法。

### 6.3 后续是否提顶层

后续如果 report engine 某些节点需要更直接访问：

- `confirmed_facts`
- `constraints`
- `evidence_points`

可以逐步从 `gathered_context` 中挑高价值字段提升为 engine 顶层 state，但这不应是第一阶段目标。

---

## 7. 现有代码的最小改造点

本节只定义承接位置，不展开成任务清单。

### 7.1 存储层

在 `ConversationStoreAdapter` / `conversation_storage` 一侧补齐：

- `conversation_summary`
- `conversation_memory`
- `active_context`

对应入口：

- [conversation_store_adapter.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/persistence/conversation_store_adapter.py)
- [conversation_storage.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/core/conversation_storage.py)

### 7.2 上下文读取层

保留现有 `ContextBuilder`，但让它能读取：

- summary
- memory
- active_context

并把这些原材料交给新的 `GenerationContextBuilder`。

### 7.3 report 组装层

新增：

- `GenerationContextBuilder`
- `ReportAssembler`

建议放在 `app/chat/orchestrator` 或相邻上下文构建目录中，不要塞进 runtime。

### 7.4 runtime 层

`ReportWorkflowRuntime` 从“自己拼 gathered_context”改为：

- 接收 `ReportInput`
- 仅做 state 装配与调用

---

## 8. 第一阶段建议保留的旧逻辑

为了降低改造风险，report 先行阶段不建议一次性推翻所有旧逻辑。

### 8.1 保留 `summary`

即使引入 `ConversationMemory`，`summary_text` 仍然保留，并继续作为 report 骨架材料之一。

### 8.2 保留 `recent_messages`

但从“最近消息”改为“最近相关消息”。

这层仍有价值，因为：

- Memory 不覆盖所有短期细节
- 有些用户刚给出的局部要求还没沉淀进 summary

### 8.3 保留 `workflow_state`

report engine 仍需要知道：

- 当前是否在追问
- 是否已软确认
- 是否已确认大纲

因此 workflow_state 不应移除。

### 8.4 保留 `selected_doc_ids`

这是当前系统里已经成熟的强上下文信号，应继续保留。

---

## 9. 第一阶段建议下沉的旧逻辑

### 9.1 runtime 直接理解历史消息

runtime 不应再承担：

- 从 `recent_messages` 中自己抽主题
- 自己推断事实
- 自己判断对象引用

这些应下沉到 builder / assembler。

### 9.2 report engine 对“聊天原文”的隐式依赖

如果底层某些节点过度依赖原始输入，应逐步调整为优先消费：

- `confirmed_facts`
- `constraints`
- `teaching_issues`
- `evidence_points`

### 9.3 临时状态拼装分散在多个入口

目前 reply 和 report 有不同入口，后续上下文拼装逻辑不应在二者内部分叉，应该共用 builder。

---

## 10. 第一阶段的成功标准

report 先行承接方案的成功，不是“一次性完成全部重构”，而是满足以下判断：

### 10.1 输入更稳定

同一会话中多次触发 report 时：

- 上下文材料一致性更高
- 不再明显依赖最近 20 条消息窗口的偶然性

### 10.2 report runtime 更轻

runtime 只做：

- state 装配
- engine 调用
- 结果规范化

而不做复杂上下文理解。

### 10.3 对话沉淀开始真正被消费

`conversation_summary / conversation_memory / active_context` 不只是“存了”，而是真的成为 report 输入来源。

### 10.4 为后续资源复用提供模板

一旦 report 跑通，后续资源只需复制同一范式：

- `GenerationContextBuilder`
- `<Resource>Assembler`
- `<Resource>WorkflowRuntime`

---

## 11. 风险与防守点

### 11.1 风险：一次性改太多层

如果同时重写：

- 存储
- builder
- runtime
- engine 节点

会导致问题难以定位。

**建议：** 第一阶段只改“上下文供给方式”，尽量不改 report engine 内部状态机行为。

### 11.2 风险：把 `GenerationContext` 做得过重

如果一上来把所有想象中的字段都塞进去，会让 builder 复杂度暴涨。

**建议：** 先按 `GenerationContextMVP` 打通 report。

### 11.3 风险：结构化状态质量不稳定

如果 `ConversationMemory` 的 merge 规则未先收口，report 输入会更脏而不是更稳。

**建议：** 先依赖前述 merge 规范，只让第一批核心字段进入 report。

### 11.4 风险：runtime 与 engine 语义不匹配

如果 assembler 输出字段与 engine 当前期待的语义不对齐，会出现“有字段但不好用”。

**建议：** 第一阶段保持 `gathered_context` 容器不变，只升级其内容。

---

## 12. 推荐演进顺序

### 阶段 A：先补状态来源

- 补 `conversation_summary`
- 补 `conversation_memory`
- 补 `active_context`

### 阶段 B：补 builder 与 assembler

- `GenerationContextBuilder`
- `ReportAssembler`

### 阶段 C：runtime 改为消费 `ReportInput`

- 保持 engine 不变
- 优先替换上下文注入方式

### 阶段 D：再逐步优化 report engine 内部节点

- 让 extractor / evaluator / outliner 更稳定消费结构化材料

---

## 13. 最终收口

report 先行承接方案的核心判断只有四句：

1. **第一条要落地的不是“全资源统一”，而是“report 先吃上统一上下文”。**
2. **现有 report 链路已经有 `gathered_context` 这个天然承接点，不需要推倒重来。**
3. **`GenerationContextBuilder` 负责统一取材，`ReportAssembler` 负责 report 专属压缩，runtime 不负责理解整段会话。**
4. **第一阶段的目标不是重写 report engine，而是把结构化沉淀真正送进 report 输入。**

如果继续推进，下一步最适合做的是基于这份文档写一份真正的 implementation plan，把：

- 新增对象
- 改造位置
- 测试策略
- 回归范围

全部落成任务清单。
