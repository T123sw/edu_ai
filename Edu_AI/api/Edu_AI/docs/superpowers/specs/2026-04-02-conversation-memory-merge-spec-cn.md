# 对话记忆字段级 Merge 规范草案
**状态：** 草案，可作为后续实现与评审依据  
**日期：** 2026-04-02  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`  
**依赖基线文档：**
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-conversation-memory-generation-context-design-cn.md`

## 1. 文档目的

本文档用于把“对话记忆与生成上下文设计稿”中的原则，进一步收敛成**字段级可执行 merge 规则**。

它不负责定义所有实现细节，也不直接替代代码层接口设计，但它必须回答以下问题：

- 每个核心字段从哪里来
- 每轮对话后如何更新
- 是追加、覆盖、升级还是降级
- 如何去重
- 如何处理冲突
- 何时过期或退出 active 状态

本文档的目标是让后续实现不再依赖口头理解，而是依赖统一规则。

---

## 2. Merge 系统的总原则

### 2.1 以增量更新为主

状态维护不是每轮全量重建，而是：

- 原始消息 append-only
- Memory 做字段级增量合并
- Summary 按阈值压缩更新
- ActiveContext 按任务和产物变化实时切换

### 2.2 以“稳定复用信息”为目标

只有未来高概率再次被生成任务使用的信息，才应进入 Memory。

### 2.3 事实、推断、建议必须分开

- 用户明确陈述或多轮确认的信息，才能进入 `confirmed_facts`
- assistant 的推断、建议、分析，不应直接写成事实
- 证据点可以保留较弱信号，但必须带来源和置信度

### 2.4 merge 优先级高于抽取能力

系统的稳定性主要取决于 merge 规则，而不是抽取结果有多聪明。

### 2.5 允许状态退场

不是所有进入状态的信息都要永久保活。

需要支持：

- 降权
- 覆盖
- supersede
- 退出 active

---

## 3. 核心状态更新节奏

### 3.1 每轮必做

在每次用户轮次完成后，至少执行：

1. 追加消息
2. 抽取本轮最小信号
3. 合并到 `ConversationMemory`
4. 更新 `ActiveContext`

### 3.2 按阈值执行

满足以下任一条件时，刷新 `ConversationSummary`：

- 连续新增 3~5 轮有效对话
- 最近未压缩消息达到长度阈值
- 关键节点强更新触发

### 3.3 关键节点强更新

以下事件发生时，需要执行更严格的 merge：

- 用户确认结论
- 用户确认大纲
- 用户切换资源类型
- 用户显式要求生成资源
- workflow 状态变化
- artifact 生成成功
- workflow 中断或完成

---

## 4. 字段级规则总览

本草案先覆盖以下第一批核心字段：

- `current_topics`
- `user_goals`
- `confirmed_facts`
- `constraints`
- `teaching_issues`
- `student_signals`
- `evidence_points`
- `selected_doc_ids`
- `referenced_artifact_ids`
- `last_confirmed_output_type`
- `ActiveContext`

这几类字段足以支撑第一阶段 report 先行改造。

---

## 5. `current_topics` 规则

### 5.1 字段职责

表示当前对话正在围绕的主要主题，而不是会话历史里出现过的所有主题。

### 5.2 建议内部结构

持久化可继续暴露为 `string[]`，但内部 merge 建议采用带权结构：

```ts
type TopicState = {
  name: string
  score: number
  first_seen_at: string
  last_seen_at: string
  source_message_ids: string[]
}
```

### 5.3 数据来源

来源于：

- 本轮用户输入中的新主题
- 用户确认的课程主题、知识点
- 当前活跃资源的主题回指

### 5.4 更新方式

- 新 topic 出现：新增，初始 `score = 1`
- 已存在 topic 再次出现：`score + 1`
- 在连续 2~3 轮中被重复提及：提升为高优先级 topic
- 与当前 workflow 或当前课程直接相关：额外加权

### 5.5 去重规则

去重粒度采用“语义归并”，至少要合并明显同义表达。

例如：

- “课堂纪律”
- “纪律问题”
- “课堂秩序”

应尽量归并到同一个主题簇。

