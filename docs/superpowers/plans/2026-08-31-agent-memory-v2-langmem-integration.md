# Agent Memory V2 LangMem 集成实施计划

> **日期**：2026-08-31
>
> **状态**：核心实施完成，待产品验收与规模化样本扩充
>
> **对应设计**：[2026-08-31-agent-memory-v2-langmem-integration-design-cn.md](../specs/2026-08-31-agent-memory-v2-langmem-integration-design-cn.md)
>
> **验收文档**：[2026-08-31-agent-memory-v2-langmem-integration-acceptance.md](../../acceptance/2026-08-31-agent-memory-v2-langmem-integration-acceptance.md)

## 1. 实施目标

实现一个可控、可审计、可逐步接入 LangMem 的 Agent Memory V2。系统需要同时支持三类记忆：

- **Agent 工作记忆**：当前会话、任务、工具结果、生成计划、任务账本和恢复点。
- **对话记忆**：跨会话的对话摘要、用户偏好、明确承诺、待办和可引用来源。
- **用户全局记忆画像**：用户长期偏好、角色属性、学习习惯和可撤回画像事实。

第一阶段的核心不是让 Agent “什么都记”，而是先建立项目自己的记忆网关、数据契约和权限边界。LangMem 只作为候选记忆抽取、合并和召回策略辅助层接入，不能直接成为事实权威源。

## 2. 架构原则

1. **结构化事实优先**：测评结果、学习进度、任务完成状态和教师反馈只来自项目内结构化表，不从对话摘要推断。
2. **统一读接口**：Agent runtime 只通过 `AgentMemoryReader.read_for_agent(...)` 获取记忆上下文。
3. **统一写接口**：对话结束、任务完成、测评完成和教师反馈只通过 `AgentMemoryWriter` 或领域服务写入记忆。
4. **权限前置过滤**：用户、课程、角色、可见范围和租户边界必须在数据库查询层或 repository 层过滤。
5. **LangMem 可替换**：LangMem 接在 `LangMemAdapter` 后，关闭、超时或失败时不得影响基础记忆能力。
6. **RAG 与记忆分层**：课程/个人资料检索仍由 RAG 管，用户长期记忆由 Memory Service 管，提示词中必须标注来源类型。
7. **可撤回与可审计**：所有长期记忆都必须记录来源、置信度、写入策略、更新时间和撤回状态。

## 3. 目标文件结构

### 3.1 后端新增

实施时按现有 `app.chat.memory` 模块边界收敛，实际文件为 `domain.py`、`repository.py`、`service.py`、`policy.py`、`rule_extractor.py`、`langmem_adapter.py`、`embedding.py`、`api.py`、`dependencies.py` 和 `eval.py`；下列名称是设计阶段的职责拆分，不再作为最终路径清单。

- `backend/src/app/chat/memory/__init__.py`
- `backend/src/app/chat/memory/models.py`
- `backend/src/app/chat/memory/policies.py`
- `backend/src/app/chat/memory/store.py`
- `backend/src/app/chat/memory/context_assembler.py`
- `backend/src/app/chat/memory/write_pipeline.py`
- `backend/src/app/chat/memory/langmem_adapter.py`
- `backend/src/app/persistence/postgres_agent_memory_repository.py`
- `backend/src/app/schemas/agent_memory.py`
- `backend/src/app/api/agent_memory.py`
- `backend/src/alembic/versions/20260831_0015_agent_memory_v2.py`

Alembic revision 编号需要在实施时以当前 head 为准；上面的文件名只表达期望语义。

### 3.2 后端修改

- `backend/src/app/database/models.py`
- `backend/src/app/database/__init__.py`
- `backend/src/app/bootstrap.py`
- `backend/src/app/chat/runtime/react_agent.py`
- `backend/src/app/chat/runtime/memory/manager.py`
- `backend/src/app/chat/persistence/agent_run_store.py`
- `backend/src/app/chat/persistence/conversation_store_adapter.py`
- `backend/src/app/learning/context_reader.py`
- `backend/src/app/chat/runtime/nodes/prompts.py`

### 3.3 前端与调试入口

