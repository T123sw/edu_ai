# Agent Memory V2 LangMem 集成设计

日期：2026-08-31

状态：设计草案，已拆分实施计划和验收文档

适用范围：教师端 Agent、学生端 Agent、课程学习任务、测评反馈、对话记忆和用户全局画像

前置文档：

- `docs/superpowers/specs/2026-08-10-agent-memory-v2-design-cn.md`
- `docs/superpowers/specs/2026-08-10-teacher-student-interaction-loop-phase2-design-cn.md`
- `docs/superpowers/specs/2026-08-12-learning-task-assessment-loop-design-cn.md`
- `Edu_AI/docs/acceptance/2026-08-12-learning-task-assessment-loop-acceptance.md`

交付文档：

- `docs/superpowers/plans/2026-08-31-agent-memory-v2-langmem-integration.md`
- `docs/acceptance/2026-08-31-agent-memory-v2-langmem-integration-acceptance.md`

## 0. 决策摘要

本项目的 Agent 记忆不应直接购买或接入一个黑盒“记忆框架”后让它决定什么是真实事实。教育场景里的任务完成、测评成绩、知识点掌握、教师反馈和学生权限必须由项目自己的结构化事实源维护。

本设计采用：

1. **LangGraph 继续负责 Agent 工作流和会话内工作记忆**。
2. **PostgreSQL 作为教育事实、对话记忆和用户画像的权威存储**。
3. **pgvector 作为长期语义记忆检索能力**，与用户、课程、角色、可见范围过滤放在同一数据库边界内。
4. **LangMem 作为候选记忆抽取、记忆管理和召回策略的辅助工具层**，不直接成为事实源，不绕过权限和审计。
5. **Mem0、Graphiti、Letta、Cognee 暂不进入第一阶段主线**；只保留后续评估点。

第一阶段目标不是做一个“会记所有事”的 Agent，而是先实现一个可靠的记忆网关：

```text
Agent Runtime
  -> MemoryContextAssembler
      -> WorkingMemoryStore
      -> LearningFactReader
      -> ConversationMemoryStore
      -> UserProfileStore
      -> SemanticMemorySearch
```

所有 Agent 只依赖项目自己的接口。LangMem 可被放在接口后面，用来生成候选记忆、辅助合并和检索，但不能让 Agent 直接调用 LangMem 读取未经授权的数据。

## 1. 背景与问题

当前项目已经具备以下基础：

- ReAct Agent 的 `working_memory`、`task_ledger` 和 `conversation_summary`。
- `agent_runs` 对部分 Agent 状态进行持久化。
- `learning_events` 和 `learning_progress` 记录学习任务事件与完成口径。
- `assessment_*` 表记录正式测评、作答、成绩、复核和学生/教师投影。
- 课程知识库、个人知识库和 RAG 检索已有独立链路。

但这些能力尚未组成完整的 Agent 记忆系统：

- 工作记忆仍偏向当前会话和生成任务，无法稳定表达长期学习状态。
- 对话摘要存在，但没有生产级跨会话 MemoryReader/Writer。
- 用户画像还没有独立的结构化表和可撤回机制。
- 向量检索主要服务课程知识和个人文档，不服务用户长期记忆。
- Agent 上下文组装没有统一顺序，容易让历史生成任务覆盖当前学习事实。
- 教师和学生读取边界必须由数据层保证，不能依赖提示词要求模型自觉。

## 2. 三类记忆定义

### 2.1 Agent 工作记忆

工作记忆描述当前 Agent 正在处理什么，不描述用户长期事实。

包含：

- 当前课程、角色、会话、任务和活动页面。
- 当前意图、资源类型、生成计划、计划步骤和待确认大纲。
- 当前选中的课程资料、个人资料、Web/RAG 选项。
- 正在运行或最近完成的后台生成任务账本。
- 本轮工具结果、错误状态、重试点和确认策略。

要求：

- 以 `conversation_id + owner_user_id + course_id` 为作用域。
- 由 Agent runtime 和确定性路由更新。
- 模型摘要不得覆盖工作事实、任务 ID、材料 ID、确认状态或权限字段。
- 服务重启后可恢复。
- 同一用户不同课程、不同用户同一课程之间不得串线。

### 2.2 对话记忆

对话记忆描述跨会话可复用的交流信息。

包含：

- 对话片段摘要。
- 用户明确确认的偏好。
- 教师对教学风格、资源格式、讲解深度的要求。
- 学生在对话中表现出的典型误区、偏好解释方式、需要复习的点。
- 重要反馈和纠错记录。

