# 稳定型教学 Agent 能力优化执行计划

> 日期：2026-08-09
> 状态：Task 11—17 已实施并完成自动化、真实服务、双 Provider、长对话与浏览器验收
> 审计基线：`main@8eb20f7`（工作区干净）
> 对应 SPEC：`docs/superpowers/specs/2026-08-09-stable-teaching-agent-optimization-design.md`
> 验收文档：`docs/acceptance/2026-08-09-stable-teaching-agent-optimization-acceptance.md`

## 0. 审计结论与实施边界

### 0.1 已完成的审计工作

- [x] 阅读交接、能力基线、调研、SPEC、原执行计划和验收文档；
- [x] 审计 Planner、Executor、Tools、Reflect、LangGraph state/checkpointer、工具 handler、GenerationCommand 和 durable task store；
- [x] 审计教师普通问答与 Agent 两条提示词路径；
- [x] 审计报告、教案、习题、博客、闪卡、思维导图、小游戏和 AI 课堂的证据传递入口；
- [x] 运行 `api/src/tests/chat/runtime`：151 passed；
- [x] 运行工具注册、模型注册、GenerationCommand 和 durable task store 目标回归：34 passed；
- [x] 已运行后端全量、前端单元与构建、真实 Provider/RAG/Web/Job/材料 E2E、五次重复、双 Provider 与教师端浏览器全流程。

### 0.2 现状分级

| 分级 | 项目 |
|---|---|
| 已实现/复用 | UI 来源规范化、强制 RAG/Web、检索失败闭门、大纲确认、八类非 PPT 工具入口、durable Job 基础设施、报告 grounding、模型 fallback、基础 trace |
| 部分实现/需收敛 | 自由计划后置修正、guided/strict 工具过滤、Reflect 重试、图片链路、研究证据传递、任务进度记忆 |
| 未实现 | `TeachingTaskContract`、固定模板编译器、材料包、控制意图、确定性 Agent 幂等、Agent run 持久化、统一 `ResearchBundle`、结构化 `VerificationReport`、教师 PersonaPolicy、Agent Eval Dataset |

### 0.3 必须先关闭的 P0 缺口

1. strict 空 allowlist 当前会暴露全部工具；
2. Executor 全程使用 `tool_choice="auto"`；
3. Reflect 会把 `ok=false` 的工具结果当作 `pass`；
4. Agent 生成 handler 使用随机 UUID 幂等键；
5. LangGraph 仅使用进程级 `MemorySaver`；
6. Agent 只验证 Job 已接受，不验证最终 `result_ref` 与材料可读性；
7. 普通问答快速路径仍是面向学习者的启发式教师语气。

实施期间保留现有 LangGraph、工具 handler 和资源生成服务。除非目标测试证明必须调整，不重写已有生成器，不扩大到 PPT 或学生端产品。

### 0.4 本轮执行结果（2026-08-09）

- [x] Task 1：落地任务契约、教师/学生角色策略和教师 Fast/Agent 统一提示词。
- [x] Task 2：落地固定模板编译器，覆盖 QA、单资源、材料包、确认、状态、取消与修改大纲。
- [x] Task 3：关闭空 allowlist 回退、按步骤设置 tool choice，并阻止失败工具推进。
- [x] Task 4：落地 Agent SQLite run state、逻辑任务幂等键和课堂生成去重。
- [x] Task 5：落地共享 ResearchBundle、结构化 VerificationReport、任务状态/取消工具及材料引用读回判定；全部八类非 PPT 资源实际消费研究上下文并记录 bundle 证据。
- [x] Task 6（本地部分）：新增 12 轮长对话真实服务冒烟脚本；目标回归 257 passed、最终后端全量 1314 passed/2 skipped、前端 223 passed、生产构建、编译与 diff 检查通过。
- [x] Task 6（核心 L3）：真实教师凭据下的 RAG/Web、报告 Worker、Job/材料读回、结构化审计与 12 轮长对话通过。
- [x] Task 6（发布扩展）：执行浏览器 E2E、双 Provider、五次重复和完整故障注入。

