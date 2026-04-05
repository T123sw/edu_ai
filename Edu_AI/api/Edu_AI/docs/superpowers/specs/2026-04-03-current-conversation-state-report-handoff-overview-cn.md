# 当前对话状态维护与报告承接实现总览
**状态：** 已整理，可作为当前阶段团队同步与后续规划参考  
**日期：** 2026-04-03  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat` 与 `D:\Edu_AI_1\Edu_AI\src\components\teacher`

---

## 1. 当前阶段结论

当前系统已经完成了从“消息驱动聊天系统”到“会话状态驱动、可被 workflow 稳定承接的生成系统”的第一阶段跃迁。

这次跃迁的核心不在于新增了几个字段，而在于以下 4 条链已经真正串起来：

1. 对话状态会持续沉淀，而不只是保存原始消息。
2. 普通对话已经能自动生产可复用状态，而不是必须进入 workflow 后才整理上下文。
3. report 已经从“读取最近消息”切换到“消费统一上下文”。
4. 状态卡片已经变成真实状态的可视化层，而不是展示层面的假 UI。

换句话说，当前系统已经具备以下基础能力：

- 状态不是临时算的，而是持续维护的。
- workflow 不再需要自己回扫历史考古。
- 前后端对“当前系统在做什么、理解了什么”已经有统一表达。
- evidence 已经开始具备来源可追溯性。

---

## 2. 当前已经完成的工作

### 2.1 对话状态维护链已经落地

每个对话不再只是保存原始消息，还会维护一份结构化状态。核心入口在：

- `app/chat/persistence/conversation_store_adapter.py`
- `app/chat/orchestrator/context_builder.py`
- `app/chat/domain/conversation_snapshot.py`

当前已经能够通过 `ContextBuilder -> ConversationSnapshot` 恢复以下内容：

- 原始消息历史
- `conversation_summary`
- `conversation_memory`
- `active_context`
- `workflow_state`
- `capability_policy`

### 2.2 普通对话已支持自动抽取并写回

当前普通 `reply` 成功返回后，会自动做轻量抽取与状态写回。当前实际运行的抽取器是：

- `app/chat/orchestrator/conversation_memory_extractor_v2.py`

这意味着用户在普通对话中逐步表达主题、目标、问题和约束时，系统已经能把这些信息沉淀成结构化状态，而不是只停留在消息列表里。

### 2.3 report-first 统一上下文承接已经打通

report 生成链已经改造成消费统一上下文，而不是仅依赖最近几条消息。主链路如下：

`ConversationSnapshot -> GenerationContext -> ReportAssembler -> ReportWorkflowRuntime`

核心文件：

- `app/chat/orchestrator/generation_context_builder.py`
- `app/chat/domain/generation_context.py`
- `app/chat/workflows/report/assembler.py`
- `app/chat/workflows/report/runtime.py`

### 2.4 状态卡片已经产品化

状态卡片已经接入前后端真实状态，而不是临时 UI 拼装。

后端：

- `app/chat/domain/status_card.py`
- `app/chat/orchestrator/status_card_builder.py`

前端：

- `src/components/teacher/StatusCardV2.tsx`
- `src/components/teacher/StatusCard.css`
- `src/components/teacher/ChatPanel.tsx`

当前卡片已经能展示：

- 当前状态
- 当前主题 / 目标 / 问题点
- 来源
- 约束
- 建议动作
- 展开详情中的 `confirmed_facts / student_signals / evidence / extra_constraints`

### 2.5 evidence 已具备基础来源可追溯性

当前 evidence 不再只是句子列表，而是开始具备 richer metadata：

- `content`
- `source_type`
- `source_message_ids`
- `confidence`

消息层也已经有了稳定 `message_id`，核心文件：

- `core/conversation_storage.py`

这为后续 evidence 回跳原始消息、做来源解释和可信度展示提供了基础。

---

## 3. 当前每个对话维护什么状态

当前每个对话维护两层状态：原始留痕层 + 结构化状态层。

### 3.1 原始留痕层

原始消息历史会保存：

- `role`
- `content`
- `timestamp`
- `message_id`
- 可选 `sources`

这一层的职责是：

- 保留完整事实历史
- 支撑审计、回放和调试
- 在必要时作为结构化状态的兜底来源

### 3.2 结构化状态层

当前对话 `state` 中已经维护的核心对象包括：

#### `conversation_summary`

- `summary_text`

职责：

- 提供当前对话的轻量压缩摘要
- 降低后续 workflow 对完整历史消息的依赖

#### `conversation_memory`

当前已经自动维护的字段包括：

- `current_topics`
- `user_goals`
- `confirmed_facts`
- `teaching_issues`
- `student_signals`
- `evidence_points`
- `constraints`

职责：

- 沉淀未来高概率复用的稳定信息
- 为状态卡片和资源生成提供统一输入

#### `active_context`

当前主要维护：

- `active_workflow_type`
- `active_workflow_status`
- `active_artifact_id`
- `active_artifact_type`
- `current_course_id`
- `pinned_doc_ids`

职责：

- 表达“当前工作对象”与“当前承接对象”
- 解决“根据上面的内容”“继续刚才那个结果”这类承接问题

#### 其他状态

- `workflow_state`
- `active_task`
- `active_artifact`
- `referenced_artifact_ids`
- `capability_policy`

其中 `capability_policy` 当前包含：

- `allow_rag`
- `allow_web`
- `selected_doc_ids`

---

## 4. 当前抽取逻辑是什么

当前抽取逻辑的定位是：

**启发式、规则化、可测试的 MVP 抽取器，而不是深语义 LLM 级总结器。**

### 4.1 触发时机

当前在以下时机触发抽取与写回：

- 每次 `reply` 成功返回后
- 每次 `report` 等 workflow 响应成功后

写回入口主要在：

- `app/chat/persistence/conversation_store_adapter.py`
- `app/chat/application/route_chat_service.py`

### 4.2 抽取字段与方法

#### `user_goals`

根据以下信号识别：

- 用户问题中的关键词
- action name
- workflow type

当前会识别成类似：

- `生成报告`
- `整理教案`
- `生成练习`
- `分析问题`
- `解释原因`
- `总结内容`
- `继续对话`

当前策略是：

- 新目标会排到前面
- 旧目标不会立刻丢弃

#### `current_topics`

当前逻辑是：

- 去掉动作前缀，如“请帮我”“分析一下”“总结一下”
- 对问题按标点切分
- 取前 1~2 个有意义短句
- 做去重与限长

#### `constraints`

当前会从问题中抽取：

- `audience`
- `tone`
- `length`
- `grade_level`
- `subject`
- `course_id`
- `extra_constraints`

例如：

- 面向教研组
- 正式一点
- 800 字左右
- 高一物理
- 按提纲形式输出
- 加入可执行建议

#### `teaching_issues`

当前会抽取带问题信号的句子，如：

- 参与度低
- 互动不足
- 吸引力不足
- 纪律问题
- 分心

#### `student_signals`

当前会抽取更偏“学生表现 / 课堂现象”的句子，如：

- 后排学生多次走神
- 前 10 分钟注意力不稳
- 举手响应较少

#### `confirmed_facts`

当前会从回答中抽相对确定的陈述句，并过滤：

- 建议句
- 假设句
- 提问句

#### `evidence_points`

当前会从回答中抽“更像观察证据”的句子，并生成 richer evidence 结构：

- `type`
- `content`
- `source_type`
- `source_message_ids`
- `confidence`

### 4.3 当前 evidence merge 行为

当前 evidence 已经具备基础 merge 能力：

- 同一 evidence 内容再次出现时，不会重复新增
- 会合并 `source_message_ids`
- 会按来源数量升级 `confidence`

当前简单规则：

- 1 个来源：`low`
- 2 个来源：`medium`
- 3 个及以上来源：`high`

### 4.4 当前 summary 生成方式

`conversation_summary.summary_text` 当前优先由：

- `topics + goal + issues`

拼接生成；如果信息不足，则退化为：

- 主题摘要
- 或回答前若干字

---

## 5. 当前如何承接到报告生成模块

### 5.1 `ContextBuilder` 恢复会话快照

`ContextBuilder` 会从存储中恢复 `ConversationSnapshot`，其中已经包含：

- `recent_messages`
- `summary`
- `conversation_memory`
- `active_context`
- `workflow_state`
- `capability`

这一步的意义是：

**把“消息 + 状态”统一成 workflow 可消费的快照对象。**

### 5.2 `GenerationContextBuilder` 组装统一生成上下文

`GenerationContextBuilder` 会把快照转成统一 `GenerationContext`，当前包含：

- `summary_text`
- `current_topics`
- `user_goals`
- `confirmed_facts`
- `constraints`
- `teaching_issues`
- `student_signals`
- `evidence_points`
- `selected_doc_ids`
- `referenced_artifact_ids`
- `current_course_id`
- `active_artifact_id`
- `active_artifact_type`
- `recent_relevant_messages`
- `source_scope`

### 5.3 `recent_relevant_messages` 已不再是简单最近窗口

这一层已经做过一轮升级：

- 过去：直接取最后 6 条消息
- 现在：优先按相关性选消息

当前相关性选择会优先考虑：

- `current_topics`
- `user_goals`
- `confirmed_facts`
- `teaching_issues`
- `student_signals`
- 当前请求文本

没有明显相关性时，才回退到最近消息窗口。

### 5.4 `ReportAssembler` 与 `ReportRuntime` 承接

`ReportAssembler` 会把 `GenerationContext` 转成 report workflow 需要的 `gathered_context`。

`ReportWorkflowRuntime` 再把这份 `gathered_context` 注入 report engine。

这意味着 report 现在吃到的已经不再只是：

- 最后一条用户消息
- 最近几条聊天记录

而是：

- 结构化摘要
- 结构化 memory
- relevance-selected messages
- 当前课程 / 文档 / artifact
- evidence
- constraints

也就是说，report 已经从“消息驱动临时理解”切换成了“状态驱动上下文承接”。

---

## 6. 状态卡片当前起到什么作用

状态卡片当前不是附属 UI，而是：

### 6.1 会话状态的可视化层

它展示当前真实状态，包括：

- 当前任务
- 当前理解
- 当前来源
- 当前约束
- 当前等待事项

### 6.2 workflow 承接的解释层

它能把本来隐形的系统状态显化出来，让用户知道：

- 系统现在理解了什么
- 系统依据了什么
- 系统接下来准备做什么

### 6.3 状态质量的外部质检器

状态卡片现在也是一块很有价值的观察窗。很多状态问题都可以通过卡片直接暴露，例如：

- goal 抽错
- issues 漂移
- source_labels 不合理
- waiting_label 与 workflow 状态不一致

所以卡片不只是展示层，也是在反向校验状态系统。

---

## 7. 当前阶段的架构判断

如果从系统成熟度看，当前已经完成的是：

**“会话结构化沉淀 + report-first 承接 + 状态可视化”阶段**

这个阶段意味着：

- 对话状态已经不再只是消息堆
- 普通对话已经开始生产可复用状态
- report 已经真正承接统一上下文
- 前端已经能稳定展示状态
- evidence 已具备基础来源可追溯性

这比典型的“AI 聊天 + 资源生成”系统已经更进一步，因为系统已经开始具备真正的“状态连续性”。

---

## 8. 下一阶段重点

当前最值得推进的 4 件事如下。

### 8.1 继续稳定 merge 规则

最关键的是以下字段的 merge 质量：

- `user_goals`
- `current_topics`
- `constraints`
- `teaching_issues`
- `student_signals`
- `confirmed_facts`

需要继续补稳的点：

- 去重
- 覆盖
- 升级
- 过期
- 冲突降级

### 8.2 完善状态写回事件流

需要彻底定死不同事件下的写回规则，例如：

- 普通 reply 完成
- reply 内切 report
- report 生成 outline
- report `awaiting_confirm`
- report `completed`
- workflow `interrupted`

### 8.3 推广到更多资源 workflow

当前 report 已经先打通，下一步应尽快让以下资源也走同一条链：

- lesson plan
- quiz
- ppt

目标是避免它们重新各自扫描聊天历史。

### 8.4 继续把状态卡片当作质检器

后续可以继续利用卡片暴露真实状态质量问题，并推动：

- 状态更稳
- evidence 更可信
- workflow 承接更自然

---

## 9. 一句话收口

当前系统已经完成了：

**“对话状态化”和“report 上下文化”的第一批关键基础设施建设。**

这意味着系统已经正式进入了：

**可以稳定扩展到更多资源 workflow 的阶段。**
