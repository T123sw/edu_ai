# DeepSeek Harness 接入前：功能拆分与代码审查

日期：2026-09-07。源码基线：`b045484adb8039a6f5c3f6392a5d1b8ff22fdf30`。性质：静态审查与迁移准备设计，未修改运行时代码。

## 1. 结论

当前系统并不缺工具或 Skills，而是同一个任务在多套入口、上下文和状态机中执行。正式接入 dsh 前，应先抽取独立业务能力和稳定契约，让 dsh 接管对话决策与工具调用循环，保留已有生成、存储、权限、课堂和学习服务。

当前 `agent_tools/registry.py` 注册了 **17 个工具：8 个生成入口和 9 个检索、规划、验证、查询及控制入口**。`backend/skills/` 有 **10 份 SKILL.md**，但不少内容绑定旧路由字段或旧产品能力，不能原样搬入新 Harness。

建议第一条正式适配路径为：**报告 Skill → 来源检索 → 结构化大纲 → 版本确认 → durable 生成任务 → 产物读取与验证**。上一轮独立实验只打通 Skill 与新写的大纲工具，尚未证明现有服务适配、审批恢复或完整报告链路。

本次覆盖聊天入口与总控、现有 Skills、工具注册与主要 handlers、生成任务服务及各资源入口、记忆、资料修改、知识建设、课堂和前端流协议。重点是职责与调用边界；并非逐行审计所有渲染器、算法或数据库实现，也未对所有工作流运行端到端测试。

## 2. 当前调用结构

```text
聊天 API／应用服务
  → MainOrchestrator.dispatch：规则路由 → fast 或旧 workflow
  → MainOrchestrator.dispatch_stream
      → action_hint：旧 workflow + background_runner
      → 普通流式：ReAct / LangGraph planner-executor-tools-reflect
      → 关闭 ReAct：旧规则路径

生成工具 handlers
  → GenerationCommandService → durable task → 资源生成 adapter → 产物发布
  → classroom 使用独立课堂任务／OpenMAIC 服务

知识库直接生成入口
  → direct_*_service_v2 等已有服务与任务路径
```

依据：[聊天入口](../../backend/src/app/chat/routes.py)、[RouteChatService](../../backend/src/app/chat/application/route_chat_service.py)、[ReplyService](../../backend/src/app/chat/application/reply_service_v2.py)、[MainOrchestrator](../../backend/src/app/chat/orchestrator/main_orchestrator.py)、[工具注册](../../backend/src/app/chat/runtime/agent_tools/registry.py)、[生成命令](../../backend/src/app/services/generation_command.py)。

重要边界：`GenerationCommand` 支持 report、lesson_plan、blog、quiz、flashcard、graph、game 七类，课堂是第八类生成工具，当前走独立服务；不要为了统一命名强行塞进尚不支持它的命令枚举。

## 3. 目标分层

| 层 | 负责什么 | 不应混入什么 |
| --- | --- | --- |
| 入口与上下文装配 | 认证、用户／课程／知识点范围、记忆读取、会话与任务引用 | 根据关键词编译整条内容生产流程 |
| 根角色与工作流 Skills | 角色、任务选择、澄清、内容策略、完成标准 | 数据库写入、身份判断、事务和无限重试 |
| dsh runtime adapter | 模型循环、Skill 加载、MCP、事件转译、会话生命周期 | 再内嵌一套旧 ReAct 总控循环 |
| Python 工具适配层 | 参数校验、权限、调用应用服务、结构化结果 | 依赖旧 ctx 私有缓存、让模型提供任意 owner |
| 应用／领域服务 | 检索、大纲、生成、校验、版本保存、任务控制 | 读取某段对话猜测任务是否获准执行 |
| 基础设施 | SQL、文件、向量索引、模型客户端、队列、OpenMAIC | 对话流程路由 |

**工具粒度以稳定输入输出、可复用性和独立失败边界决定。** 搜索、大纲、生成提交、任务查询值得分别暴露；JSON 解析、提示词拼装、数据库事务内部步骤不必全部做成模型工具。整个报告流程不能只剩一个不可介入的工具，但正文生成服务仍可内部完成分节生成、拼装和资源本地化。