真实 E2E 只从 `EDU_AI_SMOKE_TOKEN` 环境变量读取凭据，绝不记录或输出令牌。

## 1. 执行原则

1. 保留现有 LangGraph 和资源生成服务，不做框架迁移。
2. 测试先行：每个任务先写失败测试，再实现，再跑目标回归。
3. 先收紧契约和计划，再改语气；避免提示词优化掩盖编排缺陷。
4. 规则可以判断的内容不用 LLM 判断。
5. 每个不可逆生成调用都必须先完成幂等防护。
6. 不因单个真实供应商失败伪造通过；替身测试和真实冒烟分别记录。
7. PPT 和学生端产品不进入本计划；只提供学生角色策略扩展点。
8. 每个阶段完成后更新验收文档，不等到最后补写测试证据。

## 2. 建议执行顺序

```text
现状冻结
→ 任务/角色契约
→ 计划模板与编译器
→ 有界执行和工具白名单
→ 幂等与持久状态
→ 统一 ResearchBundle
→ 结构化自检与错误恢复
→ 教师语气和学生策略接口
→ 评测数据集
→ 真实 E2E 与重复稳定性实验
→ 最终验收
```

## Task 0：冻结基线与测试夹具

**目标：** 保留当前 1280 项后端回归和真实 Agent 能力结果，建立优化前可比较基线。

**文件：**

- Review: `docs/acceptance/2026-08-09-agent-capability-status.md`
- Modify: `api/src/scripts/smoke_teacher_agent_tools.py`
- Modify: `api/src/scripts/smoke_teacher_agent_generation.py`
- Create: `api/src/tests/chat/runtime/fixtures/agent_baseline_cases.yaml`
- Modify: `docs/acceptance/2026-08-09-stable-teaching-agent-optimization-acceptance.md`

**步骤：**

- [x] 完成代码审计并记录当前实现分级。
- [x] 运行现有 runtime 与工具/任务基础设施目标回归，分别为 151 passed、34 passed。
- [x] 将现有通过用例转换为稳定的 case ID，不改变运行逻辑。
- [x] 记录当前意图、工具顺序、模型轮次、耗时、Job 和材料终态。
- [x] 为现有已知缺口建立预期失败用例：教师语气、材料包、重复提交、跨重启恢复、统一研究包。
- [x] 新增预期失败用例：空 allowlist、`tool_choice`、失败 Observation 推进步骤、accepted 冒充 completed。
- [x] 运行当前目标测试集，确认新增用例按预期 RED，旧用例保持 GREEN。

**完成证据：** 基线数据集可重复执行；旧能力无倒退；新增目标存在明确失败原因。

## Task 1：建立任务契约与角色策略

**目标：** 把自然语言理解结果从任意字典收紧为版本化结构，并分离教师/学生沟通策略。

**文件：**

- Create: `api/src/app/chat/domain/teaching_task_contract.py`
- Create: `api/src/app/chat/domain/persona_policy.py`
- Create: `api/src/app/chat/runtime/planning/task_contract_extractor.py`
- Modify: `api/src/app/chat/domain/capability_policy.py`
- Modify: `api/src/app/chat/application/request_normalizer.py`
- Modify: `api/src/app/chat/orchestrator/context_builder.py`
- Create: `api/src/tests/chat/runtime/test_teaching_task_contract.py`
- Create: `api/src/tests/chat/runtime/test_persona_policy.py`

**步骤：**

