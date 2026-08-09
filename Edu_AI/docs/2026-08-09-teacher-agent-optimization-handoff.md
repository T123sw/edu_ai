# 教师端 Agent 智能优化工作交接

> 日期：2026-08-09
> 项目目录：`D:\github\edu_ai\Edu_AI`
> 下一阶段目标：在不追求高自治和复杂多 Agent 的前提下，把教师端 Agent 优化成稳定、可验证、能正确规划并调用工具的备课助手。

## 1. 交接结论

教师端的基础功能修复与资源生成链路已经完成一轮实现和真实端到端验证。当前 Agent 已能完成普通问答、RAG、Web 检索以及八类非 PPT 资源生成，并能在明确场景下保持“先检索、后生成”的基本顺序。

下一轮不应重新建设资源生成模块，也不应迁移 Agent 框架。应以现有 LangGraph、Planner、Executor、Tools、Reflect 和后台 Job 体系为基础，集中解决以下问题：

1. 将自由度较高的规划收敛为少量稳定的教学工作流模板。
2. 统一工具输入、输出、错误、重试、幂等和成功判定契约。
3. 让 RAG、Web、图片和资源生成之间的顺序可预测、可验证。
4. 建立可重复运行的 Agent 评测集，重点衡量稳定率而不是单次“看起来聪明”。
5. 将教师端语气固定为帮助教师完成备课的教学助手，而不是向教师讲课的学习导师。

## 2. 产品范围和不可变决策

以下决策已经由用户确认，下一轮不得自行扩大范围：

- 当前只实现教师端；学生端后续再做。
- 教师端 Agent 的角色是“备课与教学资源助手”，核心价值是减轻教师工作量。
- 学生端未来使用引导式教师 Persona，可反问和启发，但当前只保留策略接口，不实现完整学生端。
- PPT 模块后置。用户计划评估并可能接入开源项目 `ppt-master`，本轮不得把 PPT 作为阻断项。
- Agent 不需要处理高复杂度通用任务，也不需要多 Agent 团队、深层计划树或完全自由的自治 ReAct。
- 优先保证工具选择、调用顺序、失败恢复、任务终态和结果落库稳定。
- 用户勾选文档时，必须先检索这些文档再回答或生成；不得先回答、后补检索。
- 未勾选文档时，默认不使用知识库；用户可显式选择使用课程知识库全部数据，此时按主题检索相关内容，不能拼接全库正文。
- 图文资源链路采用“先生成内容大纲和图片需求，再从知识库/Web 找图并审核，最后带图生成正文或资源”的顺序。
- 遇到一般实现决策时，先选择风险最低、最稳定的方案并记录；只有会改变产品范围或造成不可逆外部影响时才向用户确认。

## 3. 当前已经完成并验证的能力

### 3.1 基础 Agent 能力

- 普通问答不误调用工具。
- 已选文档 RAG。
- 课程知识库全库相关检索（`course_auto`）。
- Web 检索。
- RAG 与 Web 联合检索。
- “先查网络，再生成报告”能够形成 `web_search -> generate_report` 顺序。
- 报告和教案的大纲确认边界已实现：首轮生成大纲，确认后才提交后台生成任务。
- Agent 规划器、执行器和正文生成支持已配置模型之间的故障切换。
- 后台资源生成使用统一 Job 体系，可查询终态和结果引用。

### 3.2 已通过真实生成的非 PPT 资源

- 教学报告
- 教案
- 教学博客
- 习题
- 闪卡
- 思维导图
- 课堂小游戏
- AI 课堂

验收不能只看接口返回 202 或工具名称。必须同时验证：

1. 工具顺序正确。
2. 工具调用成功。
3. Job 最终为 `succeeded`。
4. `result_ref` 存在。
5. 资源已落库并可在“我的资源”中打开。
6. 资源预览内容真实可用。

### 3.3 最近完成的 RAG 溯源修复

最新修复解决了“五个来源点击后仍高亮相同关键词”的问题：

- 生成模型仍使用父章节扩展上下文，以保持回答质量。
- 溯源接口改为返回真实命中的子片段，不再把多个子片段统一替换成同一父章节。
- 历史对话按 `chunk_id` 回填了原始检索片段。
- 前端按完整片段匹配，支持换行、缩进和代码块映射。
- 无法精确对齐时，单独展示实际检索内容，禁止用重复关键词伪装成来源高亮。
- 已在真实教师页面依次点击来源 1—5，确认其分别定位到不同的说明段、Java 代码、C# 代码、正文和 JS 分栏标记。

注意：第 5 条索引片段本身只有一行 `=== "JS"`。当前界面忠实展示该片段；这属于后续分块质量优化问题，不是高亮截断。

