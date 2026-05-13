# 对话状态卡片字段与映射设计（MVP）

**状态：** 草案，可作为对话界面状态卡片的产品与后端联调基线  
**日期：** 2026-04-03  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`  
**依赖文档：**
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-conversation-memory-generation-context-design-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-conversation-memory-merge-spec-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-generation-context-field-matrix-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-state-writeback-event-flow-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-report-first-context-integration-plan-cn.md`

## 1. 文档目的

本文档用于回答一个具体问题：

**在对话界面增加“当前系统状态卡片”时，前端应该显示哪些字段，后端应该真正存哪些状态，这两者之间如何映射。**

这份文档不是视觉设计稿，也不是完整实施计划。它的目标是给后续实现提供统一边界：

- 卡片显示什么
- 卡片不显示什么
- 哪些字段应长期持久化
- 哪些字段只应在运行时派生
- API 应如何承接

---

## 2. 核心结论

### 2.1 可行，而且值得做

对话系统已经不再只是“消息输入框 + 一条回复”，而是包含：

- 普通对话与 workflow 切换
- active artifact
- 课程与文档上下文
- 会话摘要与结构化记忆
- report 等资源生成入口

在这样的系统里，增加状态卡片可以同时提升：

- 可解释性
- 用户纠错效率
- workflow 承接能力
- 资源生成前的上下文可见性

### 2.2 不应持久化“卡片对象本身”

本方案的核心原则是：

**后端持久化的是支撑卡片的状态对象，前端显示的是从这些状态对象派生出来的 `StatusCardViewModel`。**

也就是说：

- 存 `ConversationSummary`
- 存 `ConversationMemory`
- 存 `ActiveContext`
- 存 `WorkflowState`
- 存 `CapabilityPolicy`
- 不单独把 `StatusCardVM` 当成数据库实体长期保存

这样可以避免：

- UI 字段演进反向污染后端契约
- 卡片文案变化导致数据模型频繁改动
- 同一状态在多处重复存储、相互不一致

---

## 3. 产品定位

状态卡片的定位不是“调试面板”，而是“对当前会话状态的用户友好解释层”。

它主要回答五个问题：

1. 当前系统在做什么
2. 当前系统理解到了什么
3. 当前系统用了哪些上下文来源
4. 当前系统受哪些约束
5. 当前系统希望用户下一步做什么

因此，卡片应优先展示：

- 当前任务
- 当前理解
- 当前来源
- 当前约束
- 当前等待事项

而不应直接展示：

- graph 节点名
- router 分数
- 模型中间推理过程
- 未确认推测
- 大段原始 summary 原文

---

## 4. MVP 展示原则

### 4.1 默认紧凑，支持展开

MVP 建议采用两层展示：

- 默认态：只显示最关键的 4 到 6 条信息
- 展开态：显示约束、能力开关、当前 artifact 等补充信息

### 4.2 以用户可改正为导向

卡片中的字段应优先选择“用户一眼看错就能纠正”的内容，例如：

- 目标理解错了
- 当前来源理解错了
- 当前模式理解错了
- 生成约束理解错了

### 4.3 以压缩后的稳定信息为主

卡片应主要消费：

- summary
- memory
- active context
- workflow state

而不是大段原始消息。

---

## 5. 前端展示模型建议

建议前端使用统一的 `StatusCardVM`，作为对话状态卡片的直接渲染模型。

```ts
type StatusCardVM = {
  mode: "chat" | "workflow"
  status_label: string
  workflow_label?: string

  topics: string[]
  goal?: string
  issues: string[]
  confirmed_facts: string[]

  source_labels: string[]
  active_artifact_label?: string

  waiting_label?: string
  suggested_actions: string[]

  audience?: string
  tone?: string
  length?: string
  grade_level?: string
  subject?: string

  allow_rag: boolean
  allow_web: boolean

  summary_hint?: string
}
```

### 5.1 字段分层

`StatusCardVM` 内字段建议分成三层：