- [x] 写测试覆盖七类意图、九类资源枚举、三种知识来源和三种 Web/图片策略。
- [x] 明确 PPT 仅保留枚举兼容，不进入本轮生成模板和成功率分母。
- [x] 写测试证明 UI capability 覆盖模型输出，明确资源关键词覆盖概率分类。
- [x] 实现 `TeachingTaskContract`、版本号、规范化和默认值。
- [x] 实现教师与学生 `PersonaPolicy`；当前请求固定解析为教师角色。
- [x] 将同一教师策略同时注入普通问答 fast path 与 Agent path，先写测试证明旧 fast prompt 会触发学生式反问。
- [x] 对非法字段、未知资源和模型虚构的 selected document ID fail closed。
- [x] 运行契约、请求规范化和上下文相关回归。

**完成证据：** 相同输入得到稳定任务契约；模型不能修改 UI 权威来源和权限。

## Task 2：用计划模板和编译器替代自由计划

**目标：** 模型只提取任务，代码编译合法计划；彻底消除“先回答再检索”等顺序问题。

**文件：**

- Create: `api/src/app/chat/runtime/planning/templates.py`
- Create: `api/src/app/chat/runtime/planning/compiler.py`
- Replace/Modify: `api/src/app/chat/runtime/planning/schema.py`
- Modify: `api/src/app/chat/runtime/nodes/planner.py`
- Modify: `api/src/app/chat/runtime/planning/prompts.py`
- Modify: `api/src/app/chat/runtime/graph/state.py`
- Create: `api/src/tests/chat/runtime/test_plan_compiler.py`
- Create: `api/src/tests/chat/runtime/test_plan_templates.py`
- Modify: `api/src/tests/chat/runtime/test_mandatory_retrieval_plan.py`

**步骤：**

- [x] 为 QA、单资源、材料包、修改、确认、状态和取消写计划快照测试。
- [x] 写对抗测试：模型漏 RAG、把 Web 放最后、生成提前、重复生成、非法 action、循环依赖。
- [x] 写空 allowlist 测试：等待确认、自检、汇报阶段必须暴露 0 个工具。
- [x] 实现枚举化 `CompiledPlan` 与 dependency validator。
- [x] 实现默认材料包：教案 + 练习题 + 思维导图；高成本 AI 课堂必须显式请求。
- [x] 材料包只生成一次合并确认卡；教案/报告结构和 AI 课堂成本提示并入同一次确认。
- [x] 将当前多个后置 `_ensure_*` 修正逻辑收敛到一个编译器，不保留两套权威计划。
- [x] 计划不合法时使用确定性模板回退，不直接放行自由 Executor。
- [x] 运行规划和 ReAct 现有回归。

**完成证据：** 任何 planner 输出都不能形成违反来源、确认和生成顺序的可执行计划。

## Task 3：阶段化工具白名单与有界 ReAct

**目标：** ReAct 只在当前计划阶段内行动，具备明确预算和终止条件。

**文件：**

- Modify: `api/src/app/chat/runtime/nodes/executor.py`
- Modify: `api/src/app/chat/runtime/nodes/tools.py`
- Modify: `api/src/app/chat/runtime/nodes/reflect.py`
- Modify: `api/src/app/chat/runtime/graph/routes.py`
- Modify: `api/src/app/chat/runtime/graph/builder.py`
- Modify: `api/src/app/chat/runtime/agent_tools/schemas.py`
- Modify: `api/src/app/chat/runtime/agent_tools/executor.py`
- Create: `api/src/app/chat/runtime/execution/budgets.py`
- Create: `api/src/app/chat/runtime/execution/termination.py`
- Create: `api/src/tests/chat/runtime/test_stage_tool_allowlist.py`
- Create: `api/src/tests/chat/runtime/test_agent_budgets_and_termination.py`

**步骤：**

