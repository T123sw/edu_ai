# StatusCardBuilder 规则草案

**状态：** 草案，可作为状态卡片 MVP 的实现约束  
**日期：** 2026-04-03  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`  
**依赖文档：**
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-03-status-card-field-mapping-mvp-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-state-writeback-event-flow-cn.md`

## 1. 文档目的

本文档用于把状态卡片从“字段设计”推进到“可实现规则”。

它回答的是以下问题：

- `StatusCardBuilder` 的输入与输出是什么
- 这个 builder 是否应保持纯函数
- 各字段的优先级与回退规则是什么
- 文案映射层应放在哪里
- 低信息会话如何降级展示
- 状态卡片应在什么时候重建

这份文档不是视觉稿，也不是完整实现计划。它的目标是减少实现阶段的分叉与隐式规则。

---

## 2. 核心结论

### 2.1 `StatusCardBuilder` 应是派生层，而不是状态维护层

`StatusCardBuilder` 的职责是：

- 消费现有会话状态
- 生成一个可直接渲染的 `StatusCardVM`

它**不负责**：

- 写回数据库
- 刷新 summary
- 刷新 conversation memory
- 推进 workflow 状态
- 查询大范围历史消息

一句话说：

**Builder 只做“读状态 -> 派生视图”，不做“改状态 -> 维护状态”。**

### 2.2 Builder 应尽量保持纯函数

MVP 推荐：

```ts
build(snapshot, workflow_state, capability) -> StatusCardVM
```

更完整的输入可表示为：

```ts
build({
  snapshot,
  workflow_state,
  capability,
  label_resolver,
  label_mapper,
}) -> StatusCardVM
```

其中：

- `snapshot` 提供 summary / memory / active context
- `workflow_state` 提供当前流程状态
- `capability` 提供 rag/web 等能力开关
- `label_resolver` 负责把 id 转成更自然的展示标签
- `label_mapper` 负责把内部枚举转成用户可读文案

Builder 自身不应直接发请求，不应直接访问数据库，不应直接拼接大量业务查询。

---

## 3. 输入输出建议

### 3.1 输入

建议输入结构：

```ts
type StatusCardBuildInput = {
  snapshot: ConversationSnapshot | null
  workflow_state?: Record<string, unknown> | null
  capability?: CapabilityPolicy | null
}
```

其中：

- `snapshot.summary` 作为压缩主线
- `snapshot.conversation_memory` 作为结构化信息主来源
- `snapshot.active_context` 作为当前焦点对象主来源
- `workflow_state` 作为“正在做什么 / 等待什么”的主来源
- `capability` 作为能力标签来源

### 3.2 输出

建议输出结构继续使用：

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

---

## 4. 纯函数边界

### 4.1 推荐边界

`StatusCardBuilder` 推荐保持“输入确定，输出确定”的纯函数特征。

也就是说：

- 相同输入应产生相同输出
- 不在内部修改 `snapshot`
- 不在内部补写 `workflow_state`
- 不在内部更新 memory

### 4.2 允许的轻量依赖

MVP 可以允许 builder 依赖两个轻量协作者：

#### A. `StatusCardLabelMapper`

职责：

- `workflow_type + status + phase -> status_label`
- `workflow_type -> workflow_label`
- `status + required_slots -> waiting_label`
- `status -> suggested_actions`

#### B. `ContextLabelResolver`

职责：

- `course_id -> 课程标签`
- `doc_ids -> 文档来源标签`
- `artifact_id + artifact_type -> 产物标签`

这两个依赖都应是轻量、可替换、可测试的，不应把 builder 本身变成服务层编排器。

---

## 5. 字段优先级规则

## 5.1 `mode`

优先级：

1. `workflow_state.status in {"running", "awaiting_confirm"} -> "workflow"`
2. `snapshot.active_context.active_workflow_type` 存在且未结束 -> `"workflow"`
3. 其他情况 -> `"chat"`

说明：