- `frontend/src/stitch/memory/agentMemory.ts`
- `frontend/src/stitch/memory/AgentMemoryPanel.tsx`
- `frontend/src/stitch/api/agentMemory.ts`
- `frontend/src/stitch/types/agentMemory.ts`

第一版 UI 只做教师/学生可见的记忆检查、撤回和纠错入口，不做自动画像编辑器。

### 3.4 测试新增

- `backend/src/tests/chat/memory/test_memory_policies.py`
- `backend/src/tests/chat/memory/test_memory_repository.py`
- `backend/src/tests/chat/memory/test_context_assembler.py`
- `backend/src/tests/chat/memory/test_write_pipeline.py`
- `backend/src/tests/chat/memory/test_langmem_adapter.py`
- `backend/src/tests/chat/memory/test_langmem_candidate_eval.py`
- `backend/src/tests/chat/runtime/test_agent_memory_integration.py`
- `backend/src/tests/learning/test_memory_learning_fact_reader.py`
- `frontend/tests/e2e/agent-memory-v2.spec.ts`

### 3.5 LangMem 接入配置

- `backend/src/requirements*.txt` 或项目实际依赖文件：加入固定版本的 LangMem 依赖。
- `backend/src/app/core/config.py`：增加 `AGENT_MEMORY_LANGMEM_ENABLED`、`AGENT_MEMORY_LANGMEM_SHADOW_MODE`、`AGENT_MEMORY_LANGMEM_TIMEOUT_MS`。
- `backend/src/app/chat/memory/langmem_prompts.py`：集中维护候选记忆抽取 schema、允许类型和拒绝类型。
- `backend/src/tests/fixtures/memory/langmem_candidate_cases.jsonl`：沉淀候选抽取评测集。

## 4. 阶段计划

### Phase 0：权威源清理与红测

目标：先用失败测试固定边界，避免在 LangMem 接入时把事实来源搞混。

- [ ] 梳理现有 `working_memory`、`task_ledger`、`conversation_summary`、`agent_runs`、`learning_events`、`learning_progress` 和 `assessment_*` 的读写点。
- [ ] 增加红测：同一会话内工作记忆可恢复。
- [ ] 增加红测：服务重启后从 `agent_runs` 恢复任务账本和确认状态。
- [ ] 增加红测：跨课程不得召回另一个课程的工作记忆。
- [ ] 增加红测：跨用户不得召回另一个用户的对话记忆和画像。
- [ ] 增加红测：对话摘要不得覆盖测评成绩、知识点掌握和正式学习进度。
- [ ] 保留现有 `update_agent_memory` 作为 L0 工作记忆工具，先不改变 Agent 外部行为。

建议命令：

```powershell
cd backend/src
python -m pytest tests/chat/runtime tests/chat/persistence -q
```

### Phase 1：核心数据契约与 repository

目标：落地 Memory Service 的数据模型、迁移、repository 和写入策略。

- [x] 定义候选、策略决策、记忆记录、画像事实、上下文和评测报告等领域模型。
- [x] 增加 `conversation_episodes` 表，记录对话片段摘要、来源 turn、角色、课程和可见范围。
- [x] 增加 `agent_memory_items` 表，记录长期可检索记忆，支持来源、置信度、有效期、撤回状态和可选向量字段。
- [x] 增加 `user_profile_facts` 表，记录用户全局画像事实，支持纠错、撤回和审计。
- [ ] 预留 `knowledge_mastery` 和 `course_learning_insights` 表，但第一阶段只允许结构化学习链路写入。
- [x] 实现 SQLAlchemy/PostgreSQL repository；本地测试环境无 pgvector 时降级为文本检索。
- [x] 实现 `MemoryWritePolicy`，拦截禁止写入的事实类型。
- [x] 为迁移、repository、policy 写单元测试。

建议命令：

```powershell
cd backend/src
python -m pytest tests/chat/memory/test_memory_policy.py tests/chat/memory/test_memory_repository.py -q
```

### Phase 2：读路径与上下文组装

目标：让 Agent 通过统一 Reader 获取有优先级、有边界、有来源标签的记忆上下文。