- [x] 写测试证明每一阶段只暴露合法工具，空白 allowlist 不得回退为全部工具。
- [x] 写最大轮次、最大工具调用、一次重试、一次重规划和超时测试。
- [x] 将 `tool_choice` 按计划设为禁止、自动、指定或必需，而不是全程 `auto`。
- [x] 在工具执行前再次校验阶段和 allowlist；越权统一返回 `contract_violation`。
- [x] 将 Observation 规范化为短结构，不把整份工具输出重复塞入消息历史。
- [x] `ok=false`、非法 Observation 和生成提交异常不得推进步骤；先修正现有 Reflect 的失败默认通过行为。
- [x] 达到生成提交、等待确认、明确失败或预算上限时立即终止。
- [x] 运行全部 runtime 测试，检查无死循环。

**完成证据：** 禁止工具调用率为 0；所有异常路径都有确定终态。

## Task 4：生成工具幂等、任务关联与跨重启状态

**目标：** 前台超时、重复确认、模型重试或服务重启都不能重复创建资源。

**文件：**

- Create: `api/src/app/chat/runtime/execution/idempotency.py`
- Create: `api/src/app/chat/persistence/agent_run_store.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/report.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/lesson_plan.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/quiz.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/resource.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/classroom.py`
- Modify: `api/src/app/chat/runtime/graph/builder.py`
- Modify: `api/src/app/services/job_store.py`
- Create: `api/src/tests/chat/runtime/test_generation_idempotency.py`
- Create: `api/src/tests/chat/runtime/test_agent_run_persistence.py`

**实现决策：** 复用现有 durable task store 的 SQLite 基础设施，新增独立 Agent run/step/reference 表；`MemorySaver` 只作运行时缓存，不再是事实来源。不要把高频步骤状态写入整文件 JSON 对话存储。

**步骤：**

- [x] 写重复确认、客户端重连、网关重试、双 API 实例和提交后超时测试。
- [x] 实现稳定 `logical_task_id` 和基于 owner/course/conversation/resource/contract hash 的确定性幂等键；重规划不得改变逻辑任务 ID。
- [x] 移除 Agent handler 的随机 UUID 幂等键；AI 课堂纳入同一协议。
- [x] 持久化任务契约、计划步骤、确认点、研究包引用、Job 引用和验证结果。
- [x] 服务重启后从持久层恢复到等待确认、运行中或已完成状态。
- [x] 对已提交长任务只轮询，不再次调用生成 handler。
- [x] 运行 Job、task store、双实例和故障恢复回归。

**完成证据：** 所有重复路径只存在一个资源 Job；重启后能继续查看和完成流程。

## Task 5：统一 `ResearchBundle` 与全部资源证据消费

**目标：** RAG、Web 和图片只研究一次，所有计划内资源实际消费同一研究结果。

**文件：**

- Create: `api/src/app/chat/domain/research_bundle.py`
- Create: `api/src/app/chat/runtime/research/builder.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/retrieval.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/image_search.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/report.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/lesson_plan.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/quiz.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/resource.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/classroom.py`
- Modify: `api/src/app/services/generation_task_handlers.py`
- Create: `api/src/tests/chat/runtime/test_research_bundle.py`
- Create: `api/src/tests/chat/runtime/test_all_resources_consume_research.py`

**步骤：**

- [x] 用唯一知识事实写 selected/course_auto/none 三种失败测试。
- [x] 写 Web 来源、图片 provenance、去重、证据不足和跨资源复用测试。
- [x] 实现 `ResearchBundle` 构建、质量摘要和引用标识。
- [x] 将研究包引用放入 GenerationCommand，生成器必须回报实际消费状态。
- [x] 以报告现有 grounding 为参考，为博客、习题、闪卡、思维导图、小游戏和教案补齐证据消费协议；AI 课堂改为引用同一 bundle，而不是单独拼接文本。
- [x] Trace 仅记录 bundle ID、计数和引用 ID，不保存完整私有正文。
- [x] 确保 `none` 不泄露课程知识库事实。
- [x] 运行资源生成集成回归。

**完成证据：** 八类非 PPT 资源都能证明是否使用 RAG/Web/图片，而不是只在快照中保存字段。