- `mode` 不应从 `user_goals` 推断
- `mode` 只表达当前交互形态，不表达历史曾经进入过什么 workflow

## 5.2 `status_label`

优先级：

1. `StatusCardLabelMapper.map_status(workflow_type, status, phase, required_slots)`
2. 从 `active_context.active_workflow_type + active_workflow_status` 映射
3. 低信息回退为 `普通对话`

约束：

- 绝不直接把内部枚举值原样给前端展示
- `status_label` 是卡片最重要的一条文案，必须走统一映射

## 5.3 `workflow_label`

优先级：

1. `workflow_state.workflow_type`
2. `active_context.active_workflow_type`
3. 为空

示例映射：

- `report -> 报告`
- `lesson_plan -> 教案`
- `quiz -> 练习`
- `ppt_outline -> PPT 提纲`

## 5.4 `goal`

优先级建议调整为：

1. 当前 `workflow_type` 对应目标
2. `active_context` 中的当前焦点任务
3. `conversation_memory.user_goals` 中最高优先级项
4. `summary` 提取的主任务
5. 为空

说明：

- 不建议简单使用 `user_goals[0]`
- 当前 workflow 目标应覆盖旧目标

## 5.5 `topics`

优先级：

1. `conversation_memory.current_topics`
2. `summary` 提取
3. 最近消息窗口提取

排序建议：

1. 与当前 workflow 相关性高
2. 当前活跃度高
3. 置信度高

展示约束：

- 默认不超过 3 条
- 展开不超过 5 条

## 5.6 `issues`

优先级：

1. `conversation_memory.teaching_issues`
2. `conversation_memory.student_signals`
3. 与当前任务强相关的 `confirmed_facts`

排序建议：

1. 已确认教学问题
2. 学情信号
3. 候选问题

展示约束：

- 默认不超过 3 条
- 没有问题时不强行填充

## 5.7 `confirmed_facts`

优先级：

1. `conversation_memory.confirmed_facts`
2. 无兜底

排序建议：

1. 与当前 workflow 直接相关
2. 明确被确认过
3. 最近仍有效

展示约束：

- 展开态优先
- 建议显示前 2 到 3 条

## 5.8 `source_labels`

建议至少包含：

1. `当前会话`
2. `已选文档 N 份`，如果存在 doc 选择
3. `当前课程`，如果存在课程上下文
4. `当前产物`，如果存在 active artifact

约束：

- `当前会话` 是最低保底标签
- 不应为空数组

## 5.9 `waiting_label`

优先级：

1. `awaiting_confirm`
2. `required_slots` 未填满
3. `active_context.active_workflow_status`
4. 否则为空

规则：

- `waiting_label` 只在“确实需要用户动作”时显示
- `running` 状态下默认可为空

## 5.10 `suggested_actions`

优先级：

1. `label_mapper` 根据 workflow 状态生成
2. 前端静态兜底模板

约束：

- 最多 2 到 3 个
- 必须是用户可立即执行的动作

## 5.11 `summary_hint`

规则：

- 只在 `topics/goal/issues` 不足时启用
- 最多 1 句
- 建议 40 到 60 字以内
- 不可替代结构化区块本身

---

## 6. 低信息 / 空状态回退规则

冷启动或低状态会话是 MVP 必须覆盖的场景。

### 6.1 典型场景

- 新会话刚开始
- 用户只说了一句简短问候
- memory 尚未形成
- 没有 workflow、课程、文档、artifact

### 6.2 回退策略

建议回退卡片如下：

- `mode = "chat"`
- `status_label = "普通对话"`
- `topics = []`
- `goal = undefined`
- `issues = []`
- `source_labels = ["当前会话"]`
- `waiting_label = "继续提问，或告诉我你想生成什么"`
- `suggested_actions = ["继续提问", "生成报告"]`

### 6.3 空区块处理

建议：