## 4. 当前代码入口

### 4.1 Agent 主链路

- `api/src/app/chat/runtime/fast_chat_runtime.py`
- `api/src/app/chat/runtime/react_agent.py`
- `api/src/app/chat/runtime/nodes/planner.py`
- `api/src/app/chat/runtime/nodes/executor.py`
- `api/src/app/chat/runtime/nodes/tools.py`
- `api/src/app/chat/runtime/nodes/prompts.py`
- `api/src/app/chat/runtime/planning/schema.py`
- `api/src/app/chat/runtime/planning/prompts.py`
- `api/src/app/chat/runtime/agent_tools/registry.py`
- `api/src/app/chat/runtime/agent_tools/schemas.py`
- `api/src/app/chat/runtime/agent_tools/tool_meta.py`
- `api/src/app/chat/runtime/agent_tools/handlers/`

### 4.2 检索与证据

- `api/src/app/chat/runtime/agent_tools/handlers/retrieval.py`
- `api/src/app/chat/tools/search_tools.py`
- `api/src/app/integrations/rag_client.py`
- `api/src/modules/rag_v2/rag_main/system.py`
- `api/src/modules/rag_v2/document_resolver.py`
- `src/components/teacher/ChatPanel.tsx`
- `src/components/teacher/SourcePanel.tsx`
- `src/components/teacher/sourceHighlight.ts`

### 4.3 资源工具与后台任务

- `api/src/app/chat/runtime/agent_tools/handlers/report.py`
- `api/src/app/chat/runtime/agent_tools/handlers/resource.py`
- `api/src/app/chat/runtime/agent_tools/handlers/classroom.py`
- `api/src/app/services/generation_task_handlers.py`
- `api/src/app/services/platform_task_handlers.py`
- `api/src/app/services/generation_source_resolver.py`
- `src/components/teacher/generation/`

## 5. 必读文档

开始实现前应先核对以下文档与当前代码，不要直接假定计划中的项目已经实现：

1. [Agent 能力现状与真实验收基线](acceptance/2026-08-09-agent-capability-status.md)
2. [稳定教学 Agent 开源方案调研](research/2026-08-09-stable-teaching-agent-open-source-research.md)
3. [稳定教学 Agent 优化 SPEC](superpowers/specs/2026-08-09-stable-teaching-agent-optimization-design.md)
4. [稳定教学 Agent 执行计划](superpowers/plans/2026-08-09-stable-teaching-agent-optimization.md)
5. [稳定教学 Agent 验收文档](acceptance/2026-08-09-stable-teaching-agent-optimization-acceptance.md)
6. [可可信 Agent 与多模态资源生成验收](acceptance/2026-08-09-grounded-agent-and-multimodal-resource-generation.md)

其中“Agent 能力现状”与“可可信 Agent 验收”记录的是已经真实运行过的能力；“稳定教学 Agent 优化 SPEC、计划、验收”主要定义下一阶段目标，开始时必须进行代码审计并更新实际完成状态。

## 6. 下一轮建议架构

继续使用现有 LangGraph，不做框架迁移。建议采用：

```text
确定性教学工作流
  ├─ 意图与材料包解析
  ├─ 获取信息（RAG / Web / 图片）
  ├─ 资源生成或修改
  ├─ 结构化自检
  └─ 结果汇报
        └─ 每个阶段内部允许有限 ReAct
```

设计原则：

- 工作流代码负责阶段、顺序、权限、预算、终止条件和确认边界。
- 模型负责自然语言理解、参数补全和当前阶段内的局部判断。
- 强制 RAG、Web 或图片时，不使用完全自由的 `auto` 工具选择。
- 每个阶段最多两次工具尝试；整次任务最多一次重规划。
- 不展示内部思维链，只展示简洁计划、工具状态、证据和结果。
- 规则型判断用代码完成；语气和开放内容质量才使用模型评价。

## 7. 下一轮优先级

### P0：稳定工作流和工具契约

1. 定义少量任务类型：普通问答、单资源生成、教学材料包、资源修改、状态查询、取消和确认续跑。
2. 定义统一的 `TaskIntent`、`PlanStep`、`ToolObservation`、`SelfCheckResult` 和终态模型。
3. 为每个工具声明允许阶段、必填参数、成功条件、可恢复错误和不可恢复错误。
4. 强制顺序约束：检索和图片获取必须在依赖它们的生成工具之前完成。
5. 给所有资源生成工具加入幂等键，避免模型重试时重复创建资源。
6. 将 Job `succeeded`、`result_ref` 和资源可读取性纳入工具成功条件。