#### A. 必显字段

- `mode`
- `status_label`
- `topics`
- `goal`
- `issues`
- `source_labels`
- `waiting_label`

#### B. 常用折叠字段

- `confirmed_facts`
- `active_artifact_label`
- `audience`
- `tone`
- `length`
- `grade_level`
- `subject`

#### C. 次要辅助字段

- `allow_rag`
- `allow_web`
- `summary_hint`
- `suggested_actions`

---

## 6. 后端状态来源建议

MVP 后端建议继续围绕以下五类状态对象组织数据。

### 6.1 `ConversationSummary`

用途：

- 提供当前会话的压缩主线
- 为卡片提供 `summary_hint`
- 在 memory 尚不完整时作为兜底说明

建议结构：

```ts
type ConversationSummary = {
  summary_text: string
  last_updated_at: string
}
```

### 6.2 `ConversationMemory`

用途：

- 提供主题、目标、问题点、事实、约束等结构化信息
- 为资源生成与状态卡片同时供数

建议重点字段：

```ts
type ConversationMemory = {
  current_topics: string[]
  user_goals: string[]
  confirmed_facts: string[]
  teaching_issues: string[]
  student_signals: string[]
  constraints: {
    audience?: string
    tone?: string
    length?: string
    grade_level?: string
    subject?: string
    extra_constraints: string[]
  }
  evidence_points: Array<Record<string, unknown>>
  referenced_artifact_ids: string[]
  last_updated_at?: string
}
```

### 6.3 `ActiveContext`

用途：

- 定义当前会话焦点对象
- 为卡片提供“当前模式、当前来源、当前活跃产物、当前课程/文档”

建议重点字段：

```ts
type ActiveContext = {
  active_workflow_type?: string
  active_workflow_status?: string
  active_workflow_phase?: string
  active_artifact_id?: string
  active_artifact_type?: string
  current_course_id?: string
  pinned_doc_ids: string[]
  pinned_message_ids?: string[]
  updated_at?: string
}
```

### 6.4 `WorkflowState`

用途：

- 表达当前 workflow 是否在运行、等待确认、已完成或被打断
- 为卡片生成 `waiting_label` 与 `workflow_label`

建议重点字段：

```ts
type WorkflowState = {
  workflow_id?: string
  workflow_type?: string
  status?: string
  phase?: string
  required_slots?: string[]
  filled_slots?: Record<string, unknown>
  artifact_ids?: string[]
}
```

### 6.5 `CapabilityPolicy`

用途：

- 显示当前是否允许文档检索与 web 检索

建议重点字段：

```ts
type CapabilityPolicy = {
  allow_rag: boolean
  allow_web: boolean
  selected_doc_ids: string[]
}
```

---

## 7. 前端字段与后端字段映射表

