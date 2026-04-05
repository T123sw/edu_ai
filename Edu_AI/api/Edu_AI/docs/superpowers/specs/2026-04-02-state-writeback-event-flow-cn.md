# 对话状态写回与事件流转表
**状态：** 草案，可作为状态更新实现与评审依据  
**日期：** 2026-04-02  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`  
**依赖文档：**
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-conversation-memory-generation-context-design-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-conversation-memory-merge-spec-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-generation-context-field-matrix-cn.md`

## 1. 文档目的

本文档用于定义：

**当对话系统发生不同类型事件时，会话状态应该写回哪些字段，哪些字段要清理，哪些字段要保留，哪些字段只做轻量更新。**

它解决的不是“字段怎么 merge”，而是“什么事件触发什么写回动作”。

如果前两份文档回答的是：

- 状态应该长什么样
- 字段应该怎么 merge

那么本文档回答的是：

- 系统在什么时候触发这些 merge
- 哪些字段在该事件下必须写
- 哪些字段在该事件下不能乱写

---

## 2. 状态写回的总原则

### 2.1 写回由事件驱动，不由字段驱动

实现上不能让每个字段各自决定是否更新，而应由系统事件统一触发状态写回。

也就是：

- 先识别事件
- 再决定这类事件的写回范围
- 最后由字段级 merge 规则落地更新

### 2.2 轻量事件不触发重写

普通对话不应该每轮都全量刷新：

- `ConversationSummary`
- `ConversationMemory`
- `ActiveContext`

正确方式是：

- 普通事件做轻量更新
- 关键事件做强更新
- 压缩事件做摘要刷新

### 2.3 workflow 状态和内容状态要分开

以下两类状态不能混写：

- 内容状态：topics、facts、constraints、evidence
- 工作流状态：active workflow、active task、artifact、phase

### 2.4 写回必须允许“保留”和“退场”

并不是每次事件都在新增状态。

有些事件会：

- 延续当前 active 状态
- 覆盖旧状态
- 清空旧状态
- 将 active 对象降为 reference

---

## 3. 事件分类

本文档先定义第一批核心事件：

1. `user_turn_received`
2. `assistant_reply_completed`
3. `summary_refresh_triggered`
4. `resource_intent_confirmed`
5. `workflow_started`
6. `workflow_phase_changed`
7. `artifact_created`
8. `workflow_awaiting_confirm`
9. `workflow_completed`
10. `workflow_interrupted`
11. `task_switched_by_user`
12. `doc_selection_changed`
13. `course_context_changed`

其中：

- 1~3 属于通用对话事件
- 4~10 属于 workflow 事件
- 11~13 属于上下文切换事件

---

## 4. 状态对象范围

本文档中的写回动作涉及以下对象：

- `MessageRecord`
- `ConversationSummary`
- `ConversationMemory`
- `ActiveContext`
- `workflow_state`
- `active_artifact`

说明：

- `GenerationContext` 是临时构建对象，不在写回范围内
- 本文档只关注长期状态与当前会话状态

---

## 5. 事件级写回规则

### 5.1 `user_turn_received`

**触发时机：**

- 用户新消息进入系统

**必须写回：**

- 追加 `MessageRecord(user)`

**可做轻量更新：**

- 抽取 topic 信号
- 抽取 goal 信号
- 抽取 constraint 信号
- 抽取 fact / evidence 候选

**不应在此时做：**

- 强制刷新 `ConversationSummary`
- 覆盖 `ActiveContext.active_workflow_type`
- 提前写入 `last_confirmed_output_type`

**原因：**

- 这时还只是输入到达，尚未经过路由、理解和执行

---

### 5.2 `assistant_reply_completed`

**触发时机：**

- 普通回复已产生，且本轮没有进入新 workflow

**必须写回：**

- 追加 `MessageRecord(assistant)`

**建议轻量写回：**

- `ConversationMemory.current_topics`
- `ConversationMemory.user_goals`
- `ConversationMemory.constraints`
- `ConversationMemory.confirmed_facts` 中的候选项
- `ActiveContext.updated_at`

**保留策略：**

- 现有 `active_workflow_type` 保留不动
- 现有 `active_artifact` 不应因普通回复被清空

**不应在此时做：**

- 把 assistant 推断直接写成 `confirmed_facts`
- 重置当前 workflow 状态

---

### 5.3 `summary_refresh_triggered`

**触发时机：**

满足以下任一条件：

- 连续新增有效轮次达到阈值
- 最近未压缩消息达到长度阈值
- 关键确认动作发生
- 进入资源生成前需要稳定摘要

**必须写回：**

- 刷新 `ConversationSummary.summary_text`
- 更新 `ConversationSummary.last_updated_at`

**建议同时做：**