## Task 6：结构化自检与故障恢复

**目标：** 把“Agent 自检”变成可机器验证的完成门禁，不依赖泛化反思提示词。

**文件：**

- Create: `api/src/app/chat/domain/verification_report.py`
- Create: `api/src/app/chat/runtime/verification/plan_verifier.py`
- Create: `api/src/app/chat/runtime/verification/artifact_verifier.py`
- Create: `api/src/app/chat/runtime/verification/persona_verifier.py`
- Modify: `api/src/app/chat/runtime/reflection/rules.py`
- Modify: `api/src/app/chat/runtime/nodes/reflect.py`
- Modify: `api/src/app/chat/runtime/graph/builder.py`
- Create: `api/src/tests/chat/runtime/test_verification_report.py`
- Create: `api/src/tests/chat/runtime/test_agent_failure_recovery.py`

**步骤：**

- [x] 写工具缺失、顺序错误、禁止工具、重复任务、材料缺失、证据未消费等失败测试。
- [x] 区分 `accepted/running/succeeded/partial/failed/cancelled/timed_out`，禁止把 Job 接受当作资源完成。
- [x] 实现代码规则 verifier 和 `pass/partial/retry/fail` 决策表。
- [x] 将 LLM/Vision reviewer 限制为内容质量补充，不得覆盖执行事实。
- [x] 对 RAG 空、Web 失败、图片失败、参数错误、Provider fallback、Job 失败分别实现策略。
- [x] 材料包允许部分成功，并精确列出失败资源；不回滚已完成材料。
- [x] Job 成功后必须读取 `result_ref` 指向的材料；材料不存在、无权限或内容不可解析时判定 `artifact_unreadable`。
- [x] 运行故障注入与全 runtime 回归。

**完成证据：** 所有成功都可由 trace、Job、材料和 VerificationReport 共同证明。

## Task 7：教师助手语气与学生策略扩展点

**目标：** 教师端稳定表现为备课助手，同时预留学生端引导式教学策略。

**文件：**

- Modify: `api/src/app/chat/runtime/nodes/prompts.py`
- Modify: `api/src/app/chat/runtime/planning/prompts.py`
- Modify: `api/src/app/chat/runtime/react_agent.py`
- Modify: `api/src/app/chat/application/response_builder_v2.py`
- Create: `api/src/app/chat/runtime/persona/teacher.py`
- Create: `api/src/app/chat/runtime/persona/student.py`
- Create: `api/src/tests/chat/runtime/test_teacher_persona.py`
- Create: `api/src/tests/chat/runtime/test_student_persona_contract.py`

**步骤：**

- [x] 建立正反例语料：行动导向、无谓教学、连续追问、过度寒暄、内部思维泄露。
- [x] 教师提示词只注入角色和沟通规则，不负责修复工具顺序。
- [x] 删除 fast path 中默认的“2-3 个延伸学习方向”和“理解反问”要求，改为备课行动导向的轻量下一步建议。
- [x] 清晰请求默认执行，非关键参数采用资源默认；追问预算为 1。
- [x] 普通 QA 从课堂讲解、教学案例、易错点角度组织，但不擅自生成资源。
- [x] 学生策略测试验证提示优先、关键点反问和反问预算，不接入学生端路由。
- [x] 使用规则检查 + LLM Judge + 人工抽检评估语气。

**完成证据：** 教师语气合规率达到 95%，清晰请求无谓追问率不超过 5%。

## Task 8：建立版本化 Agent Eval Dataset

**目标：** 将 Agent 评价从单次脚本升级为可重复实验。

**阶段处理：** 第一阶段未实施，完整内容顺延并升级为第二阶段 Task 11，作为智能优化的第一项工作。

**文件：**