要求：

- 原始消息和摘要分开存。
- 摘要必须记录来源 conversation、message 范围、抽取器版本和置信度。
- 对话记忆只能作为上下文候选，不得单独成为学习完成或掌握结论。
- 用户更正后，旧记忆必须可失效。

### 2.3 用户全局记忆画像

用户画像描述相对稳定、跨会话可复用的用户事实和偏好。

包含：

- 教师画像：常用教学对象、偏好课件风格、常用评分标准、常用语言、喜欢的课堂节奏。
- 学生画像：学习偏好、常见薄弱点、已验证掌握点、需要复习的知识点、偏好例子类型。
- 全局设置：语言、表达详略、是否优先给提示、是否偏好表格或步骤。

要求：

- 区分事实、偏好、推断和系统策略。
- 每条画像都必须有来源、置信度、可见范围、有效期和撤回状态。
- 教师默认不能读取学生私人对话画像；只能读取课程授权范围内的学习摘要、测评结果和班级聚合。
- 学生本人可以看到和更正自己的画像记忆。

## 3. 非目标

第一阶段不包含：

- 用 Graphiti 或其他图数据库替换现有 PostgreSQL 学习事实源。
- 用 Letta 替换现有 LangGraph/ReAct runtime。
- 将所有课程知识库文档迁入 LangMem 或 Mem0。
- 用 LLM 直接判断知识点掌握度。
- 跨课程能力迁移、因果干预分析和复杂遗忘算法。
- 教师读取学生私人 Agent 对话全文。
- 自动保存所有聊天内容为永久画像。

## 4. 开源框架评估

| 框架 | 适配度 | 集成难度 | 适合承担 | 不适合承担 | 结论 |
| --- | --- | --- | --- | --- | --- |
| LangGraph + LangMem | 高 | 低到中 | 工作流记忆、候选记忆抽取、语义召回、与现有 Agent 编排集成 | 教育事实源、权限源、成绩和掌握度 | 第一阶段推荐 |
| Mem0 | 中高 | 中 | 通用用户偏好、个人事实、快速画像试点 | 任务完成、测评成绩、课程权限和审计 | 备用评估 |
| Graphiti | 中 | 高 | 时间关系、事件演化、复杂知识图谱记忆 | 第一阶段核心事实和轻量落地 | 后期评估 |
| Letta | 中 | 高 | Memory Blocks 思想、长期 persona 组织方式 | 替换现有 runtime | 借鉴，不主接 |
| Cognee | 中 | 中高 | 文档知识图谱和外部知识组织 | 用户学习事实和课程权限 | 暂不优先 |

### 4.1 选择 LangMem 的原因

LangMem 与 LangGraph 同属 LangChain 生态，适合放在现有 Agent 图执行前后：

- 在对话完成后抽取候选记忆。
- 对候选记忆做合并、更新、删除建议。
- 在下一轮 Agent 运行前按 query 召回相关记忆。
- 保持 Python 技术栈，不引入新的 agent runtime。

但 LangMem 不应直接写入最终画像。所有候选记忆必须经过项目自己的 `MemoryWritePolicy` 校验，才能进入 PostgreSQL。

### 4.2 暂不选择 Mem0 的原因

Mem0 对快速实现用户记忆很有吸引力，但默认抽象偏通用 Agent 记忆。我们的核心问题不是“如何记住用户喜欢什么”，而是“如何不把未经授权和未经验证的学习事实写成真相”。因此 Mem0 可作为后续 `ConversationMemoryStore` 的替代实现评估，不作为第一阶段主线。

### 4.3 暂不选择 Graphiti 的原因

Graphiti 适合表达随时间变化的关系，例如“学生 A 在三次测评后逐渐修复了递归终止条件误区”。但第一阶段还没有稳定的掌握度模型和记忆评估集，过早引入图数据库会增加部署、迁移、权限和查询复杂度。

## 5. 总体架构

```text
Chat / Agent Request
  -> AuthenticatedActor
  -> ConversationStore
  -> AgentRunStore
  -> LearningContextReader
  -> MemoryContextAssembler
       1. load working memory
       2. load structured learning and assessment facts
       3. load course-authorized profile facts
       4. semantic search memory_items
       5. compact into token budget
  -> LangGraph ReAct Agent
  -> Tool Execution
  -> Final Response
  -> MemoryWritePipeline
       1. persist working memory snapshot
       2. summarize conversation episode
       3. ask LangMem for candidate memories
       4. validate, classify, scope and upsert
       5. enqueue embedding and derived insight jobs
```