- `ConversationMemory` 轻压缩
- topics 降权
- 低价值候选状态清理

**失败策略：**

- 刷新失败不阻塞主链路
- 保留旧 summary
- 记录错误并允许下一窗口重试

---

### 5.4 `resource_intent_confirmed`

**触发时机：**

- 用户明确要求生成某类资源
- 或系统路由已高置信判断资源类型

例如：

- “帮我整理成一份报告”
- “基于上面的内容生成教案”
- “按刚才那份结果出一套练习”

**必须写回：**

- `ConversationMemory.user_goals`
- `ConversationMemory.last_confirmed_output_type`

**建议写回：**

- 对应资源类型相关的 intent hint

**不应在此时做：**

- 直接写 `workflow_completed`
- 直接覆盖 `active_artifact`

**原因：**

- 这一步只确认“要生成什么”，不等于生成成功

---

### 5.5 `workflow_started`

**触发时机：**

- 某资源 workflow 被真正拉起

**必须写回：**

- `ActiveContext.active_workflow_type`
- `ActiveContext.active_workflow_status = running`
- `ActiveContext.active_task_id`
- `workflow_state.workflow_type`
- `workflow_state.status = running`
- `workflow_state.stage`

**建议写回：**

- `ConversationMemory.last_confirmed_output_type`

**保留策略：**

- 已有 `active_artifact` 默认保留，直到新 artifact 产生后再决定切换

---

### 5.6 `workflow_phase_changed`

**触发时机：**

- workflow 内部 phase / stage 变化

**必须写回：**

- `workflow_state.stage`
- `workflow_state.status`（若有变化）
- `ActiveContext.active_workflow_status`（若有变化）

**不一定写回：**

- `ConversationMemory`
- `ConversationSummary`

**原因：**

- phase 变化本质上是流程推进，不一定意味着内容态发生变化

---

### 5.7 `artifact_created`

**触发时机：**

- 新 artifact 成功生成

**必须写回：**

- `referenced_artifact_ids`
- `ActiveContext.active_artifact_id`
- `ActiveContext.active_artifact_type`
- `workflow_state.artifacts`

**建议写回：**

- 若 artifact 带来稳定内容，可更新：
  - `confirmed_facts`
  - `last_confirmed_outline`
  - `evidence_points`

**切换规则：**

- 新 artifact 成为当前 active artifact
- 旧 active artifact 不删除，降为 referenced artifact

---

### 5.8 `workflow_awaiting_confirm`

**触发时机：**

- workflow 进入等待用户确认阶段

**必须写回：**

- `ActiveContext.active_workflow_status = awaiting_confirm`
- `workflow_state.status = awaiting_confirm`

**保留策略：**

- 当前 active artifact 保持 active
- 当前 active workflow 保持 active

**不应在此时做：**

- 清空 active task
- 把 workflow 标记为 completed

---

### 5.9 `workflow_completed`

**触发时机：**

- workflow 正常完成

**必须写回：**

- `ActiveContext.active_workflow_status = completed`
- `workflow_state.status = completed`

**建议写回：**

- 清空 `ActiveContext.active_task_id`
- 保留最终 `active_artifact`
- 更新 `ConversationMemory.last_confirmed_output_type`

**保留策略：**

- 已产出的最终 artifact 继续保留为 active artifact
- workflow 本身可以 completed，但对象仍然是“当前最近主对象”

---

### 5.10 `workflow_interrupted`

**触发时机：**

- workflow 被用户中断
- workflow 失败退出
- workflow 被新任务抢占

**必须写回：**

- `ActiveContext.active_workflow_status = interrupted`
- `workflow_state.status = interrupted`

**建议写回：**

- 清空 `ActiveContext.active_task_id`

**清理规则：**

- 若 workflow 未生成有效 artifact，则不设置新 `active_artifact`
- 若 workflow 已生成中间 artifact，可保留为 referenced artifact

**不应直接做：**

- 大面积清空 `ConversationMemory`
- 删除已有历史 artifact 引用

---

### 5.11 `task_switched_by_user`

**触发时机：**

- 用户显式切换任务方向

例如：

- “先别写报告了”
- “改成教案”
- “基于刚才那个报告生成 PPT”

**必须写回：**

- `ConversationMemory.user_goals`
- `ConversationMemory.last_confirmed_output_type`
- `ActiveContext.active_workflow_type`
- `ActiveContext.active_workflow_status`

**切换规则：**

- 旧 workflow 退出 active
- 新 workflow 成为 active
- 旧 active artifact 降为 referenced artifact
- 若新任务依赖旧 artifact，则保留引用链

**特别注意：**

- 任务切换不是状态清空
- 它更像是 active 焦点迁移

---

### 5.12 `doc_selection_changed`

**触发时机：**

- 用户显式改变当前选中文档集合

**必须写回：**

