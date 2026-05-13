# 报告生成工作流重构设计（修订版）：上下文整理驱动、关键缺口追问、软确认后生成

## 1. 设计目标

本次重构不是继续修补旧的报告槽位，而是把报告 workflow 的入口哲学从：

`补槽位 -> 判断是否充分 -> 多轮追问 -> 生成`

改成：

`整理上下文 -> 形成报告准备结果 -> 判断是否可生成 -> 必要时追问关键缺口 -> 软确认/直接生成`

核心目标有四个：

1. 先消费和整理对话上下文，而不是先对旧槽位做缺口检查。
2. 让报告引擎承接“整理后的报告输入结构”，而不是承接零散聊天信息。
3. 保留“是否足以生成”的判断，但把它改造成基于报告可写性的判断，而不是基于旧槽位完整性的判断。
4. 让追问降级成例外分支，只在关键缺口存在时触发。


## 2. 当前问题

当前 report-first 链路已经具备上下文注入能力，但仍存在三个结构性问题：

1. 报告工作流仍然以旧槽位模型为核心入口。
2. 对话上下文虽然被注入，但没有先被系统性整理成“报告生成输入结构”。
3. 旧的充分性评估机制，尤其是 `focus_assessor`，会把“还可以更具体”错误地当成“不能生成”的理由。

这导致用户体验上出现：

- 用户已经聊了很多，系统还像第一次见到用户一样继续追问。
- 有效信息注入了 report workflow，但没有稳定落到可生成输入上。
- 本来已经够生成一版报告的场景，被反复追问打断。


## 3. 新的总体流程

### 3.1 主流程

新的报告工作流应调整为：

`对话上下文 + 当前请求`
-> `GenerationContext`
-> `ReportContextOrganizer (LLM)`
-> `ReportPreparationResult`
-> `GenerationReadinessJudge`

然后分成两条路径：

#### 路径 A：信息已足够

`ReportPreparationResult`
-> `StrongSoftConfirm / WeakSoftConfirm / DirectGenerate`
-> `ReportGenerator`

#### 路径 B：信息不足

`ReportPreparationResult`
-> `AskCriticalGap`
-> `补全关键缺口`
-> `重新整理`
-> `重新判断`
-> `SoftConfirm`
-> `ReportGenerator`


### 3.2 流程原则

新的流程必须遵守以下原则：

1. 先整理，再判断，再决定是否追问。
2. 追问是兜底分支，而不是默认主流程。
3. 只要已经能够组织出一版“方向明确、结构成立、可继续迭代”的报告骨架，就应允许先生成。
4. 可增强信息的缺失，不应默认阻止生成。


## 4. 新的报告准备结构

旧的 `core_topic / focus_area / length_requirement / depth_level / format_style / dynamic_constraints` 可以保留为兼容映射层，但不再作为 report workflow 的主结构。

新的主结构应是 `ReportPreparationResult`。


## 5. ReportContextOrganizer

### 5.1 定位

`ReportContextOrganizer` 是新的入口核心节点。

它负责：

1. 吃进当前 `GenerationContext`
2. 用 LLM 进行跨轮整理、聚合、消歧
3. 输出“报告是否可以生成”的准备结果

它不是旧槽位提取器的加强版，而是“报告生成前的上下文整理器”。


### 5.2 输入

`ReportContextOrganizer` 的输入应至少包括：

- 当前请求
- `GenerationContext`
  - summary
  - topics
  - goals
  - constraints
  - key memory
  - evidence
  - recent relevant messages
  - selected docs / course / artifacts


### 5.3 输出 Schema

第一版建议统一输出为：