## 6. 组件边界

| 组件 | 职责 | 不允许做 |
| --- | --- | --- |
| `WorkingMemoryStore` | 保存和读取当前会话工作状态 | 保存用户长期画像 |
| `LearningFactReader` | 读取学习任务、进度、测评和教师反馈投影 | 调用 LLM 推断掌握度 |
| `ConversationMemoryStore` | 保存对话片段摘要和候选情节记忆 | 覆盖原始对话和工作事实 |
| `UserProfileStore` | 保存用户确认或高置信画像事实 | 保存无来源的推断 |
| `SemanticMemorySearch` | 按权限过滤后做向量/关键词检索 | 绕过用户、课程和角色过滤 |
| `MemoryContextAssembler` | 按优先级组装 Agent 上下文 | 直接写记忆 |
| `MemoryWritePipeline` | 抽取、校验、写入和失效记忆 | 把 LLM 输出直接标记为事实 |
| `LangMemAdapter` | 封装 LangMem 抽取/管理/召回能力 | 直接访问生产表或泄露未授权数据 |

## 7. 接口设计

### 7.1 读取接口

```python
class AgentMemoryReader(Protocol):
    def read_for_agent(
        self,
        *,
        actor: AuthenticatedActor,
        conversation_id: str,
        course_id: str | None,
        task_id: str | None,
        query: str,
        token_budget: int,
    ) -> AgentMemoryContext: ...
```

`AgentMemoryContext` 必须分层返回：

```python
class AgentMemoryContext(BaseModel):
    working_memory: dict
    learning_facts: list[LearningFact]
    assessment_facts: list[AssessmentFact]
    profile_facts: list[ProfileFact]
    conversation_memories: list[MemoryItem]
    retrieval_notes: list[str]
    denied_scopes: list[str]
```

### 7.2 写入接口

```python
class AgentMemoryWriter(Protocol):
    def persist_turn(
        self,
        *,
        actor: AuthenticatedActor,
        conversation_id: str,
        course_id: str | None,
        user_message: str,
        assistant_message: str,
        agent_state: dict,
        tool_events: list[dict],
    ) -> MemoryWriteResult: ...
```

写入接口只允许：

- 更新工作记忆快照。
- 生成对话片段摘要。
- 生成候选记忆。
- 将通过策略的候选写入 `memory_items` 或 `user_profile_facts`。
- 提交异步 embedding job。

写入接口不得：

- 直接写学习任务完成。
- 直接写测评成绩。
- 直接写 `assessment_verified`。
- 直接给知识点掌握度满分。

### 7.3 画像接口

```python
class UserProfileMemoryStore(Protocol):
    def list_profile_facts(
        self,
        *,
        actor: AuthenticatedActor,
        subject_user_id: str,
        course_id: str | None,
        visibility: set[str],
    ) -> list[ProfileFact]: ...

    def upsert_profile_fact(
        self,
        *,
        actor: AuthenticatedActor,
        fact: ProfileFactDraft,
    ) -> ProfileFact: ...

    def invalidate_profile_fact(
        self,
        *,
        actor: AuthenticatedActor,
        fact_id: str,
        reason: str,
    ) -> ProfileFact: ...
```

## 8. 数据模型

### 8.1 `agent_working_memory`

用于替代或收敛现有 `agent_runs.state.agent_memory` 中的核心工作状态。

- `conversation_id`
- `owner_user_id`
- `course_id`
- `schema_version`
- `working_memory`
- `task_ledger`
- `conversation_summary`
- `updated_at`

唯一约束：`conversation_id + owner_user_id + course_id`。

第一阶段可继续复用 `app_state_records` 或 `agent_runs`，但必须明确权威来源和加载顺序。

### 8.2 `conversation_episodes`

保存可追溯的对话片段摘要。

- `episode_id`
- `conversation_id`
- `owner_user_id`
- `course_id`
- `scope_type`
- `scope_id`
- `message_start_position`
- `message_end_position`
- `summary`
- `salient_points`
- `extracted_at`
- `extractor`
- `extractor_version`
- `confidence`
- `visibility`
- `metadata`

### 8.3 `memory_items`

保存可召回的长期语义和情节记忆。