- Create: `api/src/evals/teacher_agent/cases.yaml`
- Create: `api/src/evals/teacher_agent/failure_cases.yaml`
- Create: `api/src/evals/teacher_agent/persona_cases.yaml`
- Create: `api/src/scripts/eval_teacher_agent.py`
- Create: `api/src/app/chat/evals/evaluators.py`
- Create: `api/src/tests/chat/runtime/test_eval_dataset_schema.py`

**步骤：**

- [x] 至少建立 80 个离线 case：路由、来源、单资源、材料包、多轮、故障和角色。
- [x] 数据集固定 schema_version、case_id、capability、对话轮次、预期契约、预期工具偏序、终态和敏感数据策略。
- [x] evaluator 优先检查结构事实：工具集合、顺序、次数、Job、材料、grounding。
- [x] 仅对语气和教学质量使用 LLM Judge，并保存 Judge 模型版本。
- [x] 支持同一 case 重复 5 次并统计稳定率，而不是覆盖结果。
- [x] 输出 JSON 与 Markdown 报告，包含通过率、P50/P95、模型/Provider、失败聚类。
- [x] 建立 CI 快速集和本机真实服务完整集。

**完成证据：** 每次 Agent 变更都能产生与历史版本可比较的实验报告。

## Task 9：扩展真实 Agent 端到端测试

**目标：** 从真实对话入口验证规划、工具、任务、材料和语气，而不只测试 handler。

**文件：**

- Modify: `api/src/scripts/smoke_teacher_agent_tools.py`
- Modify: `api/src/scripts/smoke_teacher_agent_generation.py`
- Create: `tests/e2e/teacher-agent-orchestration.spec.ts`
- Modify: `tests/e2e/fixtures/teacherApp.ts`
- Modify: `docs/acceptance/2026-08-09-stable-teaching-agent-optimization-acceptance.md`

**步骤：**

- [x] 真实执行普通 QA、selected RAG、course_auto RAG、Web、RAG+Web 与图片。
- [x] 真实执行八类非 PPT 单资源并验证实际材料。
- [x] 真实执行默认材料包；显式扩展材料包由编译器/集成测试覆盖。
- [x] 验证“查找网络，生成快速排序报告”为 `web_search → generate_report → verify`。
- [x] 验证“按勾选文档准备教学材料”为 `rag_search → confirm → generate_* → verify`。
- [x] 浏览器验证计划卡、确认、后台任务、部分成功、取消和恢复。
- [x] 关键核心契约在两个可用 Provider 通道各重复 5 次，共 20/20。

**完成证据：** 真实对话链路达到 SPEC 指标，报告中保留 trace、Job、材料 ID 和耗时。

## Task 10：全量回归、性能与最终验收

**目标：** 证明优化没有破坏教师端既有功能，并形成真实交付记录。

**文件：**

- Modify: `docs/acceptance/2026-08-09-stable-teaching-agent-optimization-acceptance.md`
- Modify: `docs/acceptance/2026-08-09-agent-capability-status.md`
- Review: 本计划涉及的全部生产代码和测试

**步骤：**

- [x] 运行 Agent/runtime 目标回归。
- [x] 运行完整后端测试。
- [x] 运行前端单元测试、构建和教师端核心浏览器自动化。
- [x] 执行真实 Eval Dataset 和 Agent E2E 矩阵。
- [x] 执行重启、双实例、超时和部分失败演练。
- [x] 检查敏感数据、日志、补丁格式和意外生成文件。
- [x] 填写全部验收指标；未通过项保留说明。
- [x] 更新 SPEC、计划与验收文档，明确新能力、限制和下一阶段建议。

**完成证据：** SPEC 完成定义全部满足；验收报告包含真实数字与可复验证据。

## 3. 阶段门禁