### 5.6 降级与过期

- 若一个 topic 在最近若干轮中未再出现，则按窗口衰减 `score`
- 当 `score` 低于阈值时，不再暴露到 `current_topics`
- 过期 topic 可保留在内部历史结构中，但不应继续污染生成上下文

### 5.7 冲突处理

`current_topics` 一般不做冲突覆盖，只做权重迁移。

---

## 6. `user_goals` 规则

### 6.1 字段职责

表示用户当前想达成的任务目标，允许并存多个，但必须有优先级。

### 6.2 建议内部结构

```ts
type GoalState = {
  goal: string
  priority: number
  status: "candidate" | "active" | "completed" | "superseded"
  first_seen_at: string
  last_seen_at: string
  source_message_ids: string[]
}
```

### 6.3 数据来源

来源于用户明确表达的目标：

- 分析问题
- 生成报告
- 生成教案
- 生成练习
- 改写已有产物

### 6.4 更新方式

- 明确出现新目标：新增为 `candidate`
- 同一目标被再次强调：提高 `priority`
- 进入对应 workflow：置为 `active`
- 目标已完成：置为 `completed`
- 被新目标替代：置为 `superseded`

### 6.5 去重规则

目标按“任务语义”去重。

例如：

- “帮我整理成报告”
- “生成一份汇报”

如果语义等价，应归并为一个 goal。

### 6.6 覆盖规则

`user_goals` 不是单值字段，不是简单覆盖。

但以下情况应切换当前主目标：

- 用户明确说“先别做报告了”
- 用户明确说“改成教案”
- workflow 已切换到新资源类型

### 6.7 过期规则

- `completed` 或 `superseded` 的 goal 不应继续作为主目标参与生成
- 历史 goal 可保留，但应在 `GenerationContext` 中默认排除

---

## 7. `confirmed_facts` 规则

### 7.1 字段职责

表示已经确认、可稳定复用的事实信息。

### 7.2 建议内部结构

建议内部使用 richer 结构，外部可只暴露 confirmed 项：

```ts
type FactItem = {
  content: string
  status: "candidate" | "confirmed" | "superseded"
  confidence: "high" | "medium" | "low"
  source_message_ids: string[]
  source_doc_ids?: string[]
  source_artifact_ids?: string[]
  first_seen_at: string
  last_updated_at: string
}
```

### 7.3 数据来源

来源仅限：

- 用户明确陈述的事实
- 文档或 artifact 中明确可引用的事实
- 多轮重复确认后沉淀的事实

默认不接受：

- assistant 推断
- 一次性猜测
- 未确认建议

### 7.4 更新方式

- 新事实首次出现：进入 `candidate`
- 同一事实再次出现，或被用户明确确认：升级为 `confirmed`
- 事实来自可靠文档或已确认 artifact：可直接高置信进入 `confirmed`

### 7.5 去重规则

按语义去重，而不是按字面字符串去重。

例如：

- “前10分钟学生分心明显”
- “课堂开场阶段学生注意力容易分散”

可视为同一事实簇。

### 7.6 冲突处理

如果新事实与已确认事实冲突：

- 不直接覆盖旧事实
- 将旧事实降级为 `superseded`
- 新事实成为 `candidate` 或 `confirmed`
- 记录冲突来源，供后续排查

### 7.7 过期规则

事实一般不因时间自动过期，但会因用户修正或新证据出现而 `superseded`。

---

## 8. `constraints` 规则

### 8.1 字段职责

表示对生成结果有直接约束作用的条件。

### 8.2 结构要求

不建议长期持久化为简单 `string[]`，建议采用槽位结构：

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

### 8.3 数据来源

来源于用户显式约束，例如：

- 面向家长
- 更正式
- 控制在 800 字
- 高一物理
- 不要太学术

### 8.4 更新方式

- 槽位型字段：采用“最新有效值覆盖”
- `style_notes`：去重后追加

### 8.5 覆盖规则

以下字段默认最新值覆盖旧值：

- `audience`
- `tone`
- `length`
- `grade_level`
- `subject`

例如：

- “简短一点” 后来变为 “详细一点”