### P0：教师 Persona

- 默认主动帮教师完成任务，少讲概念、少反问。
- 缺少非关键参数时使用可靠默认值，不让教师填长表。
- 只有缺少会显著改变产物的关键信息时才追问。
- 回答重点为“已完成什么、生成到哪里、还需要教师决定什么”。
- 禁止把教师当学生进行知识点测验或无必要的启发式反问。

### P1：教学材料包

将“帮我准备快速排序的教学材料”定义成确定性组合意图。建议默认材料包为：

- 教案
- 习题
- 思维导图或闪卡（二选一，可由课程阶段决定）

如果用户明确列出资源类型，则只生成所列资源。报告、教学博客、小游戏和 AI 课堂不应默认全部生成，以控制耗时和成本。

### P1：统一 ResearchBundle

目前报告对 RAG/Web 证据消费最完整，其他资源仍需统一。建议抽取 `ResearchBundle`：

- 检索摘要
- RAG 来源与片段
- Web 来源、标题和 URL
- 图片需求、候选、审核结果和最终位置
- 查询、时间、来源等级和去重信息
- 引用与事实覆盖信息

所有资源生成器只接收同一份已验证的 ResearchBundle，禁止各自重新发明检索结果格式。

### P1：有限 ReAct 和失败恢复

- RAG 零结果：允许一次查询重写；仍失败则说明证据不足。
- Web 结果质量差：允许一次更具体的查询。
- 图片未命中：允许一次关键词替换；仍失败则生成无图资源并记录原因。
- 参数结构错误：允许一次结构化修复。
- 后台任务已成功：禁止再次提交。
- 不可恢复错误直接终止当前分支，不进入无限循环。

### P1：评测与可观测性

- 每条评测记录意图、计划、工具顺序、工具参数、Observation、重试、重规划、Job、资源和耗时。
- 日志不得记录令牌或完整私有文档正文。
- 同一用例至少重复五次，目标稳定通过率不低于 98%。
- 规则指标由代码判定；教师语气和内容质量可增加人工抽检或受控 LLM Judge。

## 8. 必须覆盖的评测场景

| 场景 | 预期行为 |
|---|---|
| “解释一下快速排序”且未启用工具 | 直接简洁回答，不调用生成工具 |
| 已勾选文档后提问 | `rag_search` 必须是回答前的第一阶段 |
| 未勾选文档但启用全课程知识库 | 使用 `course_auto` 检索相关片段，不拼接全库 |
| “查找网络，生成快速排序报告” | `web_search -> 大纲/确认 -> generate_report -> 自检` |
| “根据资料和网络准备快速排序教案” | RAG 与 Web 完成后才可生成教案 |
| “帮我准备快速排序教学材料” | 使用默认材料包，顺序稳定，资源不重复 |
| “生成教案和五道习题” | 只创建教案和习题，并正确传递题量 |
| 报告/教案首轮 | 只展示大纲并等待确认，不立即提交任务 |
| RAG 零结果 | 一次重写后说明证据不足，不伪造引用 |
| Web 失败 | 有界重试或明确降级，不无限重规划 |
| 资源任务重复回调 | 幂等命中已有任务，不创建重复资源 |
| Job 成功但材料不可读 | 自检失败，不向教师宣称完成 |
| 教师语气 | 以备课助手语气汇报，不向教师出题反问 |
| 五次重复运行 | 工具集合、顺序和终态保持稳定 |

## 9. 测试与验收入口

### 9.1 自动化

```powershell
cd D:\github\edu_ai\Edu_AI\api
$env:PYTHONPATH='src'
D:\anaconda\envs\edu-ai\python.exe -m pytest -q

cd D:\github\edu_ai\Edu_AI
npm test
npm run build
```

Agent 重点回归：

```powershell
cd D:\github\edu_ai\Edu_AI\api
$env:PYTHONPATH='src'
D:\anaconda\envs\edu-ai\python.exe -m pytest `
  src/tests/chat/runtime/test_agent_tools.py `
  src/tests/chat/runtime/test_mandatory_retrieval_plan.py `
  src/tests/chat/runtime/test_phase5_strict.py `
  src/tests/chat/test_tool_registry.py -q
```

### 9.2 真实 Agent 冒烟

- `api/src/scripts/smoke_teacher_agent_tools.py`
- `api/src/scripts/smoke_teacher_agent_generation.py`
- `api/src/scripts/smoke_teacher_generation.py`

真实执行必须使用本机现有配置，并通过环境变量提供令牌。不得把令牌写入脚本、命令历史、日志或文档。验收必须检查真实工具 trace、Job 终态、`result_ref` 和资源可读性。

