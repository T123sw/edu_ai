# 对话状态维护优化方案：每轮轻量更新 + 按需 LLM 微抽取 + 周期性压缩整理
**状态：** 已整理，可作为下一阶段对话状态优化的设计基线  
**日期：** 2026-04-05  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`

---

## 1. 文档目的

本文档用于回答以下问题：

1. 当前对话状态维护为什么仍然是系统质量的第一瓶颈
2. 下一阶段是否应该改成“每轮全量 LLM 抽取”
3. 更稳的方案应该是什么节奏
4. 规则抽取、LLM 微抽取、周期性压缩整理分别负责什么
5. 哪些字段适合交给 LLM，哪些字段不适合
6. 如何在提升质量的同时控制延迟、成本和状态污染风险

本文档不是 implementation plan，而是下一阶段对话状态维护的设计方案。

---

## 2. 总体判断

当前最重要的工作，不是继续优化单个资源生成 workflow，而是先把**对话状态维护层**做得更稳、更干净、更可复用。

原因很简单：

- `report / lesson plan / quiz / ppt` 都在消费这层状态
- 如果对话状态本身混入大量系统话术、低信息短语、重复主题和脏 evidence
- 后续所有 workflow 都只能在脏输入上做二次补救

因此，下一阶段的目标不是“让每轮对话都做一次全量 LLM 总结”，而是：

> **建立一套分层、分节奏的状态维护机制：每轮轻量更新，必要时做 LLM 微抽取，每 4 到 6 轮或关键节点做一次压缩整理。**

---

## 3. 为什么不建议“每轮全量 LLM 抽取”

“每轮都让大模型重做一次全量对话抽取”看上去最聪明，但当前阶段并不是最优解。

### 3.1 成本和延迟会明显上升

- 每轮都要把多轮上下文重新送入模型
- reply 主链路时延会上升
- 高并发时成本会快速堆积

### 3.2 状态更容易漂移

- 同一段对话在不同轮可能被模型用不同方式重述
- 主题、focus、问题点容易“越整理越变”
- 不利于做稳定的 merge 和回归测试

### 3.3 更容易把系统自己的话术重新写进 memory

当前系统已经暴露出一个典型问题：

- “请基于当前内容生成一份报告”
- “根据已确认的大纲开始生成报告”
- “请确认或指出要修改的地方”

这类系统/工作流话术一旦进入多轮上下文，如果每轮都做全量 LLM 抽取，模型会更容易把它们再次理解为主题、事实或 focus。

### 3.4 可观察性和可测性下降

- 规则抽取器虽然不够聪明，但容易测
- 全量 LLM 抽取会让字段边界更模糊
- 一旦输出波动，难以判断是模型问题、prompt 问题还是 merge 问题

因此，当前阶段不建议采用“每轮全量 LLM 抽取替代规则主干”的方案。

---

## 4. 推荐方案总览

推荐方案分成三层：

### 第一层：每轮轻量更新

每轮 reply 后都执行，规则主导，负责：

- 追加消息
- 维护系统状态
- 提取明确约束
- 提取显式目标
- 做基础去噪
- 写回最小状态

### 第二层：按需 LLM 微抽取

不是每轮强制执行，而是在满足条件时触发，负责：

- 主题收敛
- focus 提炼
- 问题簇聚类
- student signal 聚类
- evidence 规范化
- summary 候选增强

### 第三层：周期性压缩整理

每 4 到 6 轮，或关键节点触发一次，负责：

- 压缩 summary
- 合并 topic cluster
- 清理重复和低质量 memory
- 提升生成上下文可复用性
- 在进入 workflow 前提供更干净的状态底座

一句话概括：

> **每轮维护状态，但不是每轮都全量 LLM 重抽；LLM 主要负责增量增强和阶段性整理。**

---

## 5. 三层节奏的详细设计

## 5.1 第一层：每轮轻量更新

### 目标

保证每轮对话结束后，系统至少有一份稳定、低成本、可回放的最小结构化状态。

### 触发时机

- 每次 `reply.completed`
- 每次资源 workflow 成功返回后

### 推荐负责字段

规则层优先负责以下字段：

- `active_context`
- `workflow_state`
- `capability_policy`
- `selected_doc_ids`
- `current_course_id`
- 明确的 `constraints`
- 明确的 `user_goals`
- 基础 `current_topics` 候选
- 基础 `summary_text` 候选

### 这一层必须继续坚持的原则

- 快
- 稳
- 可测试
- 低成本
- 不直接依赖 LLM

### 这一层最重要的优化方向

不是“更聪明”，而是“更干净”：

- 过滤 report/system 话术
- 过滤确认句和追问句
- 过滤低信息主题
- 过滤格式化噪声
- 限制 assistant 元话术进入 `confirmed_facts`

---

## 5.2 第二层：按需 LLM 微抽取

### 目标

在规则抽取结果基础上，针对语义复杂、跨轮依赖强的字段，做一次小范围增强。

### 不建议每轮都跑，而是按条件触发

建议触发条件如下：

- 本轮出现明显新主题或新 focus
- 规则抽取器置信度低
- 当前 topics 明显分叉或冲突
- 本轮信息量显著大于平时
- 用户显式切换到资源生成意图
- 即将进入 `report / lesson plan / quiz / ppt`

### 建议优先交给 LLM 增强的字段

- `summary_text`
- `current_topics`
- `teaching_issues`
- `student_signals`
- `evidence_points`
- `report/lesson/quiz` 前置的 focus 提炼

### 不建议直接交给 LLM 的字段

以下字段不适合作为 LLM 的最终写入源：

- `active_context`
- `workflow_state`
- `capability_policy`
- `selected_doc_ids`
- `current_course_id`
- `confirmed_facts`

原因：

- 前五项是系统状态或显式输入，不应由模型猜测
- `confirmed_facts` 很容易被模型的推断、总结、润色污染

### 这一层输出形式

LLM 不直接写最终状态，只输出：

- 候选主题
- 候选 focus
- 候选 summary
- 候选 issue cluster
- 候选 evidence cluster

然后统一进入 merge / guard 层做裁决。

---

## 5.3 第三层：周期性压缩整理

### 目标

避免 memory 越聊越膨胀、越聊越脏，让系统定期把状态重新收口成一份更干净、更利于资源生成的上下文包。

### 建议触发节奏

推荐采用“轮次 + 长度 + 事件”混合触发：

- 每 4 到 6 轮触发一次
- 或最近消息累计长度超过阈值
- 或对话主题发生明显切换
- 或进入资源生成前
- 或 workflow 中发生关键状态变更

### 这一步主要做什么

- 合并重复 topic
- 提炼主主题和次主题
- 收敛当前主目标
- 聚合 issue cluster
- 聚合 signal cluster
- 清理低质量 evidence
- 重新生成一版更稳定的 `summary`

### 这一步不是做什么

不是重新解释整段对话，也不是每次都推翻历史状态重来。

它的作用更像：

> **阶段性收口与压缩整理。**

---

## 6. 推荐的字段分工

## 6.1 规则层长期负责

- `active_context`
- `workflow_state`
- `capability_policy`
- `selected_doc_ids`
- `current_course_id`
- 明确 `constraints`
- 明确 `user_goals`
- 基础 topic 候选

## 6.2 LLM 微抽取优先负责

- `summary_text`
- `current_topics` 的收敛与命名
- `teaching_issues` 的聚类
- `student_signals` 的聚类
- `evidence_points` 的规范化
- workflow 前的 `subject/focus` 提炼

## 6.3 merge / guard 层长期负责

- 去重
- 覆盖
- supersede
- 冲突降级
- 过期
- source tracking
- confidence 调整

这层必须独立存在，不能让 LLM 直接绕过。

---

## 7. 对当前系统最直接的优化优先级

如果按投入产出比排序，下一阶段最值得做的是：

### P0：清理对话 memory 里的 system/report 话术污染

重点过滤：

- `请基于当前内容生成一份报告`
- `根据已确认的大纲开始生成报告`
- `确认并继续`
- `请确认或指出要修改的地方`
- `已识别用户请求生成...`
- 其他 workflow 元话术

这一步会直接提升：

- 状态卡片质量
- report organizer 输入质量
- 历史会话恢复质量
- 后续所有资源 workflow 的承接质量

### P1：引入“按需 LLM 微抽取”

第一批建议只增强：

- `summary_text`
- `current_topics`
- `teaching_issues`
- `student_signals`
- `evidence_points`

### P2：做“每 4 到 6 轮 / 关键节点”的压缩整理

把 summary、topics、issues、signals 做阶段性收口。

### P3：资源生成前再做一次高质量整理

在 `report / lesson plan / quiz / ppt` 入口前，再做一次 workflow-specific 的上下文整理。

---

## 8. 为什么这个方案比“每轮全量 LLM”更适合当前阶段

### 更稳

规则底座保证系统状态不会漂得太厉害。

### 更快

绝大多数轮次仍走轻量维护，不会显著拖慢 reply。

### 更干净

先把规则去噪做好，再让 LLM 做整理，效果会比直接让模型面对脏上下文更好。

### 更容易回归测试

规则层、LLM 增强层、merge 层职责清楚，问题更容易定位。

### 更适合后续扩展到多 workflow

这套节奏不仅适合 report，也适合后续 lesson plan、quiz、ppt。

---

## 9. 对现有架构的落点建议

当前系统已经具备以下基础：

- `conversation_memory_extractor_v2`
- `llm_enhancement_provider`
- `llm_enhancement_router`
- `extraction_guard`
- `GenerationContext`
- `ReportContextOrganizer`

因此下一阶段不需要推倒重来，而是沿现有架构推进：

### 9.1 在 `conversation_memory_extractor_v2` 里继续做去噪

目标：

- 把系统话术和 report 话术排除出 memory
- 减少低信息主题、追问句、确认句进入状态

### 9.2 把 LLM enhancement 从“预留能力”推进到“按需增强”

目标：

- 默认仍不是每轮必跑
- 但在关键节点上真正接入

### 9.3 增加压缩整理入口

可以新增：

- `conversation_memory_compactor`
- 或 `conversation_state_refiner`

专门负责每 4 到 6 轮的整理任务。

---

## 10. 最终结论

下一阶段我推荐的方案，不是：

- 每轮都由大模型全量重抽一遍对话

而是：

> **每轮轻量更新 + 按需 LLM 微抽取 + 每 4 到 6 轮/关键节点做一次压缩整理。**

这套方案更适合当前系统，因为它同时兼顾了：

- 状态质量
- 成本
- 延迟
- 可测性
- 可观察性
- 后续多 workflow 复用

一句话总结：

> **每轮都维护状态，但不是每轮都全量 LLM 重抽；LLM 应该优先承担“整理、聚合、去脏、压缩”的角色，而不是替代整个规则主干。**