则 `length` 槽位应直接切换，而不是并存。

### 8.6 去重规则

- `style_notes` 对字符串去重
- 同义约束尽量归并到已有槽位

### 8.7 失效规则

如果用户明确否定旧约束：

- 旧槽位值失效
- 不应继续进入后续 `GenerationContext`

---

## 9. `teaching_issues` 规则

### 9.1 字段职责

表示已经抽象出的教学问题点。

### 9.2 数据来源

来源于：

- 用户明确描述的问题
- 多个 observation / evidence 归纳出的稳定问题

### 9.3 更新方式

- 首次出现时进入 issue pool
- 被多轮支持或被用户认可后进入核心 issue

### 9.4 去重规则

按问题簇合并。

例如：

- “开场吸引力不足”
- “课堂开场抓不住学生”

应尽量归并为一类问题。

### 9.5 升级规则

只有在以下条件满足时才进入核心 `teaching_issues`：

- 有直接用户表述
- 或有多个高相关证据支持

### 9.6 冲突处理

如果后续用户否定问题判断：

- 原问题降级或移出核心问题集合
- 保留证据链，不直接删除底层 evidence

---

## 10. `student_signals` 规则

### 10.1 字段职责

表示对学情、参与、注意力、理解难点等的观察性信号。

### 10.2 数据来源

来源于：

- 用户的观察描述
- 文档中的学习表现记录
- 已确认 artifact 中的学情结论

### 10.3 更新方式

- 新信号出现：加入候选
- 与已有信号高相似：合并并增强置信度
- 被反复提及：升级为稳定信号

### 10.4 与 `teaching_issues` 的关系

- `student_signals` 偏观察层
- `teaching_issues` 偏归纳层

原则上：

- signal 可先存在
- issue 可基于多个 signal 派生

不建议反过来用 issue 替代 signal。

---

## 11. `evidence_points` 规则

### 11.1 字段职责

保存支撑事实、问题和信号的证据。

### 11.2 建议结构

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

### 11.3 数据来源

来源于：

- 用户直接给出的观察
- 文档数据
- 已生成 artifact 中被接受的案例或引用

### 11.4 更新方式

- 新证据点出现：新增
- 证据内容与已有项近似：合并来源，不重复新增
- 被事实或问题引用次数增加：提高置信度

### 11.5 去重规则

去重键建议综合以下维度：

- 标准化后的 `content`
- `type`
- 来源对象

如果只是字面改写，但指向同一 observation，应合并到同一证据项。

### 11.6 过期规则

证据一般不主动过期，但低置信弱证据可以在压缩阶段被降权，不进入 `GenerationContext`。

---

## 12. `selected_doc_ids` 与 `referenced_artifact_ids` 规则

### 12.1 `selected_doc_ids`

#### 职责

表示用户当前显式选中的文档集合。

#### 更新方式

- 用户主动选中文档：写入并替换当前集合
- 用户取消选择：从集合移除
- 显式切换文档组：整体替换

#### 规则

- 这是当前上下文型字段，不建议无限累积
- 默认应以“当前选择”为准

### 12.2 `referenced_artifact_ids`

#### 职责

表示对话中被引用过、后续可能复用的 artifact。

#### 更新方式

- 本轮引用某 artifact：追加
- 生成新 artifact：加入引用集合

#### 去重规则

- 按 `artifact_id` 去重

#### 保留策略

- 可保留最近 N 个高价值 artifact
- 已被替代但仍有引用价值的 artifact 保留在引用层
- 只有 `active_artifact` 参与当前主链路

---

## 13. `last_confirmed_output_type` 规则

### 13.1 字段职责

记录最近一次被用户明确确认的资源类型。

### 13.2 更新方式

以下情况更新：

- 用户明确要求“生成报告 / 教案 / 练习 / PPT”
- 用户明确从一个资源切换到另一个资源
- workflow 成功进入某资源类型主路径

### 13.3 覆盖规则

这是单值字段，以最新确认值为准。

### 13.4 使用方式

用于帮助理解如下语句：

- “继续改这个”
- “按刚才那个方式再来一个”
- “基于上一个结果继续”

---