- `memory_id`
- `subject_user_id`
- `owner_user_id`
- `course_id`
- `task_id`
- `knowledge_point_id`
- `memory_type`: `preference | profile_fact | misconception | feedback | episode | correction | strategy_hint`
- `source_type`: `conversation | learning_event | assessment_attempt | assessment_review | teacher_feedback | user_confirmation`
- `source_id`
- `content`
- `structured_payload`
- `fact_kind`: `fact | preference | inference | summary`
- `confidence`
- `importance`
- `visibility`: `private | course_student | course_teacher_summary | course_aggregate | admin_audit`
- `status`: `active | superseded | invalidated | deleted`
- `valid_from`
- `valid_until`
- `created_at`
- `updated_at`
- `embedding`
- `embedding_model`

检索前必须先按 `subject_user_id/course_id/visibility/status` 做结构化过滤，再进行向量相似度排序。

### 8.4 `user_profile_facts`

保存稳定画像，便于直接 SQL 读取，不完全依赖向量召回。

- `profile_fact_id`
- `subject_user_id`
- `course_id`
- `profile_axis`: `teaching_style | learning_style | preference | weakness | strength | accommodation | language | resource_preference`
- `value`
- `evidence_count`
- `source_memory_ids`
- `confidence`
- `visibility`
- `status`
- `last_confirmed_at`
- `last_seen_at`
- `created_at`
- `updated_at`

### 8.5 `knowledge_mastery`

保存可解释的知识点掌握状态。

- `student_id`
- `course_id`
- `knowledge_point_id`
- `mastery_score`
- `confidence`
- `evidence_count`
- `last_practiced_at`
- `next_review_at`
- `misconception_codes`
- `calculation_version`
- `updated_from_event_id`
- `updated_at`

掌握度由学习事件、测评结果和教师反馈计算，不能由 LangMem 或对话摘要直接写入。

### 8.6 `course_learning_insights`

保存教师可读的课程聚合记忆。

- `insight_id`
- `course_id`
- `insight_type`
- `window_start`
- `window_end`
- `student_count`
- `payload`
- `source_event_count`
- `calculation_version`
- `created_at`

不得包含学生私人对话全文。若包含学生级可行动建议，必须引用授权学习事实或教师可见反馈。

## 9. 读取优先级

Agent 上下文组装必须遵循固定优先级：

1. 当前请求、认证身份、课程和角色。
2. 当前会话工作记忆和任务账本。
3. 学习任务、测评、进度和教师反馈结构化事实。
4. 用户画像中与当前角色可见的稳定事实。
5. 相关对话片段和语义记忆。
6. 课程知识库或个人知识库 RAG 结果。
7. Web 检索结果。

冲突处理：

- 结构化事实优先于对话摘要。
- 新证据优先于旧画像。
- 用户明确更正优先于模型抽取。
- 私人记忆不得因为语义相关而进入教师上下文。
- 当证据不足时，Agent 必须说明缺少依据。

## 10. 写入策略

### 10.1 工作记忆写入

每轮 Agent 完成后同步写入：

- `working_memory`
- `task_ledger`
- `conversation_summary`
- `logical_task_id`
- `current_plan`
- `pending_tasks`

写入必须是 owner/course scoped，且不会覆盖其他课程的同名 conversation。

### 10.2 对话记忆抽取

触发条件：

- 对话轮次达到阈值。
- 用户明确表达偏好或更正。
- 学生出现可复用误区或学习偏好。
- 教师给出课程或资源生成偏好。
- 测评/学习反馈后出现可复用解释。

抽取流程：

```text
messages + current facts
  -> LangMemAdapter.extract_candidates
  -> MemoryWritePolicy.classify
  -> permission and scope validation
  -> dedupe or supersede
  -> write memory_items/profile_facts
  -> enqueue embedding
```

### 10.3 禁止自动写入的内容

以下内容不得由对话抽取器直接写入为事实：

- 学生已经完成学习任务。
- 学生已经通过测评。
- 学生掌握某知识点。
- 教师已经批改某作答。
- 课程成员关系。
- 课程知识图谱结构。
- 标准答案、评分键和教师私有备注。

这些只能由 Learning、Assessment、Course 或 Knowledge 服务写入。

## 11. LangMem 集成方式

### 11.1 Adapter 封装

新增 `app/chat/memory/langmem_adapter.py`：