| 前端字段 | 主要来源 | 次级兜底 | 说明 |
| --- | --- | --- | --- |
| `mode` | `ActiveContext.active_workflow_type` / `WorkflowState.workflow_type` | 无 | 有 workflow 则为 `workflow`，否则为 `chat` |
| `status_label` | `WorkflowState.status` | `ActiveContext.active_workflow_status` | 显示为自然语言，如“普通对话”“报告生成中”“等待确认大纲” |
| `workflow_label` | `WorkflowState.workflow_type` | `ActiveContext.active_workflow_type` | 展示资源类型，如“报告”“教案”“练习” |
| `topics` | `ConversationMemory.current_topics` | `ConversationSummary.summary_text` 提取 | 控制在 2 到 5 条 |
| `goal` | `ConversationMemory.user_goals[0]` | `ConversationSummary.summary_text` 提取 | 第一目标优先 |
| `issues` | `ConversationMemory.teaching_issues` | `ConversationMemory.student_signals` | 控制在 2 到 5 条 |
| `confirmed_facts` | `ConversationMemory.confirmed_facts` | 无 | 用于展开态 |
| `source_labels` | `CapabilityPolicy.selected_doc_ids` + `ActiveContext.current_course_id` + `ActiveContext.active_artifact_id` + 会话本身 | 无 | 例如“当前会话”“已选文档 2 份”“当前课程”“报告草稿” |
| `active_artifact_label` | `ActiveContext.active_artifact_type` + `active_artifact_id` | `WorkflowState.artifact_ids[0]` | 建议后续接 artifact 元数据服务补 title |
| `waiting_label` | `WorkflowState.status` + `phase` + `required_slots` | `ActiveContext.active_workflow_status` | 例如“等待你确认大纲”“等待你补充报告对象” |
| `suggested_actions` | `WorkflowState.status` + `workflow_type` | 前端静态模板 | 例如“确认大纲”“补充对象”“继续生成” |
| `audience` | `ConversationMemory.constraints.audience` | 无 | 展开态 |
| `tone` | `ConversationMemory.constraints.tone` | 无 | 展开态 |
| `length` | `ConversationMemory.constraints.length` | 无 | 展开态 |
| `grade_level` | `ConversationMemory.constraints.grade_level` | 无 | 展开态 |
| `subject` | `ConversationMemory.constraints.subject` | 无 | 展开态 |
| `allow_rag` | `CapabilityPolicy.allow_rag` | 无 | 折叠显示 |
| `allow_web` | `CapabilityPolicy.allow_web` | 无 | 折叠显示 |
| `summary_hint` | `ConversationSummary.summary_text` | 无 | 只显示一段很短的压缩提示，不直接显示完整摘要 |

---

## 8. 字段派生规则

### 8.1 `mode`

派生规则：

1. 当存在 `workflow.state.status in {"running", "awaiting_confirm"}` 时，显示 `workflow`
2. 当 `ActiveContext.active_workflow_type` 非空且未明确结束时，显示 `workflow`
3. 其他情况显示 `chat`

### 8.2 `status_label`

建议优先做文案映射，而不是直接显示状态枚举值。

建议映射：

- `chat` + 无 workflow: `普通对话`
- `report` + `running`: `正在生成报告`
- `report` + `awaiting_confirm`: `等待你确认报告大纲`
- `lesson_plan` + `running`: `正在整理教案`
- `quiz` + `running`: `正在生成练习`
- `completed`: `当前流程已完成`
- `interrupted`: `当前流程已中断`

### 8.3 `topics`

来源优先级：

1. `ConversationMemory.current_topics`
2. `ConversationSummary.summary_text` 的轻量提取结果
3. 最近消息窗口中的高频主题词

展示约束：

- 默认展示不超过 3 条
- 展开态不超过 5 条

### 8.4 `goal`

来源优先级：

1. `ConversationMemory.user_goals[0]`
2. 当前 workflow 的目标动作
3. `summary_text` 中的主任务

### 8.5 `issues`

来源优先级：

1. `ConversationMemory.teaching_issues`
2. `ConversationMemory.student_signals`
3. `confirmed_facts` 中可解释为问题点的条目

### 8.6 `source_labels`

建议来源标签最少包含以下几类：

- `当前会话`
- `已选文档 N 份`
- `当前课程`
- `当前产物`

示例：

- `当前会话`
- `已选文档 2 份`
- `当前课程：高一物理`
- `当前产物：报告大纲草稿`

### 8.7 `waiting_label`

来源优先级：

1. `WorkflowState.status == awaiting_confirm`
2. `required_slots` 中仍缺项
3. `ActiveContext.active_workflow_status`
4. 否则为空

示例：

- `等待你确认大纲`
- `等待你补充报告对象`
- `等待你选择资料`

### 8.8 `suggested_actions`

MVP 可先采用模板化输出：

- 当 `awaiting_confirm` 时：`["确认并继续", "调整要求"]`
- 当缺少资料时：`["选择资料", "跳过资料直接生成"]`
- 当流程运行中时：`["继续生成"]`
- 当处于普通对话时：`["继续提问", "生成报告"]`