| 门禁 | 通过条件 | 未通过时 |
|---|---|---|
| Contract Gate | UI 来源/权限无法被模型覆盖 | 不进入计划执行改造 |
| Plan Gate | 所有对抗计划都被编译器纠正或拒绝 | 不开放生成工具 |
| Tool Gate | 阶段白名单、幂等和终止条件通过 | 不执行真实生成冒烟 |
| Evidence Gate | 八类资源实际消费 ResearchBundle | 不签收 grounding |
| Persona Gate | 教师语气和追问指标达标 | 不签收对话体验 |
| Stability Gate | 五次重复和故障注入达标 | 不以单次成功签收 |
| Release Gate | 全量回归与真实 E2E 通过 | 不更新为已完成状态 |

## 4. 计划中的既定决策

执行中默认采用以下选择，不再为这些事项暂停询问：

- 继续使用 LangGraph；
- 单 Agent；
- 固定模板包住有界 ReAct；
- 结构化 Tool Calling，不增加 CodeAgent；
- 默认教学材料包为教案、练习题、思维导图；
- AI 课堂必须显式请求并确认；
- Agent run 状态写入 SQLite 持久层；
- 代码规则先于 LLM Judge；
- 学生端只做策略接口，不做产品实现；
- PPT 继续延期。

只有涉及新增付费服务、破坏现有数据模型、扩大到 PPT 或学生端产品、改变课程权限边界时，才需要重新请求产品决策。

## 5. 第一阶段执行回填（2026-08-09）

已完成本计划的核心实现和自动化验证。额外修复了一项真实端到端发现：确认生成的计划在 `verify_task` 后进入空白名单的 `report_result` 步骤时，模型可能继续请求 `get_task_result`，严格模式会拒绝该调用并错误地以中止结果覆盖成功轨迹。现由 `executor` 直接完成该服务端终态步骤，标记计划完成并返回原始 trace 与 `VerificationReport`。

验证结果：新增终态单元回归与计划回归 33 通过；后端全量 1314 通过、2 跳过（523.55 秒）；此前前端单测 223 通过、生产构建通过。真实服务验证包含四种信息来源组合（普通、课程 RAG、Web、RAG+Web）、联网报告生成与 12 轮连续对话。详细任务/材料证据与仍未覆盖范围见验收文档。

## 6. 第二阶段智能优化实施计划

### 6.1 执行顺序

```text
冻结智能评测基线
→ TeachingTaskContract v2
→ 三层记忆与任务绑定
→ 研究查询分解与证据覆盖
→ 成本/质量感知的工具策略
→ 资源级教学质量契约
→ 最小步骤自修复
→ 五次重复与双 Provider
→ 浏览器 E2E 和最终签收
```

### Task 11：建立版本化智能评测基线

**目标：** 先定义并测量“更智能”，避免以提示词观感代替能力提升。

**主要交付：**

- `api/src/evals/teacher_agent/cases.yaml`：不少于 80 个意图、来源、工具、长对话、故障和 Persona 用例；
- `api/src/evals/teacher_agent/failure_cases.yaml`；
- `api/src/scripts/eval_teacher_agent.py`；
- 结构事实评分器、教学质量 Judge 接口、JSON/Markdown 报告；
- 当前版本基线报告和失败聚类。

**状态：** [x] 已完成；80 个版本化用例连续 5 次，共 400/400 通过，报告位于 `evaluation/reports/2026-08-09-teacher-agent-task11-17-repeat5.*`。

### Task 12：TeachingTaskContract v2 与受控澄清

**目标：** 为每个关键字段记录值、来源、置信度、缺失/冲突原因，并把澄清限制在真正影响范围、成本或不可逆动作的歧义上。

**验收：** 契约字段准确率 ≥98%，高影响歧义召回率 ≥95%，清晰请求无谓追问率 ≤5%。

**状态：** [x] 已完成；字段证据、置信度、歧义与一次受控澄清已进入契约和评测。

### Task 13：三层记忆和长对话任务绑定

**目标：** 将原始消息、工作记忆、任务账本分离；摘要只压缩叙述，不得丢失确认点、来源、约束、Job 和材料引用。