### 9.3 当前本机状态

- 前端开发服务：`http://127.0.0.1:5173`
- API：`http://127.0.0.1:8001`
- 当前 RAG 存储根：`D:\github\edu_ai\Edu_AI\api\src\storage`
- 当前健康检查已通过，知识库加载 3641 个片段。

端口和进程状态可能在新对话开始前变化，必须先做只读检查再决定是否重启。重启时应显式设置正确的 `PYTHONPATH` 和 `STORAGE_ROOT`，避免启动到另一个空存储目录。

## 10. 最近一次修复后的验证结果

以下结果属于最近的 RAG 溯源修复：

- 浏览器真实点击来源 1—5：通过。
- 前端自动化：223 项通过。
- 后端相关测试：10 项通过。
- 前端生产构建：通过。
- API 健康检查：通过。

更大范围的 1280 项后端回归和八类资源真实 E2E 是此前同日基线，详见验收文档；下一轮完成 Agent 优化后必须重新运行，不得直接沿用为新实现的通过证据。

## 11. 工作区保护要求

当前工作区存在大量未提交改动，其中既有本轮修复，也有用户此前的知识库和教师端改动。

- 禁止 `git reset --hard`、`git checkout --` 或批量覆盖工作区。
- 修改前先查看 `git status` 和相关文件 diff。
- 不要清理或回滚与当前任务无关的改动。
- 新增评测数据和文档时使用独立文件，避免覆盖现有验收记录。
- 先审计现有优化 SPEC/计划与代码的差异，再更新实施状态。

## 12. 建议的新对话启动顺序

1. 阅读本交接文档及第 5 节列出的六份文档。
2. 检查工作区、当前服务、模型配置和测试基线。
3. 对照稳定 Agent SPEC 审计代码，列出“已实现、部分实现、未实现”。
4. 先建立版本化评测集和失败基线，再修改 Planner/Executor。
5. 按 P0 稳定工作流与契约、P0 Persona、P1 材料包、P1 ResearchBundle、P1 恢复与评测的顺序实施。
6. 每个阶段先写失败测试，再实现，再运行相关回归。
7. 最终执行自动化、真实 Agent 对话、Job/资源落库和五次重复稳定性验收。
8. 更新 SPEC、计划和验收文档，保留所有失败记录及处理决定。

## 13. 可直接复制到新对话的启动提示词

```text
请开始教师端 Agent 智能优化工作。

项目目录：D:\github\edu_ai\Edu_AI
首先完整阅读：
1. docs/2026-08-09-teacher-agent-optimization-handoff.md
2. docs/acceptance/2026-08-09-agent-capability-status.md
3. docs/research/2026-08-09-stable-teaching-agent-open-source-research.md
4. docs/superpowers/specs/2026-08-09-stable-teaching-agent-optimization-design.md
5. docs/superpowers/plans/2026-08-09-stable-teaching-agent-optimization.md
6. docs/acceptance/2026-08-09-stable-teaching-agent-optimization-acceptance.md

先检查当前代码和未提交改动，禁止重置或覆盖用户工作区。对照 SPEC 做实现审计，明确已实现、部分实现和未实现项，然后从评测基线与 P0 稳定工作流开始执行。

目标不是追求复杂自治，而是让教师端 Agent 作为备课助手，稳定完成：意图识别 -> RAG/Web/图片获取 -> 资源工具调用 -> 有界恢复 -> 自检 -> Job 与资源落库验证。必须保证用户启用或选择的检索先于回答和资源生成；PPT 与学生端不在本轮范围。

请持续执行到完成，并进行自动化测试、真实对话工具调用、后台 Job、资源落库、五次重复稳定性和教师 Persona 验收。遇到一般决策先采用风险最低且最稳定的方案并记录，只有改变范围或需要新权限时再询问我。
```

## 14. 下一阶段完成定义

只有同时满足以下条件，才能宣布 Agent 智能优化完成：

- 任务路由、工具集合、顺序和终态满足固定契约。
- 已选文档、课程全库、Web 和组合检索均先于回答或生成。
- 八类非 PPT 资源能通过 Agent 真实调用并完成 Job、落库和预览。
- 默认教学材料包与显式材料包行为正确且无重复资源。
- 可恢复错误只有有限重试，不可恢复错误能清晰终止。
- 结构化自检能识别缺工具、错顺序、零证据、重复提交和材料不可读。
- 教师 Persona 达标，不把教师当学生教学。
- 同一核心用例五次重复后的总稳定通过率不低于 98%。
- 自动化、真实 E2E、性能记录和验收文档全部更新，失败项没有被删除或隐藏。