---

## 9. API 承接建议

### 9.1 MVP 推荐方案

推荐直接在现有 `ChatResponseV2` 中增加一个可选字段：

```ts
class ChatResponseV2 {
  message: Record<string, unknown>
  conversation: Record<string, unknown>
  action: Record<string, unknown>
  artifacts: Array<Record<string, unknown>>
  workflow?: Record<string, unknown>
  sources: Array<Record<string, unknown>>
  trace: Record<string, unknown>
  status_card?: StatusCardVM
}
```

推荐原因：

- 对话页每次收到新回复时，都能同步刷新卡片
- 不需要前端在每次回复后再额外请求一个状态接口
- 与当前 `reply` / `report` 双入口兼容

### 9.2 补充接口建议

为支持页面刷新后重建卡片，建议后续增加只读接口：

```ts
GET /api/chat/v2/conversations/{conversation_id}/status-card
```

返回：

```ts
type StatusCardResponse = {
  conversation_id: string
  status_card: StatusCardVM
}
```

该接口应由以下状态重新派生：

- `conversation_summary`
- `conversation_memory`
- `active_context`
- 最近一次 workflow 状态
- 当前 capability

### 9.3 不推荐方案

MVP 不建议：

- 单独新建 `status_card` 持久化表
- 在 workflow 内部每个节点直接拼 UI 文案
- 把前端卡片文案反向写入 memory

---

## 10. 与当前代码的映射关系

当前代码里，已经存在一部分适合直接承接状态卡片的数据来源。

### 10.1 已有可复用来源

- [conversation_snapshot.py](D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\conversation_snapshot.py)
  - 已包含 `summary`、`conversation_memory`、`active_context`、`referenced_artifact_ids`、`capability`
- [context_builder.py](D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\context_builder.py)
  - 已可从持久化状态中恢复上述结构
- [generation_context_builder.py](D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\generation_context_builder.py)
  - 已有一版 report-first 的结构化上下文派生逻辑
- [conversation_store_adapter.py](D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\persistence\conversation_store_adapter.py)
  - 已会写回 `active_context` 与 `referenced_artifact_ids`
- [response_builder_v2.py](D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\response_builder_v2.py)
  - 适合扩展 `status_card`
- [schemas_v2.py](D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\api\schemas_v2.py)
  - 适合增加 `StatusCardVM` 响应契约

### 10.2 当前还缺的部分

- 专门的 `StatusCardBuilder`
- 将 workflow 状态翻译成用户文案的映射层
- artifact id 到 artifact title 的轻量映射
- 页面刷新时单独获取卡片的只读接口
- `conversation_summary` / `conversation_memory` 的自动刷新链路

---

## 11. MVP 实现边界建议

第一版建议只做以下内容：

### 11.1 必做

- 在对话响应中返回 `status_card`
- 卡片显示：
  - 当前状态
  - 当前主题
  - 当前目标
  - 当前问题点
  - 当前来源
  - 当前等待事项
- 展开态显示：
  - audience
  - tone
  - length
  - allow_rag
  - allow_web

### 11.2 可后置

- artifact 标题精确显示
- doc title 精确显示
- “相关消息片段”展示
- 更细粒度的 workflow phase 文案
- 个性化建议动作

---

## 12. 最终建议

如果要做状态卡片，MVP 的最稳落地方式是：

1. 后端继续维护 `summary / memory / active_context / workflow / capability`
2. 新增一个 `StatusCardBuilder`，专门把状态派生成 `StatusCardVM`
3. 在 `ChatResponseV2` 中增加可选 `status_card`
4. 前端默认显示紧凑卡片，支持展开查看约束和能力状态

这张卡片最应该显示的不是系统内部技术细节，而是：

- 当前任务
- 当前理解
- 当前来源
- 当前约束
- 当前等待事项

一句话概括：

**状态卡片应是会话状态的可视化层，而不是新的状态存储层。**