## 4. 现有能力与建议拆分清单

下表的拟议工具名表示目标契约，不代表当前已经注册。

| 工作流／能力 | 当前代码落点 | 拆分与复用方向 | 优先级 |
| --- | --- | --- | --- |
| 普通教学问答 | [ReplyService](../../backend/src/app/chat/application/reply_service_v2.py)、[edu-dialogue-agent](../../backend/skills/edu-dialogue-agent/SKILL.md) | 根角色处理简单问答；需要资料时调用检索；不为每次解释启动报告工作流 | P0 |
| RAG 检索 | [handlers/retrieval.py](../../backend/src/app/chat/runtime/agent_tools/handlers/retrieval.py)、[generation_source_resolver.py](../../backend/src/app/services/generation_source_resolver.py) | 提取 `rag_search` 应用接口，保留授权资料范围；返回可追溯片段及引用。直接生成的资料解析与聊天检索共用范围校验 | P0 |
| 网络搜索与资料研究 | [deepsearch_service.py](../../backend/src/app/services/deepsearch_service.py)、[retrieval handler](../../backend/src/app/chat/runtime/agent_tools/handlers/retrieval.py) | `web_search` 获取来源；`fetch_source_content` 提取正文；`import_sources` 单独入库；research Skill 决定组合 | P0/P1 |
| 图片搜索与处理 | [image_search.py](../../backend/src/app/chat/runtime/agent_tools/handlers/image_search.py)、[visual_assets](../../backend/src/app/services/visual_assets/)、[报告图片模块](../../backend/src/app/chat/workflows/report/) | 保留搜索过滤与本地化；模型选用图片，下载、去重、存储作为服务内部步骤 | P1 |
| 大纲生成 | [handlers/outline.py](../../backend/src/app/chat/runtime/agent_tools/handlers/outline.py)、[outline_parser.py](../../backend/src/app/chat/runtime/agent_tools/handlers/outline_parser.py) | 提取 OutlineService：typed 输入、结构化章节、约束校验、大纲 ID 和版本；Markdown 是展示投影 | P0 |
| 报告 | [workflows/report/runtime.py](../../backend/src/app/chat/workflows/report/runtime.py)、[report_generation.py](../../backend/src/app/chat/agents/report_generation.py)、[GenerationTaskHandler](../../backend/src/app/services/generation_task_handlers.py) | 将追问、检索选择、改纲移入 report Skill；复用正文生成与任务服务；抽离旧 SkillManager/ctx 的依赖 | P0 |
| 教案 | [workflows/lesson_plan](../../backend/src/app/chat/workflows/lesson_plan/)、[DirectLessonPlanService](../../backend/src/app/services/direct_lesson_plan_service.py) | lesson-plan Skill 组织目标、学情、课时、评价；复用教案 engine，独立校验课时分配与活动结构 | P1 |
| 习题 | [workflows/quiz](../../backend/src/app/chat/workflows/quiz/)、[direct quiz service](../../backend/src/app/chat/application/knowledge_base_direct_quiz_service_v2.py) | quiz Skill 处理题量、题型、难度、知识点；保留 QuizGenerator，统一答案／解析和数量校验；不套报告确认规则 | P1 |
| 博客 | [blog_agent/engine.py](../../backend/src/app/blog_agent/engine.py)、[langgraph_workflow.py](../../backend/src/app/blog_agent/langgraph_workflow.py) | blog Skill 组织读者、语气、结构；保留内容 engine，内部确定性流水线可保留，避免再次承担外层总控 | P1 |
| 闪卡 | [direct flashcard service](../../backend/src/app/chat/application/knowledge_base_direct_flashcard_service_v2.py) | flashcard Skill＋现有生成服务；校验正反面、数量、来源 | P1 |
| 导图 | [direct graph service](../../backend/src/app/chat/application/knowledge_base_direct_graph_service_v2.py) | concept-map Skill＋结构生成／验证；与持久课程知识图谱建设区分 | P1 |
| 互动游戏 | [direct game service](../../backend/src/app/chat/application/knowledge_base_direct_game_service_v2.py)、[game_template_registry](../../backend/src/app/chat/application/game_template_registry.py) | game Skill 选择支持的模板和教学目标；服务继续管理模板、参数和产物约束 | P1 |
| AI 课堂生成 | [classroom handler](../../backend/src/app/chat/runtime/agent_tools/handlers/classroom.py)、[classroom_service](../../backend/src/app/services/classroom_service.py)、[OpenMAIC 集成](../../backend/src/app/integrations/openmaic/) | classroom Skill 组织场景要求和知识来源；工具提交课堂任务，保留 Stage/Scene/Action/Slide 主线 | P1 |
| PPTX／视频／字幕导出 | [classroom_video_export](../../backend/src/app/services/classroom_video_export.py)、[frontend/openmaic](../../frontend/src/openmaic/) | 从已存在的课堂版本导出；后台导出可包装任务工具，浏览器导出保留客户端流程，不假定都有后端 API | P2 |
| 课堂实时问答与资源问答 | [classroom_qa_service](../../backend/src/app/services/classroom_qa_service.py)、[resource_qa_service](../../backend/src/app/services/resource_qa_service.py) | 保留专用低延迟入口、可信资源上下文、打断与 TTS；可复用检索服务，暂不强制进入通用长任务循环 | 保留 |
| 修改已有资料 | [ReportEditRuntime](../../backend/src/app/chat/workflows/report/edit_runtime.py)、[edu-artifact-revision](../../backend/skills/edu-artifact-revision/SKILL.md) | revision Skill＋`read_artifact`／按类型修订／保存新版本；先报告，其他类型逐项确认支持，不能由 Skill 宣称全类型可改 | P0/P1 |
| 学习进度查询 | [handlers/learning.py](../../backend/src/app/chat/runtime/agent_tools/handlers/learning.py)、[resource_learning](../../backend/src/app/resource_learning/) | 保留个人／课程两种读工具与角色边界；事实来自业务库，不让模型改写完成记录 | P1 |
| 任务查询与取消 | [handlers/control.py](../../backend/src/app/chat/runtime/agent_tools/handlers/control.py)、[durable_job_runtime](../../backend/src/app/services/durable_job_runtime.py) | 查询、取消作为独立工具；明确 Agent turn、生成 job、学习任务 ID 各自类型和归属 | P0 |
| 质量验证 | [handlers/verification.py](../../backend/src/app/chat/runtime/agent_tools/handlers/verification.py)、[runtime/verification](../../backend/src/app/chat/runtime/verification/) | 提取与旧 plan/trace 解耦的产物验证服务；验证完成和验证通过分别表达 | P0 |
| 课程知识建设与增量更新 | [course_knowledge_builder](../../backend/src/app/services/course_knowledge_builder.py)、[planner](../../backend/src/app/services/course_knowledge_planner.py)、[incremental](../../backend/src/app/services/course_knowledge_graph_incremental.py) | 保留来源发现、教材映射、构建、质量门禁等后台服务；先暴露提交／查询，必要时再开放规划结果审阅，不把每个内部函数变成工具 | P2 |
| 文档解析与入库 | [knowledge_document_service](../../backend/src/app/services/knowledge_document_service.py)、[personal_knowledge_service](../../backend/src/app/services/personal_knowledge_service.py)、[knowledge_ingestion](../../backend/src/app/services/knowledge_ingestion/) | 保留解析、分块、索引任务；Agent 使用获授权的文档 ID，入库是明确写操作 | P1/P2 |
| 长期记忆与对话历史 | [memory](../../backend/src/app/chat/memory/) | 复用现有服务；任务状态单独存储；详见[记忆设计](deepseek-harness-memory-design-cn.md) | P0 |

