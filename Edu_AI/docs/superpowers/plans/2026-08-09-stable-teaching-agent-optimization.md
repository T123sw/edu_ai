# 稳定型教学 Agent 能力优化执行计划

> 日期：2026-08-09
> 状态：待执行；本轮只完成设计，不实施代码
> 对应 SPEC：`docs/superpowers/specs/2026-08-09-stable-teaching-agent-optimization-design.md`
> 验收文档：`docs/acceptance/2026-08-09-stable-teaching-agent-optimization-acceptance.md`

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

- [ ] 将现有通过用例转换为稳定的 case ID，不改变运行逻辑。
- [ ] 记录当前意图、工具顺序、模型轮次、耗时、Job 和材料终态。
- [ ] 为现有已知缺口建立预期失败用例：教师语气、材料包、重复提交、跨重启恢复、统一研究包。
- [ ] 运行当前目标测试集，确认新增用例按预期 RED，旧用例保持 GREEN。

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

- [ ] 写测试覆盖七类意图、九类资源枚举、三种知识来源和三种 Web/图片策略。
- [ ] 写测试证明 UI capability 覆盖模型输出，明确资源关键词覆盖概率分类。
- [ ] 实现 `TeachingTaskContract`、版本号、规范化和默认值。
- [ ] 实现教师与学生 `PersonaPolicy`；当前请求固定解析为教师角色。
- [ ] 对非法字段、未知资源和模型虚构的 selected document ID fail closed。
- [ ] 运行契约、请求规范化和上下文相关回归。

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

- [ ] 为 QA、单资源、材料包、修改、确认、状态和取消写计划快照测试。
- [ ] 写对抗测试：模型漏 RAG、把 Web 放最后、生成提前、重复生成、非法 action、循环依赖。
- [ ] 实现枚举化 `CompiledPlan` 与 dependency validator。
- [ ] 实现默认材料包：教案 + 练习题 + 思维导图；高成本 AI 课堂必须显式请求。
- [ ] 将当前多个后置 `_ensure_*` 修正逻辑收敛到一个编译器，不保留两套权威计划。
- [ ] 计划不合法时使用确定性模板回退，不直接放行自由 Executor。
- [ ] 运行规划和 ReAct 现有回归。

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

- [ ] 写测试证明每一阶段只暴露合法工具，空白 allowlist 不得回退为全部工具。
- [ ] 写最大轮次、最大工具调用、一次重试、一次重规划和超时测试。
- [ ] 将 `tool_choice` 按计划设为禁止、自动、指定或必需，而不是全程 `auto`。
- [ ] 将 Observation 规范化为短结构，不把整份工具输出重复塞入消息历史。
- [ ] 达到生成提交、等待确认、明确失败或预算上限时立即终止。
- [ ] 运行全部 runtime 测试，检查无死循环。

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

**实现决策：** 采用与现有 durable task store 一致的 SQLite 持久层保存 Agent run snapshot，不继续依赖仅进程内有效的 `MemorySaver`；不要把高频步骤状态继续写入整文件 JSON 对话存储。

**步骤：**

- [ ] 写重复确认、客户端重连、网关重试、双 API 实例和提交后超时测试。
- [ ] 实现基于 contract hash 的幂等键和原 Job 返回。
- [ ] 持久化任务契约、计划步骤、确认点、研究包引用、Job 引用和验证结果。
- [ ] 服务重启后从持久层恢复到等待确认、运行中或已完成状态。
- [ ] 对已提交长任务只轮询，不再次调用生成 handler。
- [ ] 运行 Job、task store、双实例和故障恢复回归。

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

- [ ] 用唯一知识事实写 selected/course_auto/none 三种失败测试。
- [ ] 写 Web 来源、图片 provenance、去重、证据不足和跨资源复用测试。
- [ ] 实现 `ResearchBundle` 构建、质量摘要和引用标识。
- [ ] 将研究包引用放入 GenerationCommand，生成器必须回报实际消费状态。
- [ ] 为博客、习题、闪卡、思维导图、小游戏和教案补齐与报告一致的证据消费协议。
- [ ] 确保 `none` 不泄露课程知识库事实。
- [ ] 运行资源生成集成回归。

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