- [x] 实现 `AgentMemoryReader.read_for_agent(...)`。
- [ ] 实现 `MemoryContextAssembler`，输出 `working_memory`、`learning_facts`、`conversation_memory`、`user_profile` 和 `retrieved_memory`。
- [ ] 建立上下文优先级：系统指令 > 当前请求 > 工具结果 > 学习/测评结构化事实 > 工作记忆 > 对话记忆 > 用户画像 > 语义召回。
- [ ] 对每类上下文添加来源标签，避免模型把摘要当成正式成绩。
- [x] 在 `react_agent.py` 与 Fast Chat runtime 入口接入 Reader。
- [x] 用户和课程隔离在 repository 查询前置执行；教师聚合洞察留在 Phase 5。
- [x] 加入 token budget 裁剪，并在 retrieval notes 中记录是否发生裁剪。

建议命令：

```powershell
cd backend/src
python -m pytest tests/chat/memory/test_context_assembler.py tests/chat/runtime/test_agent_memory_integration.py -q
```

### Phase 3：写路径与对话记忆

目标：把对话结束、任务完成和用户明确偏好沉淀为可审计记忆。

- [x] 实现 `AgentMemoryWriter.persist_turn(...)`，记录当前 turn 的候选摘要和来源。
- [x] 实现写入管道：规则/LangMem 候选统一进入 policy、审计和 repository。
- [x] 使用确定性规则抽取低风险记忆，例如用户明确偏好和确认过的称呼。
- [x] 对“学会了”“掌握了”“通过了”等事实执行保护事实拒写。
- [x] 实现撤回、失效和同画像轴替换逻辑，避免无限堆叠。
- [x] 增加来源、创建者、策略版本、provider 决策和延迟审计字段。
- [x] 在 `ReplyServiceV2` 完成会话持久化后接入写入管道。

建议命令：

```powershell
cd backend/src
python -m pytest tests/chat/memory/test_write_pipeline.py tests/chat/persistence -q
```

### Phase 4：LangMem 候选层试点

目标：把 LangMem 放在 adapter 后面，仅用于候选记忆抽取和召回辅助。该阶段是明确接入工作，不只是调研。

- [x] 确认 LangMem 版本、Python/LangGraph 兼容性并锁定官方提交 `29cbe41e58528f92e9efa773c12e15c47be3808c`（包版本 `0.0.30`）。
- [x] 增加 LangMem 配置项：启用开关、影子模式、后台模式、超时和最大候选数。
- [x] 增加 `LangMemAdapter`，接口只返回候选记忆，不直接写数据库。
- [ ] 定义 adapter 输入：当前 turn、最近消息窗口、当前工作记忆、允许写入 scope、用户/课程/角色上下文。
- [ ] 定义 adapter 输出：`MemoryCandidate[]`，字段包含 kind、content、scope、confidence、source_span、reason、expires_at、raw_provider_payload。
- [x] 通过 feature flag 控制；当前验收默认后台开启，影子模式只记录候选与 policy 结果，不影响 Agent 回复。
- [x] 将 LangMem 候选输出统一送入 `MemoryWritePolicy`。
- [x] 限制第一批候选类型：称呼偏好、沟通风格偏好、明确表达的长期学习习惯、对话摘要。
- [x] 明确禁止 LangMem 生成正式学习事实、测评结果、课程权限和资源归属。
- [x] 实现候选去重和同画像轴替换/版本化。
- [ ] 将 LangMem 召回仅作为 `SemanticMemorySearch` 的 rerank 或候选补充，不替代 PostgreSQL 权限过滤。
- [x] 增加关闭、外部依赖失败、格式异常和空结果测试；provider timeout 由模型客户端配置覆盖。
- [x] 建立小型离线评测集，统计精确率、召回率、误写率和保护事实拒写率。
- [x] 记录首轮真实 LangMem 抽取/E2E 延迟，并据此将 LangMem 放入后台路径。

建议命令：

```powershell
cd backend/src
python -m pytest tests/chat/memory/test_langmem_adapter.py tests/chat/memory/test_langmem_candidate_eval.py tests/chat/memory/test_write_pipeline.py -q
```