```python
class LangMemAdapter:
    def extract_candidates(
        self,
        *,
        messages: list[dict],
        existing_memories: list[MemoryItem],
        policy_hint: dict,
    ) -> list[MemoryCandidate]: ...

    def propose_updates(
        self,
        *,
        candidates: list[MemoryCandidate],
        existing_memories: list[MemoryItem],
    ) -> list[MemoryMutation]: ...
```

Adapter 不读取数据库，不做权限判断，只处理传入的已授权上下文。

### 11.2 第一阶段使用边界

第一阶段只允许 LangMem 参与：

- 教师偏好候选抽取。
- 学生学习偏好候选抽取。
- 对话片段摘要转候选记忆。
- 对候选记忆做合并建议。

第一阶段不允许 LangMem：

- 直接读取全部用户历史。
- 直接写数据库。
- 参与测评评分。
- 参与知识点掌握度计算。
- 读取未揭示答案、教师私有备注或学生私人全文。

### 11.3 可关闭策略

必须提供配置：

```text
AGENT_MEMORY_ENABLED=true
AGENT_MEMORY_LANGMEM_ENABLED=true
AGENT_MEMORY_LANGMEM_BACKGROUND=true
AGENT_MEMORY_EMBEDDING_ENABLED=false
```

当前验收配置默认开启 LangMem，但放入后台增强路径；同步路径先完成确定性规则写入，避免真实模型约 20 秒级的抽取耗时阻塞回复。向量 embedding 默认关闭，检索使用 PostgreSQL/SQLite 权限过滤后的文本排序；启用 embedding 后再增加余弦相似度。LangMem 不可用时，系统退回规则抽取和文本检索，Agent 主链路不得失败。

## 12. 权限与可见范围

| 记忆类型 | 学生本人 | 任课教师 | 其他学生 | 管理员 |
| --- | --- | --- | --- | --- |
| 工作记忆 | 本人会话可读 | 教师本人会话可读 | 不可读 | 审计可读 |
| 私人对话摘要 | 可读可撤回 | 默认不可读 | 不可读 | 审计可读 |
| 学习事件 | 本人可读 | 课程内可读必要字段 | 不可读 | 审计可读 |
| 测评结果 | 本人投影 | 聚合和授权明细 | 不可读 | 审计可读 |
| 用户偏好 | 本人可读可改 | 仅课程授权摘要 | 不可读 | 审计可读 |
| 班级洞察 | 不可读 | 任课教师可读 | 不可读 | 审计可读 |

教师端上下文默认只允许：

- 班级聚合。
- 任务/知识点统计。
- 学生级状态摘要。
- 教师已经有权限查看的复核反馈。

教师端上下文默认禁止：

- 学生私人 Agent 对话全文。
- 未揭示标准答案。
- 教师私有备注进入学生上下文。
- 一个学生的私人画像进入另一个学生上下文。

## 13. 与现有代码的集成点

### 13.1 ReAct 入口

在 `react_agent.py` 构建 prompt 前调用：

```text
MemoryContextAssembler.read_for_agent(...)
```

现有 `build_agent_memory_context` 保留，但只负责 L0 工作记忆。新的 assembler 负责拼接 L1-L4。

### 13.2 对话持久化

`conversation_store_adapter.py` 保存消息后，触发 `MemoryWritePipeline.persist_turn`。第一阶段可同步写工作记忆，异步写对话记忆和 embedding。

### 13.3 学习与测评

`LearningContextReader` 继续读取学习/测评投影。Memory V2 不替代它，而是在 assembler 中把它的结果作为最高优先级事实。

### 13.4 RAG

课程知识库和个人知识库 RAG 不并入 Memory V2。Memory V2 的 `memory_items` 是用户/对话/画像记忆；课程文档仍走现有知识库服务。

## 14. 测试与验收

### 14.1 单元测试

- 工作记忆保存、读取、重启恢复。
- 结构化事实优先级高于对话摘要。
- 用户更正使旧记忆失效。
- LangMem 不可用时规则 fallback 生效。
- 私人可见范围过滤在向量检索前执行。
- 同一用户不同课程记忆不串线。
- 不同用户同一课程记忆不串线。

### 14.2 服务测试

- 学生新开会话后能读取自己的任务进度和测评状态。
- 教师新开会话后能读取班级聚合，不读取学生私人全文。
- 画像写入需要来源和置信度。
- 对话抽取候选不能直接写 `assessment_verified`。
- 记忆召回结果包含 source、confidence、visibility 和 recency。

### 14.3 真实 E2E

至少覆盖：

