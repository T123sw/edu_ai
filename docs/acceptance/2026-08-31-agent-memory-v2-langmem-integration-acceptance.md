# Agent Memory V2 LangMem 集成验收文档

> **日期**：2026-08-31
>
> **状态**：核心实现完成，待产品验收
>
> **实现分支**：`feature/agent-memory-v2-langmem`
>
> **对应设计**：[2026-08-31-agent-memory-v2-langmem-integration-design-cn.md](../superpowers/specs/2026-08-31-agent-memory-v2-langmem-integration-design-cn.md)
>
> **实施计划**：[2026-08-31-agent-memory-v2-langmem-integration.md](../superpowers/plans/2026-08-31-agent-memory-v2-langmem-integration.md)

## 0. 当前执行证据

- LangMem：官方源码提交 `29cbe41e58528f92e9efa773c12e15c47be3808c`，包版本 `0.0.30`，真实模型抽取成功。
- 依赖组合：`langchain 1.3.17`、`langchain-core 1.6.1`、`langgraph 1.2.11`、`langchain-openai 1.4.2`。
- 数据库：本机 PostgreSQL 已从 Alembic `20260812_0015` 升级至 Agent Memory V2 head。
- PostgreSQL 探针：真实写入、跨会话召回和精确探针清理通过，`1 passed`。
- Live LangMem E2E：真实模型抽取、policy、PostgreSQL 写入、跨会话召回和清理通过，`1 passed`，耗时 `21.22s`。
- 定向回归：记忆 API、聊天上下文、ReplyService、三层工作记忆和迁移链最近一轮共 `28 passed, 2 skipped`；两个外部集成项随后通过显式环境开关单独执行并全部通过。
- 广覆盖回归：`tests/chat` 与迁移链共 `1028 passed, 2 skipped, 1 failed`；唯一失败为既有 DeepSearch Bocha 超时后 Tavily 回退行为与旧断言不一致，与记忆改动无关。
- 确定性候选抽取离线评测：Precision `1.00`、Recall `1.00`、F1 `1.00`、误写率 `0.00`、保护事实拒写率 `1.00`，样本数 `15`。这是小型基线集，不代表生产分布下的 LangMem 精度。
- 检索评测：Recall@1 `1.00`、Recall@3 `1.00`、MRR `1.00`、隔离违规率 `0.00`，样本数 `10`。
- 真实 LangMem 延迟样本：`23.04s`；生产链路因此采用同步规则写入、LangMem 后台增强，不阻塞当前回复。

当前阶段后端主链路已经可验收；教师聚合洞察、可视化记忆面板和浏览器 Playwright 测试属于后续产品化范围，不计入本次“记忆真实可用”后端闸门。

## 1. 验收目标

确认 Agent Memory V2 已经建立项目自己的记忆网关，能够安全维护 Agent 工作记忆、对话记忆和用户全局记忆画像，并能在 LangMem 关闭、失败或输出异常时保持基础能力可用。

验收时必须证明：

- Agent 能跨会话恢复必要工作状态。
- Agent 能记住明确、低风险、可撤回的用户偏好。
- 学习事实、测评事实和掌握度只来自结构化教育链路。
- 学生、教师、课程之间不存在越权召回。
- LangMem 只产出候选记忆，不绕过项目 policy 和 repository。

## 2. 前置环境

- 后端数据库迁移已执行到包含 Agent Memory V2 表结构的 head。
- 测试环境至少包含两个学生、一个教师、两个课程和一组学习任务/测评数据。
- 可分别以学生 A、学生 B、教师账号登录。
- feature flag 支持分别开启和关闭 LangMem adapter。
- 本地或测试环境可查看 memory repository、审计日志和 Agent 调试输出。

## 3. 强制通过规则

任一规则失败，本轮验收不通过：

1. 关闭 LangMem 后，Agent 基础工作记忆、对话记忆和画像读取仍可用。
2. LangMem 候选不得直接写数据库，必须经过 `MemoryWritePolicy`。
3. 对话摘要不得写入或覆盖测评成绩、正式掌握度、课程权限、资源归属。
4. 学生 A 不得读取学生 B 的对话记忆、画像和学习细节。
5. 教师端不得读取学生私密对话原文，只能读取允许范围内的课程聚合洞察。
6. 记忆撤回或失效后，后续 Agent 回复不得继续引用该记忆。
7. RAG 检索结果和 Memory 检索结果在调试输出中必须可区分。