LangMem 接入必须满足的局部完成条件：

- 依赖可被一键安装，且锁定版本。
- `AGENT_MEMORY_LANGMEM_ENABLED=false` 时测试覆盖“不调用 LangMem”。
- `AGENT_MEMORY_LANGMEM_SHADOW_MODE=true` 时只记录候选和 policy 决策，不写长期记忆。
- LangMem 输出异常不会影响 `AgentMemoryReader`、`AgentMemoryWriter` 和当前对话。
- 所有 LangMem 候选都能在审计日志中看到原始来源、policy 决策和最终写入/拒写结果。

### Phase 5：学习事实、掌握度与课程洞察

目标：把学习/测评链路的结构化事实接入 Memory Reader，而不是让 Agent 从对话里猜。

- [ ] 实现 `LearningFactReader`，读取学习任务、测评、复核和知识点完成情况。
- [ ] 建立 `knowledge_mastery` 派生写入流程，来源仅限 assessment、learning task 和教师显式反馈。
- [ ] 建立 `course_learning_insights` 聚合流程，教师端读取聚合洞察时必须包含样本数和统计口径。
- [ ] 学生端可读取自己的掌握状态；教师端默认不能读取学生私密对话原文。
- [ ] 增加任务完成、测评提交、教师复核后的 memory invalidation 机制。

建议命令：

```powershell
cd backend/src
python -m pytest tests/learning tests/chat/memory -q
```

### Phase 6：API、UI 与端到端验收

目标：提供可检查、可撤回、可回归的产品入口。

- [x] 增加记忆检查 API：按当前用户和当前课程返回可见记忆。
- [x] 增加用户画像纠错 API：用户可撤回或修正自己的画像事实。
- [ ] 增加教师端课程聚合洞察 API：只返回聚合指标和来源口径。
- [ ] 增加 `AgentMemoryPanel`，用于本地调试和产品验收。
- [ ] 增加 Playwright E2E：跨会话召回、跨用户隔离、撤回后不再召回、LangMem 关闭降级。
- [x] 更新文档 README 索引，标记 Agent Memory V2 的规格、计划和验收文档。

建议命令：

```powershell
cd Edu_AI
npm test -- agentMemory
npm run build
npx playwright test tests/e2e/agent-memory-v2.spec.ts
```

## 5. 验收闸门

每个阶段完成后必须满足：

- 单元测试覆盖新增 policy、repository、assembler、writer 和 adapter。
- 所有记忆读写都有用户、课程、角色和可见范围过滤。
- 对话摘要和 LangMem 候选不得写入正式学习事实。
- 关闭 LangMem 后，工作记忆、对话记忆和用户画像基础能力仍可用。
- 记忆撤回后，后续 Agent 回复不得继续引用该记忆。
- 教师端课程洞察不得泄露学生私密对话原文。
- RAG 引用和 Memory 引用在提示词和调试输出中可区分。

## 6. 回滚策略

- 所有新读写路径必须受 feature flag 控制。
- 如 Memory Reader 出错，Agent 降级为当前请求、工具结果和现有工作记忆。
- 如 Memory Writer 出错，不阻断当前对话完成，但需要记录错误并可重放写入。
- 如 LangMem 出错，跳过候选抽取，不影响 repository 和规则抽取。
- 数据迁移上线前必须提供 downgrade 或等价回滚说明。

## 7. 交付顺序

推荐按以下顺序合并，避免一次性大改：

1. 红测与权威源清理。
2. 数据模型、迁移和 repository。
3. Reader 与 context assembler。
4. Writer 与确定性对话记忆。
5. LangMem adapter 接入、影子模式和灰度。
6. 学习事实、掌握度和课程洞察。
7. API、UI、E2E 和 README 索引。

## 8. 暂不做

- 不把 LangMem 作为唯一长期记忆数据库。
- 不让 Agent 直接写入测评成绩、掌握度或学习完成状态。
- 不在第一阶段引入 Graphiti 知识图谱记忆。
- 不在第一阶段替换现有课程知识库/RAG。
- 不做无边界的全局跨课程记忆召回。
- 不把用户画像自动暴露给教师端。