- [ ] 写工具缺失、顺序错误、禁止工具、重复任务、材料缺失、证据未消费等失败测试。
- [ ] 实现代码规则 verifier 和 `pass/partial/retry/fail` 决策表。
- [ ] 将 LLM/Vision reviewer 限制为内容质量补充，不得覆盖执行事实。
- [ ] 对 RAG 空、Web 失败、图片失败、参数错误、Provider fallback、Job 失败分别实现策略。
- [ ] 材料包允许部分成功，并精确列出失败资源；不回滚已完成材料。
- [ ] 运行故障注入与全 runtime 回归。

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

- [ ] 建立正反例语料：行动导向、无谓教学、连续追问、过度寒暄、内部思维泄露。
- [ ] 教师提示词只注入角色和沟通规则，不负责修复工具顺序。
- [ ] 清晰请求默认执行，非关键参数采用资源默认；追问预算为 1。
- [ ] 普通 QA 从课堂讲解、教学案例、易错点角度组织，但不擅自生成资源。
- [ ] 学生策略测试验证提示优先、关键点反问和反问预算，不接入学生端路由。
- [ ] 使用规则检查 + LLM Judge + 人工抽检评估语气。

**完成证据：** 教师语气合规率达到 95%，清晰请求无谓追问率不超过 5%。

## Task 8：建立版本化 Agent Eval Dataset

**目标：** 将 Agent 评价从单次脚本升级为可重复实验。

**文件：**

- Create: `api/src/evals/teacher_agent/cases.yaml`
- Create: `api/src/evals/teacher_agent/failure_cases.yaml`
- Create: `api/src/evals/teacher_agent/persona_cases.yaml`
- Create: `api/src/scripts/eval_teacher_agent.py`
- Create: `api/src/app/chat/evals/evaluators.py`
- Create: `api/src/tests/chat/runtime/test_eval_dataset_schema.py`

**步骤：**

- [ ] 至少建立 80 个离线 case：路由、来源、单资源、材料包、多轮、故障和角色。
- [ ] evaluator 优先检查结构事实：工具集合、顺序、次数、Job、材料、grounding。
- [ ] 仅对语气和教学质量使用 LLM Judge，并保存 Judge 模型版本。
- [ ] 支持同一 case 重复 5 次并统计稳定率，而不是覆盖结果。
- [ ] 输出 JSON 与 Markdown 报告，包含通过率、P50/P95、模型/Provider、失败聚类。
- [ ] 建立 CI 快速集和本机真实服务完整集。

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

- [ ] 真实执行普通 QA、selected RAG、course_auto RAG、Web、RAG+Web、图片。
- [ ] 真实执行八类非 PPT 单资源并验证实际材料。
- [ ] 真实执行默认材料包和显式扩展材料包。
- [ ] 验证“查找网络，生成快速排序报告”为 `web_search → generate_report → verify`。
- [ ] 验证“按勾选文档准备教学材料”为 `rag_search → confirm → generate_* → verify`。
- [ ] 浏览器验证计划卡、确认、后台任务、部分成功、取消和恢复。
- [ ] 关键用例在至少两个可用 Provider 通道各重复 5 次。

**完成证据：** 真实对话链路达到 SPEC 指标，报告中保留 trace、Job、材料 ID 和耗时。

## Task 10：全量回归、性能与最终验收

**目标：** 证明优化没有破坏教师端既有功能，并形成真实交付记录。

**文件：**

- Modify: `docs/acceptance/2026-08-09-stable-teaching-agent-optimization-acceptance.md`
- Modify: `docs/acceptance/2026-08-09-agent-capability-status.md`
- Review: 本计划涉及的全部生产代码和测试

**步骤：**

- [ ] 运行 Agent/runtime 目标回归。
- [ ] 运行完整后端测试。
- [ ] 运行前端单元测试、构建和教师端核心 Playwright。
- [ ] 执行真实 Eval Dataset 和 Agent E2E 矩阵。
- [ ] 执行重启、双实例、超时和部分失败演练。
- [ ] 检查敏感数据、日志、补丁格式和意外生成文件。
- [ ] 填写全部验收指标；未通过项不得标为完成。
- [ ] 更新 Agent 能力现状文档，明确新能力、限制和下一阶段建议。

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