```ts
type ReportContextSummary = {
  subject_summary: string
  focus_summary?: string
  key_points: string[]
  evidence_points: EvidencePoint[]
  constraints: ConstraintState
  source_scope: string[]
}

type ReportPreparationResult = {
  report_intent: "generate_report" | "unclear"
  report_subject?: string
  report_focus?: string

  report_context_summary: ReportContextSummary

  key_points: string[]
  evidence_points: EvidencePoint[]
  constraints: ConstraintState

  source_scope: {
    from_conversation: boolean
    from_docs: boolean
    from_course: boolean
    from_artifacts: boolean
  }

  open_questions: string[]
  missing_critical_fields: Array<"report_subject" | "report_focus" | "report_intent">
  confidence: "low" | "medium" | "high"

  soft_confirm_message: string
  followup_candidates: string[]
}
```


## 6. 新的字段分层

### 6.1 硬关键项

真正的硬关键项建议只保留两个：

- `report_intent`
- `report_subject`

原因：

- 没有 `report_intent`，系统不知道是不是应该进入报告生成。
- 没有 `report_subject`，系统无法组织出一版有效报告。


### 6.2 半关键项

`report_focus` 不建议被定义成绝对硬关键项。

它应被视为“半关键项”：

- 有明确 `report_focus` 时，系统按聚焦型报告生成。
- 没有明确 `report_focus` 时，只要 `report_subject` 明确、上下文足够，也允许生成综合型报告。

此时系统可以自动补出默认 focus，例如：

- `综合分析当前主题下的主要问题与结论`
- `围绕当前主题形成结构化综合报告`

这样可以避免重新回到“focus 缺一点就反复追问”的旧问题。


### 6.3 重要增强项

这些字段会显著提升质量，但不应默认阻止生成：

- `key_points`
- `evidence_points`
- `constraints`
- `source_scope`
- `current_course_id`
- `selected_doc_ids`
- `referenced_artifact_ids`


## 7. report_context_summary 的定义

`report_context_summary` 不应被视为“一段普通摘要文本”，而应被视为报告生成前的“压缩上下文包”。

它至少应包含：

- 当前主题如何理解
- 当前重点如何理解
- 已知关键观点
- 已知证据
- 已知约束
- 来源范围

因此，在内部实现上，应优先将其作为结构化产物维护，必要时再拼接成自然语言提示。


## 8. GenerationReadinessJudge

### 8.1 判断问题

新的判断问题不是：

- 槽位是否都填满了
- focus 是否已经足够精细

而是：

**当前是否已经能组织出一版“可写”的报告骨架？**

如果答案是能，就不该继续追问。


### 8.2 可生成判定规则

建议第一版把“可生成”判断写成明确规则表。

#### 可直接进入生成前确认

满足以下前提：

- `report_intent = generate_report`
- `report_subject` 存在

并且满足以下任一条件：

- `report_focus` 存在
- `key_points.length >= 2`
- `evidence_points.length >= 2`
- `report_context_summary` 质量高，足以组织一版综合型报告
- 最近相关消息足以表达清晰主线


#### 触发追问

仅在以下情况触发：

- `report_subject` 缺失
- `report_intent` 不清晰
- `report_subject` 与 `report_focus` 冲突明显
- 内容过于分散，无法组织出一版报告骨架


## 9. 追问机制

### 9.1 定位

追问不再是“补槽位”，而是“补最小关键缺口”。


### 9.2 追问类型

建议第一版只保留：

- `subject_missing`
  - 你希望这份报告围绕哪个主题来写？

- `focus_missing`
  - 你更希望这份报告重点展开哪个角度？

- `subject_focus_conflict`
  - 你更想写整体概述，还是只聚焦其中一个问题？

- `intent_unclear`
  - 你是想继续分析，还是现在直接生成报告？


### 9.3 追问原则

1. 一次只问一个问题。
2. 只问最影响生成的关键问题。
3. 不追问可增强信息。
4. 一旦关键缺口补齐，立即重新进入整理与可生成判断。


## 10. 软确认机制

软确认不应该只有一种形式，而应分档。

### 10.1 强软确认

适用场景：

- 从普通 `reply` 自然切入 report
- 用户表达“根据上面内容生成报告”
- 系统需要确认自己理解的主题和重点是否正确

形式：

- 明确问一句，等待用户确认后再生成


### 10.2 弱软确认

适用场景：

