# GenerationContext 字段分级表
**状态：** 草案，可作为 `GenerationContextBuilder` 与各资源 assembler 的设计依据  
**日期：** 2026-04-02  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`  
**依赖文档：**
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-conversation-memory-generation-context-design-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-conversation-memory-merge-spec-cn.md`

## 1. 文档目的

本文档用于回答一个非常具体的问题：

**`GenerationContext` 到底该包含哪些字段，哪些是所有资源生成都应该具备的骨架字段，哪些只是常用补充，哪些只在特定资源类型下才有价值。**

这份文档的目标不是继续扩张字段，而是给字段做分级，避免 `GenerationContext` 无限变重、无限泛化，最后重新退化成“另一份完整对话历史”。

---

## 2. 分级原则

### 2.1 通用必填字段

满足以下条件的字段进入“必填”层：

- 对大多数资源生成都直接有价值
- 缺失时会明显降低生成稳定性
- 可以从当前系统的会话状态中较稳定构建

### 2.2 常用可选字段

满足以下条件的字段进入“常用可选”层：

- 对多类资源有帮助
- 但不是所有请求都必须具备
- 缺失时不应阻塞 workflow

### 2.3 资源特有可选字段

满足以下条件的字段进入“资源特有可选”层：

- 只对某些资源类型有明显价值
- 更适合由 assembler 按资源类型选择性消费
- 不应强制所有 workflow 都背负这类字段

---

## 3. `GenerationContext` 总体结构建议

建议将 `GenerationContext` 分成五个逻辑区：

1. 会话骨架
2. 生成约束
3. 业务内容材料
4. 对象引用
5. 来源追踪

建议结构如下：