身份、选课、教师审核、资料发布规则、学习事件采集是产品业务边界，不因接入 Agent 自动开放为工具。需要对话式操作时，再按实际产品权限提供窄接口。

## 5. 接入前必须解决的耦合与缺口

### 5.1 根 Skills 绑定旧状态机

现有 [edu-orchestrator](../../backend/skills/edu-orchestrator/SKILL.md) 与 [edu-agent-routing](../../backend/skills/edu-agent-routing/SKILL.md) 规定只要 awaiting 为真就覆写为 generate_content；用户显式取消、切换主题或另问问题不能简单照搬这一规则。现有 report Skill 的核心槽位 period/outcomes/issues/next_plan 偏向总结报告，不适用于全部报告。

[SkillManager](../../backend/src/app/chat/skill_manager.py) 按旧节点装配多个 Skill，截取 SYSTEM_PROMPT 或正文前 2200 字符。它不是 dsh 原生按需加载协议。应整理成根角色＋工作流 Skill＋参考模板，并审核截断、重复指令和缺失角色支持。

### 5.2 工具依赖旧运行时私有数据

[report handler](../../backend/src/app/chat/runtime/agent_tools/handlers/report.py) 的 `_collect_research_evidence` 从 `ctx._call_cache` 回收检索证据，图片也可从缓存恢复；其他资源 handler 复用这一逻辑。这样外部 MCP 调用无法只靠显式参数复现生成结果。