- 用户显式点击“生成报告”按钮
- 当前主题和方向已经非常明确

形式：

- 在回复中直接说明：
  - 我将基于 X 和 Y 生成一版报告
  - 现在开始生成

不额外停下来等待确认。


### 10.3 直接生成

适用场景：

- 用户显式发起 report
- 上下文已经非常清晰
- 系统判断生成风险很低

此时允许跳过显式确认，直接生成。


## 11. 软确认文案

推荐统一模板：

`我将基于“{report_subject}”，重点围绕“{report_focus_or_default}”，结合当前对话内容先生成一版报告。可以直接开始吗？`

如果是弱软确认，则改写为：

`我将基于“{report_subject}”，重点围绕“{report_focus_or_default}”，结合当前对话内容开始生成一版报告。`


## 12. 和现有架构的映射

当前已经有：

`ConversationSnapshot -> GenerationContext -> ReportAssembler -> ReportRuntime`

重构后建议演进为：

`ConversationSnapshot`
-> `GenerationContextBuilder`
-> `ReportContextOrganizer`
-> `ReportPreparationResult`
-> `GenerationReadinessJudge`
-> `SoftConfirm / AskCriticalGap`
-> `ReportGenerator`

职责拆分如下：

- `GenerationContextBuilder`
  - 收敛会话状态、相关消息、文档、artifact

- `ReportContextOrganizer`
  - 理解当前上下文，并整理成报告准备结构

- `GenerationReadinessJudge`
  - 判断能否生成，是否要追问，追问哪一个关键问题

- `SoftConfirm / AskCriticalGap`
  - 负责用户交互

- `ReportGenerator`
  - 负责大纲/正文生成


## 13. 应降级或移除的旧逻辑

建议显著降级或移除以下逻辑：

1. 旧槽位模型不再作为 report workflow 主结构。
2. `focus_assessor` 不再作为默认硬门禁。
3. “还可以更具体”不再成为继续追问的充分理由。
4. 可增强信息缺失不再默认阻止生成。


## 14. 例子

### 14.1 场景 A：上下文足够，应直接走确认后生成

前面对话已经形成：

- `report_subject = 关羽北伐失败原因`
- `report_focus = 军资供应如何引发内部失和`
- 已有多个关键观点与证据

此时用户输入：

`请基于当前内容生成一份报告`

系统应执行：

1. `ReportContextOrganizer` 整理上下文
2. 形成 `ReportPreparationResult`
3. `GenerationReadinessJudge` 判断为“可生成”
4. 发起强软确认：
   - 我将基于“关羽北伐失败原因”，重点分析“军资供应如何引发内部失和”，先生成一版结构化报告。可以直接开始吗？
5. 用户确认后生成

此时不应再进入多轮追问。


### 14.2 场景 B：主题明确但 focus 不明确，也允许先生成

前面对话已经明确主题：

- `report_subject = Skills 与 MCP 的差异`

但 focus 不是单一显式字段。

同时上下文里已经有：

- 多个 key points
- 多个 evidence points
- 较高质量 summary

此时系统应允许整理为：

- `report_focus = 综合分析 Skills 与 MCP 的核心差异及适用场景`

然后直接走弱软确认或直接生成，而不是继续追问“你更想聚焦哪个点”。


### 14.3 场景 C：上下文不足，追问关键缺口

用户只说：

`帮我生成一份报告`

且前文没有有效上下文。

整理后得到：

- `report_intent = generate_report`
- `report_subject = missing`

此时应只追问：

- 你希望这份报告围绕哪个主题来写？

而不是一口气追问主题、focus、风格、长度、对象。


## 15. 设计结论

报告工作流的目标，不再是“把聊天内容补成旧槽位”，而是：

**先理解上下文，形成一份“可生成的报告准备结果”；再判断是否缺关键项；只有缺关键项时才追问，否则进行强软确认、弱软确认或直接生成。**

这会把 report workflow 从“槽位驱动追问优先”改造成“上下文理解优先、关键缺口追问兜底、够用即生成”的流程。
