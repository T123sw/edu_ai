# 对话记忆与生成上下文设计稿
**状态：** 已整理，可作为后续规划基线与长期参考  
**日期：** 2026-04-02  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`  
**关联文档：**
- `D:\Edu_AI_1\Edu_AI\docs\对话信息维护.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-app-chat-v2-frontend-aligned-design-cn.md`

## 1. 文档目的

本文档不是实施计划，也不是字段枚举清单的最终版，而是一份面向后续规划和长期维护的设计基线。

它要解决的是同一个核心问题：

**系统如何在多轮对话中持续沉淀高价值信息，并在生成报告、教案、练习、PPT 提纲等资源时稳定承接这些信息，而不是反复全量回扫聊天历史。**

本文档的目标有三个：

- 统一团队对“对话状态维护”问题的理解
- 明确后续数据结构设计和工程改造的方向
- 为后面的 implementation plan、字段定义文档、测试设计提供依据

---

## 2. 问题重述

当前系统已经具备以下基础能力：

- 保存原始对话消息
- 在会话 `state` 中保存部分业务状态
- 在 `reply` 和 `report` 两条链路中通过 `ContextBuilder` 组装上下文
- 在报告工作流中使用 `summary`、`recent_messages`、`active_artifact` 等信息

但当前结构仍然偏轻：

- `ContextBuilder` 主要组装的是“最近消息快照”，还不是“生成可复用上下文”
- `ConversationSnapshot` 目前无法稳定表达结构化记忆
- `report runtime` 仍然直接依赖 `recent_messages + summary`
- 其他资源类型未来若接入，容易各自重复造一套“从聊天里抽上下文”的逻辑

因此，我们要解决的不是“要不要做摘要”，而是：

1. 哪些信息应该长期沉淀
2. 这些信息应该沉淀到哪一层
3. 多轮对话中如何增量更新这些状态
4. 资源生成工作流如何统一承接这些状态

---

## 3. 设计结论

本设计采用以下总原则：

**原始消息持续保存 + 轻量结构化记忆增量沉淀 + 生成时按需组装通用上下文 + 各资源工作流只消费已整理后的输入。**

对应地，明确拒绝两种极端：

### 3.1 不采用“生成时才临时全量总结”

原因：

- 时延高
- 成本高
- 长对话下结果不稳定
- 容易遗漏已经确认过的约束、对象和结论

### 3.2 不采用“每轮维护一份很重的最终产物态”

原因：

- 容易脏
- 用户试探性表达会污染结构化状态
- 会让状态越来越难维护
- 不利于多种资源类型复用

### 3.3 采用“分层记忆模型 + 通用生成上下文”

核心链路：

**原始消息层 -> 轻量摘要层 -> 结构化记忆层 -> 活跃对象层 -> GenerationContext -> 资源专用 assembler -> workflow runtime**

---

## 4. 分层状态模型

### 4.1 原始消息层 `MessageRecord`

这是事实留痕层，必须完整保存，但不直接作为生成主输入。

建议职责：

- 记录完整用户、助手、工具消息
- 支持回溯、审计、排错
- 在摘要不够时提供兜底回扫来源

建议字段：

```ts
type MessageRecord = {
  message_id: string
  conversation_id: string
  role: "user" | "assistant" | "system" | "tool"
  content: string
  created_at: string
  attachments?: string[]
  cited_artifact_ids?: string[]
  cited_doc_ids?: string[]
  sources?: Array<Record<string, unknown>>
}
```

设计要求：

- append-only
- 不做语义修正
- 不把推断写进事实层

---

### 4.2 轻量摘要层 `ConversationSummary`

这是给后续生成用的压缩版会话理解，不是完整报告草稿。

建议职责：

- 压缩当前对话阶段的主线信息
- 保留最重要的主题、结论、正在推进的任务
- 降低后续工作流对长历史消息的依赖

建议字段：

```ts
type ConversationSummary = {
  conversation_id: string
  summary_text: string
  last_updated_at: string
  covered_message_range?: {
    start_message_id?: string
    end_message_id?: string
  }
}
```

内容约束：

- 不写成长文
- 不逐轮复述
- 聚焦当前主线

---

### 4.3 结构化记忆层 `ConversationMemory`

这是整个方案最关键的一层。

它不保存“完整理解”，而保存“未来高概率复用的信息”。

建议字段：

```ts
type ConversationMemory = {
  conversation_id: string

  current_topics: string[]
  user_goals: string[]
  confirmed_facts: string[]
  open_questions: string[]

  constraints: ConstraintState
  audience_hints: string[]
  tone_hints: string[]

  key_knowledge_points: string[]
  teaching_issues: string[]
  student_signals: string[]
  evidence_points: EvidencePoint[]
  extracted_requirements: ResourceIntentHint[]

  selected_doc_ids: string[]
  referenced_artifact_ids: string[]

  last_confirmed_output_type?: string
  last_confirmed_outline?: string
  last_updated_at: string
}
```

配套子结构：

```ts
type ConstraintState = {
  audience?: string
  tone?: string
  length?: string
  grade_level?: string
  subject?: string
  style_notes: string[]
}
```

```ts
type EvidencePoint = {
  type: "observation" | "data" | "example" | "quote" | "requirement"
  content: string
  source: "user_message" | "assistant_summary" | "document" | "artifact"
  confidence?: "high" | "medium" | "low"
  source_message_ids?: string[]
  source_doc_ids?: string[]
  source_artifact_ids?: string[]
}
```

```ts
type ResourceIntentHint = {
  target_type: "report" | "lesson_plan" | "quiz" | "ppt_outline" | "flashcard" | "summary"
  signal: string
  strength: "weak" | "medium" | "strong"
}
```

这层要特别注意：

- 只沉淀高价值、稳定、可复用信息
- 区分“确认过”与“只是提过”
- 不把 assistant 的分析结论直接升格为事实

---

### 4.4 活跃对象层 `ActiveContext`

这是解决“根据上面的内容”“把刚才那个变成报告”这类指代问题的关键。

建议字段：

```ts
type ActiveContext = {
  conversation_id: string

  active_task_id?: string
  active_workflow_type?: string
  active_workflow_status?: string

  active_artifact_id?: string
  active_artifact_type?: string

  pinned_doc_ids: string[]
  pinned_message_ids: string[]
  current_course_id?: string

  updated_at: string
}
```

这层的作用不是总结内容，而是明确“当前对象是谁”：

- 当前课程是谁
- 当前正在跑什么 workflow
- 当前产物是什么
- 当前用户显式选择了哪些文档或消息

---

### 4.5 通用生成上下文 `GenerationContext`

这是临时态，不是长期存储层。

它在用户触发资源生成时构建，用于统一承接各层沉淀。

建议字段：

```ts
type GenerationContext = {
  conversation_id: string
  course_id?: string

  summary_text: string
  current_topics: string[]
  user_goals: string[]
  confirmed_facts: string[]
  open_questions: string[]

  constraints: ConstraintState
  key_knowledge_points: string[]
  teaching_issues: string[]
  student_signals: string[]
  evidence_points: EvidencePoint[]

  selected_doc_ids: string[]
  referenced_artifact_ids: string[]

  active_workflow_type?: string
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

设计要求：

- 所有资源 workflow 优先消费它
- 不让 runtime 自己回扫完整会话
- 把上下文抽取责任前置到 builder / assembler 层

---

## 5. 该存什么，不该存什么

### 5.1 应该提前沉淀的

- 当前讨论主题
- 用户目标
- 已确认事实
- 明确的问题点
- 学情信号
- 证据点
- 输出约束
- 当前课程、文档、artifact、workflow 引用
- 最近确认的输出类型与大纲

### 5.2 不应重度沉淀的

- 闲聊和寒暄
- 模糊试探
- 尚未确认的猜测
- assistant 的推断性结论
- 长篇逐轮 paraphrase
- 一次性修辞表达

判断标准只有一句话：

**未来的生成任务是否高概率会再次使用这条信息。**

---

## 6. 多轮对话的状态更新策略

本方案将状态维护定义为一个**增量同步系统**，而不是每轮重算整段会话。

### 6.1 每轮必做：轻量更新

每次用户发言后，至少做以下动作：

1. 追加原始消息
2. 抽取本轮最小信号
3. 更新活跃对象引用

本轮抽取信号只关注：

- 是否出现新 topic
- 是否出现新 goal
- 是否出现新 constraint
- 是否出现新 fact
- 是否引用文档或 artifact
- 是否触发 workflow 切换意图

这一步要尽量轻，不应让主回复明显阻塞。

### 6.2 每 3~5 轮：压缩更新

在以下条件满足时刷新摘要和压缩记忆：

- 已连续多轮对话
- 会话 token / 长度达到阈值
- 结构化状态开始堆积重复信息

动作包括：

- 刷新 `summary_text`
- 合并重复 facts / issues / constraints
- 给 topic 降权
- 清理过期 active 状态

### 6.3 关键节点：强更新

以下情况触发一次更可靠的状态更新：

- 用户说“就按这个来”
- 用户确认结论或大纲
- 用户给出关键数据、案例、观察
- 用户切换任务类型
- 用户要求生成资源
- workflow 进入新阶段
- 生成 artifact 成功

强更新的目标不是更长，而是更准。

---

## 7. 状态合并规则

真正决定系统是否“越聊越稳”的，不是抽取能力，而是 merge 规则。

### 7.1 去重

语义相近的信息不能无脑累加。

例如：

- “学生参与度不高”
- “课堂参与偏低”
- “回答不积极”

应合并为同一问题簇，而不是 3 条独立核心问题。

### 7.2 覆盖

有些字段应采用“最新有效值为准”：

- audience
- tone
- length
- grade_level
- subject
- 当前目标资源类型

### 7.3 升级

有些信息应分层提升可信度，而不是一出现就进核心状态：

- 候选事实 -> 已确认事实
- 临时问题 -> 核心问题
- 一次性例子 -> 证据点

### 7.4 降级与过期

长对话中，旧状态必须允许退场：

- 长时间未提及的 topic 降权
- 已被覆盖的 constraint 标记失效
- 已完成 workflow 的 active task 退出
- 被新 artifact 替代的旧 artifact 仅保留引用

### 7.5 冲突处理

不要直接把旧状态覆盖掉。

建议内部保留状态位，例如：

```ts
type FactItem = {
  content: string
  status: "candidate" | "confirmed" | "superseded"
  source_message_ids: string[]
  updated_at: string
}
```

这样在用户修正前述说法时，可以把旧结论降级为 `superseded`，避免生成时喂入互相矛盾的材料。

---

## 8. 通用生成上下文的承接方式

所有资源生成不应直接扫描整段聊天历史，而应统一走中间层：

**Message / Summary / Memory / ActiveContext -> GenerationContextBuilder -> Resource Assembler -> Workflow Runtime**

### 8.1 `GenerationContextBuilder`

建议增加独立 builder：

```ts
type GenerationContextBuilder = {
  buildForResource(
    conversationId: string,
    resourceType: "report" | "lesson_plan" | "quiz" | "ppt_outline" | "flashcard",
    options?: {
      selectedDocIds?: string[]
      activeArtifactId?: string
      recentMessageLimit?: number
    }
  ): GenerationContext
}
```

职责：

- 从长期状态中取主骨架
- 从最近消息中取局部补充
- 在必要时回扫更早原始消息
- 对外统一产出 `GenerationContext`

### 8.2 Resource-specific Assembler

各资源只负责把通用上下文压缩成专属输入，不再自己分析原始聊天。

例如：

- `reportAssembler.from(context)`
- `lessonPlanAssembler.from(context)`
- `quizAssembler.from(context)`
- `pptOutlineAssembler.from(context)`

这样做的收益：

- 行为一致
- 方便测试
- token 更省
- 新资源接入更快

---

## 9. 各类资源如何承接沉淀

### 9.1 报告生成

优先使用：

- `summary_text`
- `confirmed_facts`
- `teaching_issues`
- `evidence_points`
- `constraints`
- 最近相关消息

### 9.2 教案生成

优先使用：

- `current_topics`
- `key_knowledge_points`
- `user_goals`
- `student_signals`
- `constraints`
- 当前课程与相关 artifact

### 9.3 练习 / 试题生成

优先使用：

- `key_knowledge_points`
- `student_signals`
- `teaching_issues`
- `constraints.length`
- 难度、题量等约束

### 9.4 PPT 提纲生成

优先使用：

- `summary_text`
- `current_topics`
- `last_confirmed_outline`
- 已有 report / lesson_plan artifact

### 9.5 Flashcard / 知识卡片生成

优先使用：

- `key_knowledge_points`
- `confirmed_facts`
- `evidence_points`
- 用户明确要求记忆的概念和定义

结论是：

**不同资源使用不同字段重心，但都应先消费统一的 `GenerationContext`。**

---

## 10. 与现有代码的映射关系

本节不写任务拆解，只说明当前结构与目标结构如何对齐。

### 10.1 现有已具备的基础

当前代码已经具备以下支点：

- `ConversationStoreAdapter`
- `ContextBuilder`
- `ConversationSnapshot`
- `WorkflowState`
- `active_artifact`
- `reply` / `report` 入口分离

说明当前架构不是推倒重来，而是沿现有主链路增强。

### 10.2 当前不足

当前不足主要体现在以下几点：

- 存储层仅有原始消息与零散 `state`
- `ContextBuilder` 只读取很薄的一层状态
- `ConversationSnapshot` 没有承载结构化记忆
- `report runtime` 仍偏向直接使用 `recent_messages`
- `memory_reader` 接口已存在，但未成为默认主路径

### 10.3 目标演进方向

建议的演进路径是：

1. 先在会话存储中补足 `conversation_summary`、`conversation_memory`、`active_context`
2. 再将 `ContextBuilder` 升级为可复用的 `GenerationContextBuilder`
3. 先让 `report` workflow 吃新的上下文
4. 再把其他资源类型逐步迁移到同一承接方式

---

## 11. 建议的 MVP 边界

第一批不要一次铺满所有字段，建议先做最小可落地版本。

### 11.1 MVP 必须有的对象

- `MessageRecord`
- `ConversationSummary`
- `ConversationMemory`
- `ActiveContext`
- `GenerationContext`

### 11.2 MVP 必须有的字段

```ts
type ConversationMemoryMVP = {
  conversation_id: string
  current_topics: string[]
  user_goals: string[]
  confirmed_facts: string[]
  constraints: ConstraintState
  teaching_issues: string[]
  evidence_points: EvidencePoint[]
  selected_doc_ids: string[]
  referenced_artifact_ids: string[]
  last_confirmed_output_type?: string
  last_updated_at: string
}
```

```ts
type ActiveContextMVP = {
  conversation_id: string
  active_workflow_type?: string
  active_workflow_status?: string
  active_artifact_id?: string
  active_artifact_type?: string
  current_course_id?: string
  pinned_doc_ids: string[]
  updated_at: string
}
```

MVP 的目标不是“最完整”，而是先打通：

- 多轮对话后生成报告
- 从报告切换到其他资源
- 基于当前课程和 artifact 做继续生成

---

## 12. 分阶段推进建议

### 阶段 1：先把概念落成字段规范

产出：

- 数据结构草案
- merge 规则
- 状态流转图

目标：

- 让后续改造有统一语义边界

### 阶段 2：先接入会话存储

产出：

- `conversation_summary`
- `conversation_memory`
- `active_context`

目标：

- 在不改 workflow 的前提下先把状态沉淀链路打通

### 阶段 3：优先让报告工作流承接

产出：

- `GenerationContextBuilder`
- `ReportAssembler`
- `report runtime` 改为消费结构化上下文

目标：

- 优先验证最典型场景

### 阶段 4：推广到其他资源工作流

产出：

- `lesson_plan`
- `quiz`
- `ppt_outline`
- `flashcard`

目标：

- 形成统一资源生成入口

---

## 13. 风险与注意事项

### 13.1 最大风险不是“抽不出来”，而是“状态变脏”

因此后续设计和测试要优先覆盖：

- 去重
- 冲突
- 覆盖
- 过期
- 错误升级

### 13.2 assistant 推断污染事实层

必须明确：

- `confirmed_facts` 只接受高置信、已确认信息
- 分析和建议不应默认写入事实层

### 13.3 先不要把所有生成场景一次性统一

正确顺序应该是：

- 先定通用上下文边界
- 先打通 report
- 再推广到其他资源

### 13.4 不要让 runtime 承担历史理解职责

runtime 的职责应是执行生成，不是做会话考古。

---

## 14. 最终设计判断

本设计的最终判断可以收敛为三句话：

1. **多轮对话状态维护，本质上是增量同步系统，而不是每轮重算。**
2. **资源生成工作流应消费统一的 `GenerationContext`，而不是各自扫描聊天历史。**
3. **真正应该长期沉淀的不是“完整推理过程”，而是“未来高概率复用的稳定信息与活跃对象”。**

---

## 15. 下一步建议

基于本文档，后续最值得优先产出的内容是：

1. 一份字段级 `merge` 规范
2. 一份 `ConversationMemory / ActiveContext / GenerationContext` 数据结构表
3. 一份面向现有代码的 implementation plan

如果后续进入实施阶段，应以本文档为设计基线，不再回到“每个 workflow 自己扫聊天历史”的实现方向。