准备工作：把证据保存为有权限、有版本的 ResearchBundle，显式传 bundle_id；图片传 asset refs；工具适配器注入认证上下文。不要给 MCP 伪造一个巨大的旧 ctx 来维持隐藏依赖。

### 5.3 大纲只是字符串，确认缺少稳固绑定

当前 `draft_outline` 用 gateway 返回 Markdown；未知 resource_type 还会回落到 report 模板。应改为明确枚举和 typed 输出，对章节数量、主题与必填结构做校验。生成提交必须引用 task_id＋outline_id＋revision，由服务读取实际已确认内容。

不能接受模型自行传 `approved=true`；确认事件必须来自真实用户操作／消息，并由应用层关联目标版本。用户改纲后旧确认失效。前期审查已发现历史大纲被复用的问题，需以回归用例保护。

### 5.4 搜索、提取、入库和成功语义混在一起

`run_deepsearch_and_crawl` 同时搜索、可选正文提取、图片本地化、保存批次及可选入库，`save_to_kb` 默认 true；这说明服务有写入能力，并不等于所有聊天搜索都会入库。工具拆分后应显式选择只读或导入路径。

当前 web handler 未像 RAG handler 一样检查下游 `ok=False`，可能把失败映射成“联网检索完成，0 个来源”。统一错误契约，区分搜索为空、正文提取失败、摘要降级和入库失败；保留来源质量与降级说明。

### 5.5 提交成功、生成完成、验证通过必须区分

当前 `verify_task` 即使 verification decision 为 fail 也返回 `ok_result`；调用成功不等于任务合格。迁移后既要表达工具是否执行，也要表达产物是否通过。

完成规则由应用层执行：有可读产物、任务已完成、所需验证通过，才发布业务完成事件。大纲完成、任务入队、SDK turn 结束分别有自己的状态，不能一律转换为“报告生成完成”。

### 5.6 重试、并发与恢复不能继承旧隐患

[工具 executor](../../backend/src/app/chat/runtime/agent_tools/executor.py) 会缓存允许缓存工具的失败结果；同参重试可能只读回失败。查询与失败缓存策略、attempt 关联需要重做。生成服务的幂等能力值得保留，但进程锁不是多 worker 的唯一性保证，需核查数据库唯一键和提交对账。

旧 [background_runner](../../backend/src/app/chat/tasks/background_runner.py) 路径不能作为正式长任务恢复机制。报告生成继续交给 durable runtime，dsh 负责提交、解释进度和后续决策。断开 SSE 是否取消任务应有明确约定；建议已提交任务继续运行，显式取消通过业务服务执行。

### 5.7 前端协议也属于迁移范围

[chatV2.ts](../../frontend/src/services/teacher/chatV2.ts) 消费 metadata、status、delta、result、task_submitted、plan、plan_step_update、tool_call、tool_result、reflect、done、error。dsh 事件不能直接原样替换该协议。

增加事件适配器，保留现有卡片和任务引用；不要求 dsh 伪造旧 planner 的每个节点。面板应能处理“没有显式 plan 事件但有任务与工具进展”的情况。工具事件展示简洁摘要，隐藏凭据和内部配置。