```ts
type GenerationContext = {
  conversation_id: string
  resource_type: "report" | "lesson_plan" | "quiz" | "ppt_outline" | "flashcard"

  summary_text: string
  current_topics: string[]
  user_goals: string[]
  confirmed_facts: string[]

  constraints: ConstraintState

  teaching_issues?: string[]
  student_signals?: string[]
  key_knowledge_points?: string[]
  open_questions?: string[]
  evidence_points?: EvidencePoint[]

  selected_doc_ids: string[]
  referenced_artifact_ids: string[]
  current_course_id?: string
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

注意：

- `GenerationContext` 是临时输入态，不是长期持久化对象
- 它的目标是“给生成工作流一份够用、稳定、可追踪的上下文”
- 它不应该重新变成“什么都装的大包袱”

---

## 4. 通用必填字段

这部分字段应被视为大多数资源 workflow 的最小骨架。

### 4.1 `conversation_id`

**分级：** 必填  
**原因：**

- 用于绑定生成请求与会话来源
- 用于 trace、状态写回、artifact 关联

### 4.2 `resource_type`

**分级：** 必填  
**原因：**

- 让 builder 和 assembler 明确本次上下文是为哪类资源准备
- 避免在 assembler 里重复推断

### 4.3 `summary_text`

**分级：** 必填  
**原因：**

- 这是压缩后的会话主线
- 几乎所有资源都需要一个稳定的对话主摘要

**约束：**

- 不能写成长文
- 应聚焦当前阶段最重要信息

### 4.4 `current_topics`

**分级：** 必填  
**原因：**

- 大多数资源都需要知道当前在谈什么
- topic 是比原始消息更稳定的语义骨架

### 4.5 `user_goals`

**分级：** 必填  
**原因：**

- 决定本次生成的任务导向
- 帮助区分“分析”“生成”“改写”“延展”这类不同动作

### 4.6 `confirmed_facts`

**分级：** 必填  
**原因：**

- 这是最稳定的材料层
- 没有这一层，workflow 就容易退回到从聊天原文里猜事实

### 4.7 `constraints`

**分级：** 必填  
**原因：**

- 约束直接影响输出样式、受众、长度、学科、年级
- 几乎所有资源生成都需要

### 4.8 `selected_doc_ids`

**分级：** 必填  
**原因：**

- 文档显式选择是非常强的上下文信号
- 即使为空，也应稳定存在

### 4.9 `referenced_artifact_ids`

**分级：** 必填  
**原因：**

- 很多生成任务是基于已有产物继续进行
- 即使没有 active artifact，也可能有重要引用 artifact

### 4.10 `recent_relevant_messages`

**分级：** 必填  
**原因：**

- 结构化状态并不覆盖所有短期局部语义
- 最近相关消息用于补足摘要与 memory 尚未收进来的细节

**约束：**

- 必须是“相关消息”，不是机械最近 N 条
- 应限制数量，避免退化成全量历史

### 4.11 `source_scope`

**分级：** 必填  
**原因：**

- 用于说明这次上下文到底从哪些层取了材料
- 有利于调试、评估和后续 trace

---

## 5. 常用可选字段

这部分字段对多类资源都有帮助，但缺失时不应阻塞生成。

### 5.1 `teaching_issues`

**分级：** 常用可选  
**常见使用方：**

- report
- lesson_plan
- quiz

**原因：**

- 对教学场景价值高
- 但不是所有生成任务都必须依赖

### 5.2 `student_signals`

**分级：** 常用可选  
**常见使用方：**

- report
- lesson_plan
- quiz

**原因：**

- 对学情相关生成非常有价值
- 但例如通用总结、PPT 提纲有时未必需要

### 5.3 `key_knowledge_points`

**分级：** 常用可选  
**常见使用方：**

- lesson_plan
- quiz
- flashcard
- ppt_outline

**原因：**

- 对知识型产物很重要
- 对纯问题分析型报告不是强必需

### 5.4 `open_questions`

**分级：** 常用可选  
**常见使用方：**

- report
- lesson_plan

**原因：**

- 可帮助生成中保留“未定项”与后续行动
- 但不是所有资源都必须带上

### 5.5 `evidence_points`

**分级：** 常用可选  
**常见使用方：**

- report
- lesson_plan
- quiz

**原因：**

- 它会显著提高输出可信度和具体性
- 但在某些轻量生成里，没有证据也不应阻塞流程

### 5.6 `current_course_id`

**分级：** 常用可选  
**常见使用方：**

- report
- lesson_plan
- quiz
- ppt_outline

**原因：**

- 对课程绑定型任务帮助很大
- 但并非所有对话都一定处于课程上下文内

### 5.7 `active_workflow_type`

**分级：** 常用可选  
**原因：**

- 对“从当前 workflow 继续生成”非常有帮助
- 但如果本次请求是独立生成，也可能没有值

### 5.8 `active_artifact_id`

**分级：** 常用可选  
**原因：**

- 对承接“基于刚才那个结果继续”的语义很重要
- 但不是每次都一定存在 active artifact

### 5.9 `active_artifact_type`

**分级：** 常用可选  
**原因：**

- 帮助 assembler 理解当前 active 对象是什么
- 和 `active_artifact_id` 配合使用时更有意义

---

## 6. 资源特有可选字段

这部分字段不建议放进所有资源的默认骨架，而应按资源类型选择性构建。

### 6.1 `last_confirmed_outline`

**分级：** 资源特有可选  
**主要适用：**

- report
- ppt_outline

**原因：**

- 对提纲延展类任务有帮助
- 对 quiz、flashcard 价值不大

### 6.2 `audience_hints`

**分级：** 资源特有可选  
**主要适用：**

- report
- lesson_plan

**说明：**

- 如果 `constraints.audience` 已足够稳定，则这类 hint 不一定需要进入顶层
- 更适合作为 builder 内部补充信息或 assembler 侧增强信息

### 6.3 `tone_hints`

**分级：** 资源特有可选  
**主要适用：**

- report
- lesson_plan
- summary

**说明：**

- 如果 `constraints.tone` 已覆盖主约束，则 hint 仅作补充

### 6.4 `resource_intent_hints`

**分级：** 资源特有可选  
**主要适用：**

- builder 内部决策
- workflow 路由增强

**说明：**

- 这类字段更偏系统内部使用
- 不建议默认暴露给所有 runtime

### 6.5 `candidate_evidence`

**分级：** 资源特有可选  
**主要适用：**

- report

**说明：**

- 如果还未升格为正式 `evidence_points`，更适合在 report assembler 内部有条件使用
- 不建议让所有资源都消费候选证据

---

## 7. 各资源推荐消费矩阵

本节不定义唯一规则，而给出推荐消费优先级。

### 7.1 report

**强依赖：**

- `summary_text`
- `confirmed_facts`
- `constraints`
- `recent_relevant_messages`
- `selected_doc_ids`

**推荐消费：**

- `teaching_issues`
- `student_signals`
- `evidence_points`
- `current_course_id`
- `active_artifact_id`

**特有增强：**

- `last_confirmed_outline`

### 7.2 lesson_plan

**强依赖：**

- `summary_text`
- `current_topics`
- `user_goals`
- `constraints`

**推荐消费：**

- `key_knowledge_points`
- `student_signals`
- `teaching_issues`
- `current_course_id`
- `referenced_artifact_ids`

### 7.3 quiz

**强依赖：**

- `current_topics`
- `constraints`
- `recent_relevant_messages`

**推荐消费：**

- `key_knowledge_points`
- `student_signals`
- `teaching_issues`
- `confirmed_facts`

### 7.4 ppt_outline

**强依赖：**

- `summary_text`
- `current_topics`
- `referenced_artifact_ids`

**推荐消费：**

- `confirmed_facts`
- `key_knowledge_points`
- `current_course_id`
- `active_artifact_id`

**特有增强：**

- `last_confirmed_outline`

### 7.5 flashcard

**强依赖：**

- `current_topics`
- `constraints`

**推荐消费：**

- `key_knowledge_points`
- `confirmed_facts`
- `evidence_points`

---

## 8. Builder 侧构建原则

### 8.1 必填字段必须总能构建出来

即使某些值为空，也应以稳定结构返回，例如：

- `selected_doc_ids: []`
- `referenced_artifact_ids: []`
- `recent_relevant_messages: []`
- `constraints.style_notes: []`

### 8.2 常用可选字段优先按资源类型构建

不要把所有可选字段都默认塞满。

正确方式是：

- 先确定 `resource_type`
- 再决定哪些常用可选字段值得补进上下文

### 8.3 资源特有可选字段尽量由 assembler 层感知

builder 可以提供原材料，但不必让所有 runtime 都看到这类字段。

### 8.4 不要让 `GenerationContext` 重新膨胀成“大而全快照”

如果某个字段满足以下任一特征，应谨慎进入顶层：

- 只有单一资源类型会用到
- 只是 builder 内部中间态
- 只是候选信号而非稳定材料

---

## 9. 推荐的最小 MVP 版本

如果第一版只做 report 先行，建议 `GenerationContext` 先保留以下字段：

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

这已经足够支撑：

- 多轮对话后生成报告
- 基于当前课程生成报告
- 基于当前 artifact 继续生成或改写报告

---

## 10. 最终建议

关于 `GenerationContext`，建议团队后续始终遵守以下三条：

1. **先定骨架字段，再谈资源增强字段。**
2. **builder 负责统一上下文构建，assembler 负责资源适配，runtime 不负责理解整段会话。**
3. **字段进入 `GenerationContext` 的标准不是“可能有用”，而是“对本次资源生成稳定有用”。**

---

## 11. 下一步建议

基于本文档，最顺的后续动作是：

1. 补一份“状态写回与事件流转表”
2. 补一份“report 先行承接方案”
3. 再进入 implementation plan

如果进入代码阶段，建议优先让 `report` workflow 消费这份字段分级后的 `GenerationContextMVP`，不要一开始就试图覆盖所有资源类型。