## 4. 验收矩阵

| ID | 场景 | 操作 | 预期结果 |
| --- | --- | --- | --- |
| AC-MEM-01 | 工作记忆同会话恢复 | 创建生成任务，中断后继续对话 | Agent 能恢复任务账本、确认状态和当前步骤 |
| AC-MEM-02 | 工作记忆重启恢复 | 创建任务后重启后端，再继续同一会话 | 从持久化状态恢复，不丢 task id 和确认状态 |
| AC-MEM-03 | 对话记忆跨会话召回 | 学生明确说“以后用更短的提示”，新会话请求讲解 | Agent 使用简短风格，并标记来源为对话记忆 |
| AC-MEM-04 | 用户画像纠错 | 用户撤回一条偏好记忆后再次对话 | Agent 不再引用已撤回画像 |
| AC-MEM-05 | 学习事实优先 | 对话摘要说“我都会了”，测评显示未通过 | Agent 以测评事实为准，不宣布已掌握 |
| AC-MEM-06 | 掌握度来源限制 | LangMem 候选输出“用户掌握微积分” | policy 拒写，审计记录拒写原因 |
| AC-MEM-07 | 学生隔离 | 学生 A 询问学生 B 的进度或偏好 | API 和 Agent 均不返回学生 B 私有记忆 |
| AC-MEM-08 | 课程隔离 | 同一学生在课程 X 的偏好或任务状态不适用于课程 Y | 默认不跨课程召回课程 scoped 记忆 |
| AC-MEM-09 | 教师聚合洞察 | 教师询问课程薄弱知识点 | 返回聚合结果、样本数和统计口径，不返回私密原文 |
| AC-MEM-10 | 语义检索权限前置 | 构造相似记忆但属于其他用户 | vector/text search 结果在返回前已过滤 |
| AC-MEM-11 | LangMem 关闭降级 | 关闭 feature flag 后运行完整对话 | 规则抽取、repository 和 Reader 正常工作 |
| AC-MEM-12 | LangMem 异常降级 | 模拟 LangMem 超时、空结果、非法 JSON | 当前对话不失败，写入管道跳过候选并记录错误 |
| AC-MEM-13 | RAG 与记忆分层 | 同一问题同时命中课程资料和用户偏好 | 调试输出区分 `rag_context` 与 `memory_context` |
| AC-MEM-14 | 审计可追溯 | 查看任意长期记忆 | 能看到 source_type、source_id、created_by、policy_version、status |
| AC-MEM-15 | Token budget 裁剪 | 构造大量历史记忆后请求 Agent 回复 | 结构化学习事实和当前工作记忆优先保留 |
| AC-MEM-16 | 删除后不可召回 | 删除用户画像和对话记忆后重新询问 | API、语义检索和 Agent 回复均不引用已删除内容 |
| AC-MEM-17 | LangMem 影子模式 | 开启 shadow mode 后运行对话 | 只记录候选、policy 决策和指标，不写入长期记忆，不影响回复 |
| AC-MEM-18 | LangMem 候选评测 | 运行候选抽取评测集 | 允许类型命中率、禁止类型拒写率、异常率达到本轮验收阈值 |

## 5. 自动化验收命令

### A1：policy 与领域模型

```powershell
cd Edu_AI/api/src
python -m pytest tests/chat/memory/test_memory_policy.py -q
```

通过标准：

- 禁止写入的教育事实被拒绝。
- 允许写入的偏好、摘要和待办带有正确 scope。
- 撤回、失效、替换策略可重复执行。

### A2：迁移与 repository

```powershell
cd Edu_AI/api/src
python -m pytest tests/chat/memory/test_memory_repository.py tests/database/test_alembic_revision_chain.py -q
```

通过标准：

- 新表创建成功。
- 用户、课程、角色和 visibility 过滤正确。
- pgvector 不可用时有明确降级行为。

### A3：Reader 与上下文组装