- `ConversationMemory.selected_doc_ids`
- `ActiveContext.pinned_doc_ids`

**更新方式：**

- 当前选择整体替换旧选择

**不应在此时做：**

- 追加历史文档集合

**原因：**

- 文档选择是当前上下文，不是历史全集

---

### 5.13 `course_context_changed`

**触发时机：**

- 用户明确切换课程
- 或请求显式带入新的 `course_id`

**必须写回：**

- `ActiveContext.current_course_id`

**建议写回：**

- 根据课程上下文更新 `current_topics`
- 根据课程变化重新评估相关 artifact 的活跃性

**切换规则：**

- 课程变更不应自动清空所有 Memory
- 但应降低旧课程相关 topic / issue / signal 的活跃度

---

## 6. 事件到状态对象的映射矩阵

以下用简化矩阵表达“这类事件一般更新哪些对象”：

| 事件 | MessageRecord | ConversationSummary | ConversationMemory | ActiveContext | workflow_state |
| --- | --- | --- | --- | --- | --- |
| `user_turn_received` | 必写 | 不写 | 轻更新 | 轻更新 | 不写 |
| `assistant_reply_completed` | 必写 | 视阈值 | 轻更新 | 轻更新 | 不写 |
| `summary_refresh_triggered` | 不写 | 必写 | 压缩更新 | 不写 | 不写 |
| `resource_intent_confirmed` | 不写 | 可选 | 强更新 | 可选 | 不写 |
| `workflow_started` | 不写 | 可选 | 可选 | 必写 | 必写 |
| `workflow_phase_changed` | 不写 | 不写 | 不写 | 可选 | 必写 |
| `artifact_created` | 不写 | 可选 | 可选 | 必写 | 必写 |
| `workflow_awaiting_confirm` | 不写 | 不写 | 不写 | 必写 | 必写 |
| `workflow_completed` | 不写 | 可选 | 可选 | 必写 | 必写 |
| `workflow_interrupted` | 不写 | 不写 | 不写 | 必写 | 必写 |
| `task_switched_by_user` | 不写 | 可选 | 强更新 | 必写 | 可选 |
| `doc_selection_changed` | 不写 | 不写 | 必写 | 必写 | 不写 |
| `course_context_changed` | 不写 | 可选 | 可选 | 必写 | 不写 |

---

## 7. 推荐实现形态

建议实现一个统一状态写回器，而不是把逻辑散在 `reply_service`、`report_service`、`workflow runtime` 中。

例如：

```ts
type ConversationStateUpdater = {
  onUserTurnReceived(...)
  onAssistantReplyCompleted(...)
  onSummaryRefreshTriggered(...)
  onResourceIntentConfirmed(...)
  onWorkflowStarted(...)
  onWorkflowPhaseChanged(...)
  onArtifactCreated(...)
  onWorkflowAwaitingConfirm(...)
  onWorkflowCompleted(...)
  onWorkflowInterrupted(...)
  onTaskSwitchedByUser(...)
  onDocSelectionChanged(...)
  onCourseContextChanged(...)
}
```

推荐职责边界：

- `reply / report / runtime` 负责发出事件
- `ConversationStateUpdater` 负责决定写回范围
- 各字段 merge 逻辑由 `MemoryMerger` 一类组件执行

这样能避免：

- 不同入口各自维护一套状态写回逻辑
- 同一事件在不同入口表现不一致

---

## 8. 与当前系统的衔接建议

基于当前已有代码结构，推荐以下接入顺序：

### 8.1 第一阶段

先在现有 `write_v2_result` 一类落点中接入：

- `assistant_reply_completed`
- `resource_intent_confirmed`
- `workflow_started`
- `artifact_created`
- `workflow_completed`
- `workflow_interrupted`

### 8.2 第二阶段

再接入摘要与压缩类事件：

- `summary_refresh_triggered`

### 8.3 第三阶段

最后补齐显式上下文切换类事件：

- `task_switched_by_user`
- `doc_selection_changed`
- `course_context_changed`

这样推进的好处是：

- 先打通 report 主链路
- 再增强状态稳定性
- 最后完善跨资源切换体验

---

## 9. 最终收口

这份写回与事件流转表，核心上只想固定三件事：

1. **状态更新应以事件为入口，而不是在各字段上零散触发。**
2. **普通对话、workflow 推进、对象切换，是三类不同的写回场景，不能混在一起。**
3. **系统稳定性的关键，不只是字段怎么 merge，更是事件发生时该写什么、不该写什么。**

下一步如果继续往实施推进，最顺的动作就是基于这份文档补一份：

**`report` 先行承接方案**

也就是把：

`ContextBuilder -> GenerationContextBuilder -> ReportAssembler -> ReportWorkflowRuntime`

这一条链路具体写出来。