## 14. `ActiveContext` 规则

### 14.1 字段职责

表示当前对话真正活跃的对象与任务状态。

### 14.2 建议结构

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

### 14.3 更新事件

#### 普通 reply 完成

- 若无 workflow 切换，则保留当前 `active_workflow_type`
- 如仅是普通问答，可更新 `active_task_id`

#### 进入 workflow

写入：

- `active_workflow_type`
- `active_workflow_status`
- `active_task_id`

#### 生成 artifact 成功

写入：

- `active_artifact_id`
- `active_artifact_type`

#### workflow awaiting_confirm

- 保持 `active_workflow_type`
- `active_workflow_status = awaiting_confirm`
- 当前 artifact 保持 active

#### workflow completed

- `active_workflow_status = completed`
- `active_task_id` 可清空
- 最近产物仍可作为 `active_artifact`

#### workflow interrupted

- 清空 `active_task_id`
- `active_workflow_status = interrupted`
- 是否保留 `active_artifact` 取决于是否已产生有效产物

#### 用户显式切换任务

例如：

- “先别写报告了”
- “改成教案”

则：

- 原 workflow 退出 active
- 新 workflow 进入 active
- 原 artifact 转入 `referenced_artifact_ids`

### 14.4 规则重点

- `ActiveContext` 是当前态，不是历史全集
- 它解决的是对象指代问题，而不是内容摘要问题

---

## 15. `ConversationSummary` 刷新规则

### 15.1 职责

压缩当前对话阶段的主线信息。

### 15.2 刷新触发

满足以下任一条件时刷新：

- 新增有效轮次达到阈值
- 有关键确认动作
- 进入资源生成前
- Memory 压缩阶段被触发

### 15.3 刷新方式

建议采用：

**旧 summary + 最近高价值增量 -> 新 summary**

而不是每次从零总结全部会话。

### 15.4 失败策略

如果 `summary` 刷新失败：

- 不应阻塞主回复
- 应记录失败并保留旧 summary
- 在下一次压缩窗口重试

---

## 16. 写回规则表

### 16.1 普通 `reply` 完成后

必须写回：

- 新增 `MessageRecord`
- 轻量更新 `current_topics`
- 轻量更新 `user_goals`
- 轻量更新 `constraints`
- 更新 `ActiveContext.updated_at`

可选写回：

- `ConversationSummary`
- `evidence_points`

### 16.2 `reply` 命中 report 意图

必须写回：

- `user_goals` 加入或提升“生成报告”
- `last_confirmed_output_type = report`
- `ActiveContext.active_workflow_type = report`
- `ActiveContext.active_workflow_status = running`

### 16.3 artifact 创建成功

必须写回：

- `referenced_artifact_ids`
- `ActiveContext.active_artifact_id`
- `ActiveContext.active_artifact_type`

### 16.4 workflow `awaiting_confirm`

必须写回：

- `ActiveContext.active_workflow_status = awaiting_confirm`

### 16.5 workflow `completed`

必须写回：

- `ActiveContext.active_workflow_status = completed`
- `active_task_id` 清空或转历史

### 16.6 workflow `interrupted`

必须写回：

- `ActiveContext.active_workflow_status = interrupted`
- `active_task_id` 清空

如无有效产物，可清空 `active_artifact`

---

## 17. 实现优先级建议

第一批最值得先写死规则的是：

1. `constraints`
2. `confirmed_facts`
3. `evidence_points`
4. `current_topics`
5. `user_goals`
6. `ActiveContext`

原因：

- 这些字段最直接影响 report 输入稳定性
- 这些字段最容易因为 merge 不清导致状态变脏

---

## 18. 最终收口

这份 merge 规范草案的核心判断是：

1. **Memory 不是 append-only 文本仓库，而是字段级状态系统。**
2. **不同字段必须有不同的 merge 策略，不能统一用“追加”或“覆盖”。**
3. **系统是否稳定，关键不在于抽取得多细，而在于 merge、冲突和退场规则是否清晰。**

后续进入实现前，建议基于本文档再补两份配套文档：

- `GenerationContext` 字段分级表
- 状态写回与事件流转表