- 没有 `topics` 时，隐藏主题区块或显示 `尚未形成明确主题`
- 没有 `goal` 时，不显示目标字段
- 没有 `issues` 时，不显示问题点字段
- 没有来源扩展时，保留 `当前会话`

原则：

**空状态要显得“轻”，而不是“坏了”。**

---

## 7. 文案映射层规则

MVP 不建议把状态文案分散在前端、builder 和 workflow runtime 中。

建议单独抽一层：

```ts
type StatusCardLabelMapper = {
  map_status(input): string
  map_workflow_label(workflow_type): string | undefined
  map_waiting_label(input): string | undefined
  map_suggested_actions(input): string[]
}
```

### 7.1 `status_label`

示例映射：

- `mode=chat` -> `普通对话`
- `report + running` -> `正在生成报告`
- `report + awaiting_confirm + outline` -> `等待你确认报告大纲`
- `lesson_plan + running` -> `正在整理教案`
- `quiz + running` -> `正在生成练习`
- `completed` -> `当前流程已完成`
- `interrupted` -> `当前流程已中断`

### 7.2 `waiting_label`

示例映射：

- `awaiting_confirm + outline` -> `等待你确认大纲`
- `required_slots` 缺 `audience` -> `等待你补充面向对象`
- `required_slots` 缺 `source_docs` -> `等待你选择资料`

### 7.3 `suggested_actions`

示例模板：

- `awaiting_confirm` -> `["确认并继续", "调整要求"]`
- `缺资料` -> `["选择资料", "跳过资料直接生成"]`
- `running` -> `["继续生成"]`
- `chat` -> `["继续提问", "生成报告"]`

---

## 8. 来源标签解析规则

状态卡片不应直接把一堆 id 原样暴露给用户。

建议由 `ContextLabelResolver` 负责把内部引用转成轻量标签。

```ts
type ContextLabelResolver = {
  resolve_course_label(course_id): string | undefined
  resolve_doc_source_label(doc_ids): string | undefined
  resolve_artifact_label(artifact_id, artifact_type): string | undefined
}
```

### 8.1 MVP 约束

MVP 阶段不要让 builder 自己去查多个 store。

建议策略：

1. 无法解析标题时，返回类型化标签
2. 标题解析作为可选增强，而不是 builder 的硬依赖

示例：

- `已选文档 2 份`
- `当前课程`
- `当前产物：报告草稿`

后续再增强为：

- `当前课程：高一物理`
- `当前产物：教学分析报告草稿`

---

## 9. 更新时机

这是 MVP 最需要写死的一条规则：

**状态卡片应在每次 `reply/report` 成功返回后重建，而不是单独维护自己的写回链路。**

也就是说：

- 会话状态继续按 summary / memory / active_context / workflow 原流程更新
- `StatusCardVM` 在响应组装阶段即时派生
- 页面刷新时通过只读接口重新派生

不推荐：

- 额外维护一套 `status_card_state`
- workflow 每个节点都去主动更新卡片
- 在数据库中把 `status_label` 之类 UI 文案长期保存

---

## 10. 实现建议

MVP 推荐落点：

1. 新增 `StatusCardBuilder`
2. 新增 `StatusCardLabelMapper`
3. 可选新增 `ContextLabelResolver`
4. 在 `response_builder_v2` 或服务层响应收口处注入 `status_card`

推荐职责边界：

- `ContextBuilder`：恢复 snapshot
- `StatusCardBuilder`：从 snapshot + workflow + capability 派生卡片
- `ResponseBuilderV2`：把卡片带回前端

---

## 11. 最终建议

如果要让状态卡片真正稳住，MVP 阶段最应坚持的不是字段多，而是规则稳：

- builder 只负责派生，不负责维护状态
- label 文案必须统一映射
- 空状态必须有友好回退
- source label 解析必须轻量，不要让 builder 变重
- 卡片应随响应即时重建，而不是单独持久化

一句话收口：

**`StatusCardBuilder` 应是一个轻量、可测试、可替换的状态派生层，而不是新的状态系统。**