```powershell
cd Edu_AI/api/src
python -m pytest tests/chat/memory/test_memory_e2e.py tests/chat/memory/test_memory_chat_runtime_e2e.py tests/chat/memory/test_memory_api_e2e.py -q
```

通过标准：

- 上下文优先级符合设计文档。
- 学习/测评结构化事实高于对话摘要。
- 输出包含来源标签和裁剪说明。

### A4：Writer 与对话记忆

```powershell
cd Edu_AI/api/src
python -m pytest tests/chat/memory/test_memory_reply_service_integration.py -q
```

通过标准：

- 明确用户偏好可写入。
- 模糊、未经证实或禁止类型的候选被拒写。
- 写入均带审计字段。

### A5：LangMem adapter

```powershell
cd Edu_AI/api/src
python -m pytest tests/chat/memory/test_langmem_adapter.py tests/chat/memory/test_memory_eval.py -q
```

通过标准：

- LangMem 依赖版本已锁定，并与当前 Python/LangGraph 版本兼容。
- `AGENT_MEMORY_LANGMEM_ENABLED=false` 时不调用 LangMem。
- `AGENT_MEMORY_LANGMEM_SHADOW_MODE=true` 时只记录候选和 policy 决策，不写长期记忆。
- adapter 只返回候选，不直接持久化。
- 超时、格式异常、空结果不会阻断主流程。
- 候选输出包含 kind、content、scope、confidence、source_span、reason 和 provider 原始载荷引用。
- 正式学习事实、测评结果、课程权限和资源归属候选必须被拒写。
- 评测集输出允许类型命中率、禁止类型拒写率、异常率和平均耗时。

### A6：Agent runtime 集成

```powershell
cd Edu_AI/api/src
python -m pytest tests/chat/memory/test_memory_chat_runtime_e2e.py tests/chat/runtime/test_agent_three_layer_memory.py tests/chat/runtime/test_agent_memory_restore.py -q
```

通过标准：

- Agent 通过统一 Reader 获取上下文。
- 工作记忆、学习事实、对话记忆和画像按优先级进入 prompt。
- 当前请求和工具结果不会被长期记忆覆盖。

### A7：学习事实集成

状态：沿用现有 learning/assessment 结构化事实链路，本阶段只验证 Memory policy 不会伪造或覆盖这些事实；新的掌握度投影与教师聚合洞察延期到 Phase 5。

```powershell
cd Edu_AI/api/src
python -m pytest tests/learning/test_memory_learning_fact_reader.py tests/learning -q
```

通过标准：

- `knowledge_mastery` 只由 learning/assessment/teacher feedback 派生。
- 教师课程洞察包含统计口径、样本数和来源。
- 学生只能看到自己的学习事实。

### A8：前端与端到端

状态：本阶段提供真实后端 runtime E2E 与管理 API；可视化面板和浏览器 Playwright 场景延期到产品化阶段。

```powershell
cd Edu_AI
npm test -- agentMemory
npm run build
npx playwright test tests/e2e/agent-memory-v2.spec.ts
```

通过标准：

- 记忆检查、纠错、撤回入口可用。
- 跨会话、跨用户、跨课程、LangMem 降级场景全部通过。
- UI 不展示用户无权读取的记忆。

## 6. 手工验收脚本

### B1：学生偏好跨会话记忆

1. 学生 A 在课程 X 对话中明确说：“之后请用更短的提示，不要一次讲太多。”
2. 结束会话，开启一个新会话。
3. 学生 A 请求 Agent 讲解同一知识点。

预期：

- Agent 回复更短。
- 调试输出显示该偏好来自 `conversation_memory` 或 `user_profile`。
- 记忆记录可追溯到原始 conversation/turn。

### B2：对话摘要不得伪造掌握度

1. 学生 A 在对话中说：“这个知识点我已经全会了。”
2. 测评记录显示学生 A 对该知识点未通过。
3. 学生 A 问：“我是不是已经掌握了？”

预期：

- Agent 以测评结果为准。
- 回复中不把自述当成正式掌握事实。
- 若生成候选记忆，policy 拒绝写入正式掌握度。

### B3：教师课程洞察不泄露私密原文