## 6. 第一批稳定契约

这些契约先在 Python 服务层定义，再生成 MCP schema；名称是设计建议。

| 契约 | 关键内容 |
| --- | --- |
| RequestContext | 认证用户、角色、课程和知识点范围、允许的来源、request/session/task 引用；服务注入 |
| TaskContract | 用户目标、资源类型、约束、来源策略、审批策略、取消／暂停／恢复语义 |
| EvidenceBundle | bundle_id、来源 ID／URL、片段、获取方式、版本、质量／降级状态、访问范围 |
| Outline | outline_id、task_id、revision、resource_type、章节结构、约束摘要、来源 bundle 引用 |
| ToolResult | 调用状态、业务状态、data refs、error code、retryable、operation_id、耗时；不得含凭据 |
| GenerationSubmission | operation_id、任务／大纲／证据引用、资源参数；返回 job_id 与提交状态 |
| Artifact／Verification | artifact_id/version、类型、读取位置、验证对象版本、pass/fail、问题列表 |

建议统一结果区分 `ok`（调用是否成功）、`status`（submitted/running/completed/failed 等）和 `verification.decision`。具体枚举应按工具类型定义，不能用宽泛字典掩盖差异。

对大纲生成这类短工具使用有上限的同步执行；报告正文、课堂、知识建设、视频导出使用任务提交和后续查询。首期不必暴露分节写作工具，等确有局部重做、并行生成或人工介入需求时再拆。

## 7. 准备工作的实施顺序

| 阶段 | 交付 | 完成条件 |
| --- | --- | --- |
| P0-A：契约与根角色 | RequestContext、TaskContract、来源／产物引用；根角色与报告 Skill；当前工具权限表 | 无旧 ctx 私有字段依赖的报告路径设计明确；角色、来源范围不会由模型改变 |
| P0-B：报告能力抽取 | RAG/Web 适配、OutlineService、任务与审批存储、生成提交／查询、产物读取／验证 | 使用现有业务服务完成可追溯报告；空结果、改纲、失败和重试语义正确 |
| P0-C：Harness 接入适配 | 固定 SDK/profile、Python MCP、会话映射、记忆与事件适配 | 同步／流式结果一致，重启恢复、事件去重、用户隔离通过 |
| P1：其余生成与修订 | 教案、习题、博客、闪卡、导图、游戏、课堂各自 Skill 与 typed 参数 | 各类型独立约束验证；直接生成入口与 Agent 共用底层服务 |
| P2：高级后台能力 | 知识建设、导出、更多版本编辑 | 保留现有主线契约，分批接入可恢复任务 |
| 收口 | 按入口灰度切换与旧路由退役 | 不同时双跑有副作用的任务；保留可回滚入口，确认无调用后再删旧总控 |

不要求先把全部 P1/P2 重构完再验证 Harness。P0 做成完整纵向路径后即可验证，其他资源按相同契约接入。

## 8. 正式切换验收

- 中文题量、否定请求和任务切换正确；“不要报告”不能创建报告任务。
- 学生／教师工具权限及课程、个人资料权限由服务验证；所见工具目录与实际权限一致。
- 大纲可独立生成、读取和改版；确认绑定版本，不复用其他任务旧大纲。
- 网络失败不虚报成功；来源关闭或选择特定资料时不越界检索。
- 提交响应丢失、SSE 断流、进程重启后不重复生成；取消与查询返回真实业务状态。
- 验证失败不发布完成事件；重试成功后旧失败记录不覆盖当前有效结果。
- 每个产物关联 task_id、来源、工具调用、版本和验证；前端可继续、查看结果与报告错误。
- 记忆验收遵循[记忆设计](deepseek-harness-memory-design-cn.md)，不以单次 outline 实验代替。

此前问题复现及证据见 [Agent 架构审查](../reviews/2026-09-07-agent-architecture-review-cn.md)。它针对更早源码基线，本次重新核查了上述关键边界；旧报告的测试成绩不作为当前版本的全量通过证明。
