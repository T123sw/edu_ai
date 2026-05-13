# 对话状态字段 Schema 与 Merge/Guard 规则表
**状态：** 已整理，可作为下一阶段状态架构收口基线  
**日期：** 2026-04-05  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`

---

## 1. 文档目的

本文档用于把“对话状态维护优化方案”进一步收紧成可执行的状态边界规范，重点回答以下问题：

1. 对话状态层里到底有哪些字段类型
2. 每类字段的 `source of truth` 是什么
3. 哪些字段允许 LLM 产出 candidate，哪些不允许
4. 字段写入时该走什么 merge / guard 策略
5. `summary` 是否允许反向回灌
6. 长期状态与 workflow 工作区如何隔离

本文档不是 implementation plan，而是下一阶段状态层实现的约束基线。

---

## 2. 总体原则

### 2.1 LLM 不负责维护系统状态真相

LLM 的职责是：

- 生成候选语义结构
- 做主题收敛
- 做问题簇聚类
- 做 evidence 规范化
- 做阶段性压缩整理

LLM 不负责：

- 直接维护系统状态真相
- 直接覆盖长期状态
- 直接写入高风险字段

### 2.2 状态写入必须经过 source-aware merge / guard

任何字段写回长期状态前，都必须基于：

- 来源类型
- 置信度
- 新旧关系
- 生命周期
- 当前 workflow 状态

做裁决。

### 2.3 summary 是消费视图，不是事实源

`summary` 可以作为：

- 状态卡片消费层
- workflow 输入压缩层
- LLM 上下文整理的辅助层

但不能作为：

- 事实反向抽取源
- 长期状态再写回源
- 新 facts 的直接来源

### 2.4 长期状态与 workflow 工作区必须隔离

长期状态负责跨轮复用、稳定沉淀。  
workflow 工作区负责一次 report / lesson / quiz / ppt 生成中的临时工作变量。

二者可以有关联，但不能混同。

---

## 3. 状态字段分层

推荐把状态字段分成四类。

## 3.1 A 类：系统真相字段

定义：只能由系统事件、显式参数或持久化流程维护，LLM 不能直接写。

代表字段：

- `workflow_state`
- `active_context`
- `capability_policy`
- `selected_doc_ids`
- `current_course_id`
- `active_artifact_id`
- `active_artifact_type`

特点：

- 来源确定
- 生命周期明确
- 不允许语义推断覆盖

## 3.2 B 类：用户显式声明字段

定义：必须能追溯到用户原话或用户显式确认，不应由 assistant 总结替代。

代表字段：

- `explicit_user_goals`
- `explicit_user_constraints`
- `deliverable_requirements`
- `user_preferences`

特点：

- 必须保留来源痕迹
- assistant 可复述，但复述本身不是真相源
- 允许 merge，但优先用户最新明确声明

## 3.3 C 类：语义整理字段

定义：允许规则层和 LLM 增强层共同参与，但最终写入必须经过 guard。

代表字段：

- `summary_text`
- `current_topics`
- `teaching_issues`
- `student_signals`
- `evidence_points`
- `topic_clusters`
- `issue_clusters`

特点：

- 跨轮整合价值高
- 容易受污染
- 必须 source-aware

## 3.4 D 类：workflow 工作字段

定义：只服务某个 workflow，允许短生命周期存在，不默认写回长期状态。

代表字段：

- `report_subject`
- `report_focus`
- `report_outline`
- `lesson_objective_candidates`
- `quiz_scope_candidates`
- `ppt_section_plan`
- `selected_evidence_for_report`

特点：

- 生命周期短
- 更接近生成过程中的工作变量
- 可由 LLM 主导整理
- 默认不直接回写长期 memory

---

## 4. 字段 Schema 建议

## 4.1 系统真相字段

建议继续采用显式结构，不增加 LLM 痕迹字段：

```ts
type ActiveContext = {
  active_workflow_type?: string
  active_workflow_status?: string
  active_artifact_id?: string
  active_artifact_type?: string
  current_course_id?: string
  pinned_doc_ids: string[]
  updated_at: string
}
```

```ts
type WorkflowState = {
  workflow_id: string
  workflow_type: string
  status: string
  phase: string
  required_slots?: string[]
  filled_slots?: Record<string, unknown>
  artifact_ids?: string[]
}
```

## 4.2 用户显式声明字段

建议统一保留来源和 turn 信息：

```ts
type ExplicitField<T> = {
  value: T
  source_message_ids: string[]
  source_type: "user_message" | "user_confirmation"
  updated_at_turn: number
}
```

例如：

```ts
type ExplicitUserConstraint = ExplicitField<string>
type ExplicitUserGoal = ExplicitField<string>
```

## 4.3 语义整理字段

建议统一采用可追踪结构：

```ts
type SemanticState<T> = {
  value: T
  source_span_ids: string[]
  source_type: "rule" | "llm_candidate" | "tool_grounded" | "assistant_rephrase"
  confidence: "low" | "medium" | "high"
  updated_at_turn: number
  status: "active" | "stale" | "superseded" | "tentative"
}
```

例如：

```ts
type TopicState = SemanticState<string>
type IssueState = SemanticState<string>
type StudentSignalState = SemanticState<string>
```

## 4.4 Evidence 字段

建议单独强化 schema：

```ts
type EvidencePoint = {
  type: string
  content: string
  source_message_ids: string[]
  source_type: "assistant_message" | "user_message" | "tool_result" | "doc_result"
  confidence: "low" | "medium" | "high"
  updated_at_turn: number
  status: "active" | "stale" | "superseded"
}
```

## 4.5 Workflow 工作字段

建议单独挂在 workflow workspace 下：

```ts
type ReportWorkspace = {
  report_subject?: string
  report_focus?: string
  report_outline?: string[]
  selected_evidence?: EvidencePoint[]
  constraints?: Record<string, unknown>
  updated_at: string
}
```

---

## 5. 字段真相源与写入权限表

| 字段类型 | 代表字段 | 真相源 | 允许 LLM candidate | 允许直接写长期状态 | 备注 |
|---|---|---|---|---|---|
| 系统真相字段 | `workflow_state` `active_context` | 系统事件 / 显式参数 | 否 | 否 | 只能由系统逻辑写 |
| 系统真相字段 | `selected_doc_ids` `current_course_id` | 前端显式选择 / 路由参数 | 否 | 否 | 不能靠模型猜 |
| 用户显式声明字段 | `explicit_user_goals` | 用户原话 / 用户确认 | 否 | 是 | 需保留 message source |
| 用户显式声明字段 | `explicit_user_constraints` | 用户原话 / 用户确认 | 否 | 是 | assistant 复述不是真相源 |
| 语义整理字段 | `summary_text` | 规则候选 + LLM candidate + guard | 是 | 是 | 但不能反向回灌事实层 |
| 语义整理字段 | `current_topics` | 规则候选 + LLM candidate + guard | 是 | 是 | 需支持 stale / supersede |
| 语义整理字段 | `teaching_issues` | 规则候选 + LLM candidate + guard | 是 | 是 | 建议聚类后写入 |
| 语义整理字段 | `student_signals` | 规则候选 + LLM candidate + guard | 是 | 是 | 来源需可追踪 |
| 语义整理字段 | `evidence_points` | 规则候选 + LLM candidate + guard | 是 | 是 | 不同 source_type 权重不同 |
| 高风险事实字段 | `confirmed_facts` | 不建议继续宽泛保留 | 谨慎 | 谨慎 | 建议拆分，不再作为大桶字段 |
| workflow 工作字段 | `report_focus` `report_outline` | workflow organizer / runtime | 是 | 默认否 | 优先留在工作区 |

---

## 6. `confirmed_facts` 的处理原则

当前宽泛的 `confirmed_facts` 字段风险很高，建议后续逐步拆分，而不是继续让它承担所有“已确认信息”。

推荐拆成：

- `user_stated_facts`
- `user_confirmed_interpretations`
- `system_verified_facts`
- `llm_inferred_hypotheses`

其中：

### 6.1 `user_stated_facts`

- 来源：用户明确陈述
- 可长期保留
- 优先级高

### 6.2 `user_confirmed_interpretations`

- 来源：assistant 复述后，用户确认
- 可长期保留
- 但要保留确认链路

### 6.3 `system_verified_facts`

- 来源：tool/doc 检索、结构化结果、工作流系统验证
- 可长期保留
- 优先级高于 LLM 推断

### 6.4 `llm_inferred_hypotheses`

- 来源：LLM 推断
- 默认不进入长期事实层
- 如需保留，只能作为短生命周期候选

结论：

> 不建议继续维护一个无区分的大而全 `confirmed_facts` 桶。

---

## 7. Summary 的使用约束

`summary_text` 很重要，但必须强约束。

## 7.1 允许的用途

- 作为状态卡片摘要来源
- 作为 workflow 输入压缩视图
- 作为 LLM organizer 的辅助上下文

## 7.2 禁止的用途

- 禁止从 `summary_text` 反向抽取新 facts 写回长期状态
- 禁止把 `summary_text` 当成新的 topic 真相源
- 禁止通过 `summary -> facts -> summary` 形成回灌回路

## 7.3 原则

> summary 是消费视图，不是事实源。

---

## 8. Merge / Guard 裁决协议

## 8.1 冲突优先级

字段冲突时，建议按以下优先级处理：

1. 系统显式状态
2. 用户最新明确声明
3. 用户历史明确声明
4. tool / doc 可验证信息
5. LLM candidate
6. assistant 历史复述
7. summary 派生信息

说明：

- 越靠后，越不应该覆盖靠前字段
- summary 不能反向压过任何前面几层

## 8.2 更新动作类型

每个字段更新都必须落在以下动作之一：

- `append`
- `replace`
- `merge`
- `supersede_previous`
- `reject`
- `quarantine`

### 典型策略

#### 系统真相字段

- 只允许 `replace`
- 不允许 `merge`
- 不允许 LLM 写

#### 用户显式声明字段

- 最新明确声明通常 `replace` 或 `supersede_previous`
- 可保留历史轨迹

#### 语义整理字段

- 语义接近时 `merge`
- 语义冲突时 `supersede_previous` 或 `quarantine`
- 低置信度 candidate 可 `reject` 或 `tentative`

## 8.3 置信度策略

建议使用统一置信度调节：

- 来源单一、且为 assistant 推断：`low`
- 来源多轮重复、且用户侧支持：`medium`
- 来源可验证、跨轮稳定、或用户确认：`high`

LLM 产出的 candidate 默认不应直接获得 `high`。

## 8.4 stale / supersede / expiry

compactor 不仅负责压缩，还必须负责状态净化：

- 长时间未活跃 topic -> `stale`
- 被新主题明确覆盖的旧主题 -> `superseded`
- workflow residue -> 到期清理
- 临时 focus / 临时规划 -> 不进入长期状态，或快速过期

---

## 9. 长期状态与 workflow 工作区隔离规则

## 9.1 长期状态允许保留什么

适合长期保留的：

- 稳定主题
- 用户显式目标
- 用户显式约束
- 可验证 evidence
- 跨轮仍然有价值的问题簇

## 9.2 不应默认写回长期状态的内容

以下内容默认应留在 workflow 工作区：

- report focus 临时候选
- lesson objective 临时候选
- quiz scope 草案
- ppt section 草案
- 某次生成过程中筛选出的 section-level evidence
- 生成前的中间解释文本

## 9.3 允许从工作区回写长期状态的例外

只有满足以下条件时，才允许从 workflow 工作区回写长期状态：

- 用户明确确认
- 信息具备跨轮复用价值
- 信息不是模板化系统话术
- 信息不是某次生成过程中的临时结构

例如：

- 用户确认某个长期写作偏好
- 用户确认某个主题方向
- 用户确认某组稳定约束

---

## 10. 消息来源分层建议

建议在消息入库或抽取前先做来源标记：

- `user_content`
- `assistant_content`
- `assistant_meta`
- `workflow_control`
- `workflow_result`
- `system_instruction_like_text`

### 10.1 默认允许进入长期状态的来源

- `user_content`
- `tool/doc grounded result`
- 被用户确认的低变形 assistant 复述

### 10.2 默认不进入长期状态的来源

- `assistant_meta`
- `workflow_control`
- `system_instruction_like_text`
- 模板化确认话术
- 资源产物正文

原则：

> 生成出来的 report / lesson / ppt 文本本身，不应自动回灌成长期状态事实。

---

## 11. 状态事件日志建议

为了增强可观察性，建议在最终状态之外，保留轻量事件日志：

```ts
type StateUpdateEvent = {
  turn_id: number
  extractor_version: string
  trigger_type: string
  changed_fields: string[]
  previous_summary: Record<string, unknown>
  new_summary: Record<string, unknown>
  source_types: string[]
  decision_notes?: string[]
  created_at: string
}
```

这样才能回答：

- 为什么这个 topic 会出现
- 为什么这个 topic 被 supersede
- 哪次 compaction 把 focus 改掉了
- 某条污染从哪轮开始写进来的

---

## 12. 当前阶段最值得先补硬的部分

如果按工程优先级排序，建议如下：

### P0：先做消息来源分层 + 污染过滤

目标：

- 不再只靠文本模式去噪
- 先把 `user_content / assistant_meta / workflow_control / workflow_result` 分流

### P1：收紧字段 schema，明确真相源

优先字段：

- `confirmed_facts`
- `constraints`
- `user_goals`
- `summary_text`

### P2：接入按需 LLM 微抽取

第一批建议只做：

- topic convergence
- summary candidate
- issue clustering
- signal clustering
- evidence normalization

### P3：做 compactor / refiner

并加入：

- stale decay
- supersede
- workflow residue cleanup

### P4：资源生成前做 workflow-specific refine

并写清楚：

- 哪些结果允许回写长期状态
- 哪些只留在工作区

---

## 13. 最终结论

下一阶段状态架构的关键，不是“再多加几个字段”，而是把以下 5 件事写硬：

1. 字段真相源
2. 状态写入边界
3. summary 回灌限制
4. 长期状态与 workflow 工作区隔离
5. source-aware merge / guard 协议

一句话总结：

> **LLM 可以增强语义整理，但不能替代状态真相源；状态层必须由明确的字段边界、来源分层和 merge/guard 规则来托底。**