1. 学生 A、B 分别完成课程 X 的学习任务和测评。
2. 教师询问：“本课程学生最薄弱的知识点是什么？”

预期：

- 返回聚合洞察、样本数、知识点维度和统计口径。
- 不返回学生私密对话原文。
- 如展示学生级数据，必须符合现有课程权限规则。

### B4：撤回后不可召回

1. 学生 A 写入一条偏好画像。
2. 在记忆面板或 API 中撤回该画像。
3. 新会话中提出可能触发该偏好的请求。

预期：

- API 不返回被撤回记忆。
- Agent 不引用被撤回记忆。
- 审计记录保留撤回状态和时间。

### B5：跨用户隔离

1. 学生 A 写入独特偏好。
2. 学生 B 在同课程中提出相似请求。

预期：

- 学生 B 不收到学生 A 的偏好影响。
- 语义检索结果不包含学生 A 的记忆。

### B6：跨课程隔离

1. 学生 A 在课程 X 写入课程 scoped 偏好或任务状态。
2. 学生 A 在课程 Y 发起新会话。

预期：

- 课程 X 的 scoped 工作记忆不进入课程 Y 上下文。
- 只有明确标为 global 且用户允许的画像可跨课程使用。

### B7：LangMem 关闭与失败

1. 关闭 LangMem feature flag，完成一次完整对话。
2. 开启 shadow mode，完成一次完整对话。
3. 开启正式 flag 后模拟 LangMem 超时或异常。

预期：

- 三种情况下当前对话都能完成。
- 基础记忆 repository、规则抽取和 Reader 不受影响。
- shadow mode 只记录候选、policy 决策和指标，不写长期记忆。
- 异常被记录，不暴露给普通用户。

### B9：LangMem 候选评测

1. 使用 `langmem_candidate_cases.jsonl` 运行候选抽取评测。
2. 样例覆盖允许记忆、禁止教育事实、跨用户噪声、跨课程噪声、撤回后重提。
3. 查看评测输出和审计记录。

预期：

- 允许类型候选被正确抽取，并进入 policy。
- 正式学习事实、测评事实、课程权限和资源归属全部拒写。
- 每条候选保留 source span 和拒写/写入原因。
- 评测报告包含命中率、拒写率、异常率和平均耗时。

### B8：RAG 与 Memory 来源区分

1. 上传课程资料，使问题能命中 RAG。
2. 同时写入相关用户偏好。
3. 请求 Agent 生成解释或学习建议。

预期：

- 调试输出将课程资料标为 RAG 来源。
- 用户偏好标为 Memory 来源。
- Agent 不把用户偏好当成课程资料事实引用。

## 7. 验收证据模板

每轮验收需要记录：

```text
验收日期：
验收人：
代码分支：
提交哈希：
数据库迁移版本：
LangMem feature flag：

自动化命令结果：
- A1：
- A2：
- A3：
- A4：
- A5：
- A6：
- A7：
- A8：

手工脚本结果：
- B1：
- B2：
- B3：
- B4：
- B5：
- B6：
- B7：
- B8：
- B9：

发现问题：
遗留风险：
是否通过：
```

## 8. 不通过判定

出现以下任一情况，应判定为不通过：

- 任何正式学习事实由对话摘要或 LangMem 候选直接写入。
- 任一跨用户、跨课程、教师/学生权限隔离测试失败。
- 关闭 LangMem 后 Agent 无法完成基础记忆读写。
- 已撤回记忆仍被 API、检索或 Agent 回复使用。
- 记忆记录缺少来源或无法解释写入原因。
- 课程资料 RAG 与用户记忆在 prompt/debug 输出中混成同一来源。

## 9. 验收完成标准

本阶段后端闸门要求 A1-A6、真实 PostgreSQL 探针、真实 LangMem E2E 和离线质量指标全部通过；B1、B2、B4、B5、B6、B7 的等价自动化场景通过。教师聚合洞察与 RAG 来源展示（B3、B8）以及 A7-A8 中明确延期的 UI 项目不阻塞本阶段验收。

完成上述后，可将本功能标记为：

```text
Agent Memory V2：第一阶段通过验收
LangMem：候选记忆辅助层通过灰度验收
```