**验收：** 50 轮后修改、确认、取消和状态查询均绑定正确任务；重启后恢复一致；不同课程/用户状态隔离。

**状态：** [x] 已完成；50 轮任务绑定、确认点保持、用户/课程隔离和 SQLite 恢复测试通过，另有 12 轮真实对话证据。

### Task 14：研究规划与证据覆盖

**目标：** 对复杂问题拆分检索子问题，对 RAG/Web 结果去重、分级和覆盖检查；证据不足时只补检索缺口。

**验收：** 来源权限 100% 合规，证据覆盖率 ≥95%，无来源回答和重复检索都有明确 trace。

**状态：** [x] 已完成；查询分解、来源去重、可信度、覆盖缺口与最多一次补检索均有结构化 trace 和回归。

### Task 15：成本/质量感知的工具决策

**目标：** 在计划允许集合内依据证据增益、预计耗时、供应商状态和历史 Observation 选择工具，禁止无收益重复调用。

**验收：** 必需工具召回率 100%，禁止工具调用率 0%，无收益重复工具调用率 ≤2%。

**状态：** [x] 已完成；检索工具按证据增益、成本、预算和既有 Observation 决策，必需/禁止/重复调用回归通过。

### Task 16：资源质量契约与最小步骤修复

**目标：** 为报告、教案、习题、博客、闪卡、导图、小游戏和 AI 课堂建立资源级质量检查；执行失败、证据不足和内容质量失败分别处理，只重做失败的最小步骤。

**验收：** `VerificationReport` 与执行事实一致率 100%；已成功材料不因其他子任务失败而重复生成；partial 结果可准确解释。

**状态：** [x] 已完成；八类资源质量契约、四类审计、材料读回和失败最小步骤修复已实现并验证。

### Task 17：稳定性、Provider 与浏览器签收

**目标：** 完成关键用例五次重复、至少两个 Provider、故障注入和教师端浏览器全流程。

**验收：** 五次执行合规率 ≥98%，双 Provider 核心通过率 ≥95%；浏览器覆盖确认、进度、预览、取消、断线恢复和部分成功。

**状态：** [x] 已完成；结构评测 400/400，Qwen 与 OpenRouter 两通道核心矩阵各连续 5 次共 20/20，浏览器覆盖确认、三资源材料包、进度、预览、取消、服务重启恢复和 partial 展示。

### 6.2 每个任务的统一完成要求

每个 Task 必须同时满足：生产代码、失败先行测试、目标回归、全量回归、真实 trace/材料证据、文档回填。未通过项必须保留，不能通过降低断言或把单次成功改写为稳定性结论来签收。

### 6.3 最终实施证据（2026-08-09）

- 版本化评测：80 个用例 × 5 次，400/400 通过，无失败聚类；
- 最终后端全量：1369 passed、2 skipped、2 条既有弃用警告，303.13 秒；前端 223 passed，生产构建通过；
- 双 Provider：`qwen3.5-plus` 与 `openai/gpt-5.4-mini`，文本契约和必需工具契约各执行 5 次，20/20 通过；
- 真实来源：普通、课程自动 RAG、选中文档 RAG、Web、RAG+Web 与图片搜索均通过；选中文档使用临时个人知识库夹具，验收后已删除远端文档；
- 真实资源：报告、教案、习题、博客、闪卡、导图、小游戏和 AI 课堂均达到 Job 终态并落库；
- 材料包：一次确认提交教案、10 道练习题和思维导图，三个 Job 全部成功且均可在资源页打开；
- 浏览器：确认边界、计划/工具卡、后台进度、结果预览、取消、页面重载、服务重启恢复和 partial 状态均已覆盖；
- 真实缺陷修复：无工具步骤重复调用、严格单工具幻觉、课堂专用大纲、主题误删“归并”的“并”、材料包确认丢资源、确认态丢图片需求与材料包终态只汇报最后任务。