1. 学生在一个会话中暴露学习偏好，换新会话后 Agent 用该偏好调整解释方式。
2. 学生通过测评后换新会话，Agent 依据测评事实回答已通过，而不是依据对话摘要。
3. 教师询问课程薄弱点，Agent 返回班级聚合和分母，不泄露学生私人对话。
4. 学生要求“忘记我喜欢图解说明”，后续会话不再召回该画像。
5. LangMem 关闭时，学习事实和工作记忆仍正常。

## 15. 分阶段实施建议

### Phase 0：权威来源收口

- 明确 `agent_runs` 与 LangGraph checkpoint 的合并顺序。
- 后端测试覆盖同进程多轮、服务重启、跨课程和跨用户隔离。
- 保留现有 `update_agent_memory`，但限制为 L0 工作记忆。

### Phase 1：记忆网关与数据表

- 新增 `conversation_episodes`、`memory_items`、`user_profile_facts`。
- 新增 `MemoryContextAssembler` 和 `MemoryWritePipeline`。
- 实现 SQL 读取、规则抽取和权限过滤。
- 暂不启用 LangMem 写入。

### Phase 2：LangMem 候选抽取试点

- 引入 LangMemAdapter。
- 仅对教师偏好、学生学习偏好、对话摘要候选启用。
- 所有写入经过 `MemoryWritePolicy`。
- 建立抽取准确率和误写率评估集。

### Phase 3：掌握度和班级洞察

- 新增 `knowledge_mastery` 和 `course_learning_insights`。
- 从测评、学习事件和教师反馈派生。
- Agent 只读取投影，不自行计算。

### Phase 4：高级记忆评估

- 评估 Graphiti 是否用于时间关系和误区演化。
- 评估 Mem0 是否可作为用户画像抽取后端。
- 评估跨课程能力迁移和遗忘策略。

## 16. 验收标准

本设计第一阶段完成时必须满足：

1. Agent 工作记忆在服务重启后恢复，且不被摘要覆盖。
2. 新会话能召回同一用户、同一课程下授权的对话记忆。
3. 用户画像至少支持创建、读取、更新、失效和来源追踪。
4. 教师和学生上下文均经过同一权限过滤器。
5. 学习任务、测评成绩和知识点状态来自结构化事实，不来自 LangMem。
6. 向量检索前执行结构化 scope 过滤。
7. LangMem 关闭或失败时主链路可用。
8. 记忆写入有审计记录和可撤回路径。
9. 真实 E2E 证明跨会话有用，且没有跨用户、跨课程泄露。

## 17. 功能需求编号

| 编号 | 要求 |
| --- | --- |
| MEM-FR-001 | Agent 必须维护独立的工作记忆、对话记忆和用户画像 |
| MEM-FR-002 | 工作记忆必须以会话、用户和课程为作用域持久化 |
| MEM-FR-003 | 对话记忆必须可跨会话召回，并保留来源消息范围 |
| MEM-FR-004 | 用户画像必须区分事实、偏好、推断和摘要 |
| MEM-FR-005 | 学生 Agent 必须能读取本人授权学习事实和画像 |
| MEM-FR-006 | 教师 Agent 必须能读取课程聚合与授权学生摘要 |
| MEM-FR-007 | 用户必须能更正或失效画像记忆 |
| MEM-FR-008 | LangMem 只能作为候选抽取和召回辅助层 |
| MEM-FR-009 | 记忆召回必须支持向量和关键词混合检索 |
| MEM-FR-010 | 记忆上下文必须按 token budget 压缩 |
| MEM-NFR-001 | 结构化学习/测评事实优先于对话记忆 |
| MEM-NFR-002 | 权限过滤必须发生在语义排序之前 |
| MEM-NFR-003 | LangMem 失败不得阻断 Agent 主链路 |
| MEM-NFR-004 | 记忆写入必须可审计、可撤回、可重算 |
| MEM-NFR-005 | 不得把 LLM 推断直接写成学习完成、测评通过或掌握事实 |

## 18. 参考

- LangGraph Persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph Long-term Memory: https://docs.langchain.com/oss/python/langchain/long-term-memory
- LangMem: https://langchain-ai.github.io/langmem/
- Mem0: https://github.com/mem0ai/mem0
- Graphiti: https://help.getzep.com/graphiti/getting-started/overview
- Letta Memory Blocks: https://docs.letta.com/v1-sdk/memory/memory-blocks/
- Cognee: https://github.com/topoteretes/cognee
