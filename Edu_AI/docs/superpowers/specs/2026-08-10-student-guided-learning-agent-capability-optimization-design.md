# 学生端引导式教学 Agent 与真实能力优化 SPEC

> 日期：2026-08-10
> 状态：已设计，待实施
> 现状证据：`docs/acceptance/2026-08-10-student-capability-real-e2e.md`
> 教师 Agent 基线：`docs/superpowers/specs/2026-08-09-stable-teaching-agent-optimization-design.md`
> 学生工作区基线：`docs/superpowers/specs/2026-08-09-student-workspace-and-permission-architecture-design.md`
> 执行计划：`docs/superpowers/plans/2026-08-10-student-guided-learning-agent-capability-optimization.md`
> 验收规范：`docs/acceptance/2026-08-10-student-guided-learning-agent-capability-optimization-acceptance.md`

## 0. 决策摘要

本阶段目标不是建设第二套学生 Agent，而是把教师端已经验证的稳定 Agent 内核完整复用于学生端，并完成学生角色、知识范围、权限和真实能力闭环。

```text
认证角色 + 当前课程 + UI 来源选择
                ↓
共享请求规范化 / TeachingTaskContract
                ↓
共享计划编译 / ReAct / 工具 / ResearchBundle / Verification
                ↓
共享 Job、资源生成器、材料存储和状态恢复
                ↓
按认证角色选择 PersonaPolicy 与允许工具目录
        ├─ teacher：备课任务助手
        └─ student：引导式教学助手
```

教师端和学生端的差异只允许出现在：

- 对话目标、语气和引导方式；
- 角色允许使用的资源工具；
- 可读取的知识范围；
- 是否具备课程写入和发布权限；
- 页面上是否展示课程管理操作。

两端不得分别维护 Planner、Executor、RAG、Web、深度研究、资源生成器、Job 协议或材料渲染器。

## 1. 现状审计

### 1.1 教师端已有能力，必须优先复用

| 能力 | 已有实现 | 学生端策略 |
| --- | --- | --- |
| 请求与来源规范化 | `api/src/app/chat/application/request_normalizer.py` | 复用；补充服务端认证角色和显式知识范围 |
| 任务契约 | `TeachingTaskContract` v2 | 复用；`actor_role` 从认证身份注入，不接受客户端伪造 |
| 计划与有界 ReAct | plan compiler、阶段 allowlist、预算和终止条件 | 原样复用，不建立 StudentPlanner |
| Agent 执行 | `ReActAgent`、工具执行器、反思与恢复 | 原样复用 |
| 研究证据 | `ResearchBundle`、RAG/Web/图片检索 | 复用；修复个人/课程范围过滤 |
| 运行状态 | SQLite Agent run、幂等键、Job/result_ref 读回 | 原样复用 |
| 资源生成 | 报告、PPT、思维导图、习题、AI课堂、闪卡、小游戏等现有生成器 | 不重写；按角色目录过滤并回归 |
| 生成工厂 | 教师端稳定生成流程及共享目录 | 复用同一流程容器 |
| AI 问答页面 | 教师三栏工作区 | 学生端当前已直接复用，继续共享业务组件 |
| 课程知识/资源/课堂 | 教师端页面和共享播放器、预览器 | 复用读取能力，按学生身份隐藏/拒绝写操作 |

### 1.2 当前学生端关键缺口

真实端到端测试确认：

- 个人知识文档索引失败，且具体异常被 durable executor 覆盖；
- `PersonalKnowledgeService.create_document()` 为个人文档写入了不正确的 `scope_type="course"`；
- 深度研究仍写入旧 `/api/rag/documents` 存储，未进入新个人知识库；
- 旧深度研究文档缺少 `library_type/scope_type/course_id`，污染课程 RAG；
- Fast Chat 固定使用 `TEACHER_PERSONA`；
- ReAct 系统提示固定使用教师 Persona；
- `TeachingTaskContract.actor_role` 没有从认证身份传入，实际默认 `teacher`；
- 学生角色策略虽已定义，但没有进入真实请求链路，也没有独立测试；
- RAG 开关和发送存在状态竞争；
- Agent 已完成时计划面板仍可能保持运行中；
- `StudentShell` 存在重复更新；
- 课程知识标签仍展示含义不清的上传按钮。

### 1.3 本阶段必须避免的做法

- 不复制 `ReActAgent`、Planner、Executor 或工具 handler；
- 不新建学生专用聊天 API；
- 不复制教师端资源生成器；
- 不通过前端传入 `actor_role=student` 作为可信权限依据；
- 不用提示词替代服务端知识范围和权限过滤；
- 不继续把深度研究写入无 scope 的旧文档目录；
- 不以 Mock E2E、工具名称出现或 Job 已提交作为真实能力通过；
- 不在本阶段增加错题本、学习计划、掌握度等新功能。

## 2. 阶段目标与非目标

### 2.1 阶段目标

1. 个人资料能够真实完成上传、解析、索引、检索、重试和删除。
2. 深度研究真实完成搜索、抽取、来源质量判断，并只归档到发起人的个人知识库。
3. 课程、个人和显式组合 RAG 的文档范围完全正确，引用可解释、可去重。
4. 学生 Fast Chat 和 Agent Chat 都使用“引导式教学助手”角色；教师端继续使用备课助手角色。
5. 学生 Agent 复用教师端稳定编排，能够完成普通问答、RAG、Web、组合检索、状态、取消和允许的资源生成任务。
6. 学生端页面中的能力开关、任务进度、研究进度和完成状态与后端事实一致。
7. 现有资源生成能力只做必要接入修复和真实回归，不重写已经完成的生成器。
8. 建立版本化学生 Agent 评测集、重复实验、双 Provider 和真实浏览器 E2E。

### 2.2 非目标

- 新增资源类型；
- 重做资源配置表、渲染器或导出器；
- 建设开放式自治 Agent、多 Agent 或代码执行 Agent；
- 自动批改、考试监考或学术诚信判定系统；
- 长期学习画像、错题本、掌握度、学习计划和教师端学生分析；
- 改变“所有用户产物默认属于个人”的数据规则；
- 允许学生向课程知识库或课程共享区发布内容。

## 3. 产品定位：引导式教学助手

### 3.1 核心职责

学生 Agent 的目标是帮助学生理解、练习和完成明确的学习任务。它不是教师备课助手，也不是只会反问的苏格拉底机器人。

它应当：

- 先判断学生是在询问知识、解决问题、检查理解，还是要求执行资源任务；
- 对概念学习给出清晰解释、例子和一个关键理解检查点；
- 对有求解过程的问题优先提供可前进的一层提示，再根据学生反馈加深提示或给完整解法；
- 学生明确要求完整答案、总结或资源生成时直接完成，不用无意义反问阻塞任务；
- 发现学生误解时先指出具体冲突，再给纠正线索；
- 使用 RAG/Web 时明确知识来自课程、个人资料或网络；证据不足时说明边界；
- 每个知识点最多设置一个理解检查，不在每句话结尾反问；
- 不伪造学习进度、知识库证据或工具执行结果。

### 3.2 与教师 Persona 的差异

| 维度 | 教师端 | 学生端 |
| --- | --- | --- |
| 主要目标 | 完成备课和教学资源任务 | 引导理解并完成学习任务 |
| 普通问答 | 直接给教学可用结论、重点和易错点 | 解释 + 示例 + 必要时一个理解检查 |
| 解题 | 面向教师给方法和讲解建议 | 先给可执行提示，按反馈渐进到完整解法 |
| 追问 | 仅高影响缺失参数追问一次 | 学习关键点或高影响缺失参数追问一次 |
| 资源生成 | 行动导向，按教师目录执行 | 行动导向，按学生目录执行；不强制进入引导对话 |
| 语气 | 简洁、专业、备课导向 | 清楚、鼓励、不过度幼化 |
| 权限 | 可按课程角色发布课程内容 | 只能生成和管理个人内容 |

### 3.3 学生交互模式

这是同一 Agent 的响应策略，不是新的 Agent 或新的计划器。

| 模式 | 适用场景 | 响应要求 |
| --- | --- | --- |
| `explain` | 概念、区别、原理 | 先给结论，再解释和示例；必要时一个检查点 |
| `coach` | 数学、算法、推理、代码问题 | 给一层有效提示；根据学生尝试升级提示；明确要求时给完整解法 |
| `check` | “考考我”“我理解得对吗” | 提出一项问题或检查具体回答，给针对性反馈 |
| `task` | 检索、总结、生成闪卡/报告/小游戏等 | 直接复用教师 Agent 工作流完成任务，不用教学式反问阻塞 |

模式只影响对话组织和最终表达，不得改变计划事实、工具顺序、权限或来源范围。

### 3.4 提示梯度

`coach` 模式使用最多三级提示：

1. 指出应关注的概念、条件或第一步；
2. 给局部示例、公式结构或伪代码骨架；
3. 给完整解法并解释关键转折。

默认从第一级开始；学生已尝试失败、明确说“直接告诉我”或题目本身是知识查询时，可以直接进入更深级别。提示等级属于对话状态，不触发新工具或新计划。

## 4. 复用优先的架构规则

### 4.1 Teacher-first 检查门禁

每个实施任务开始前必须完成：

1. 搜索教师端页面、服务、接口、测试和验收记录；
2. 在变更说明中列出“直接复用、抽到 shared、仅做角色适配、确实缺失”四类结论；
3. 优先补共享参数或策略注入，不复制整文件；
4. 如果准备创建 `student_*` 后端服务，必须证明教师端或 shared 中没有可复用实现；
5. 运行教师端目标回归，证明共享修改没有破坏教师角色。

每个任务的完成证据必须包含一项“教师端复用审计”，否则不得进入实现完成状态。

### 4.2 允许独立维护与必须共享的边界

允许学生端独立：

- 一级导航、学生首页、只读操作呈现；
- 学生文案、Persona 视觉提示；
- 学生允许工具的目录呈现；
- 页面级空状态和权限提示。

必须共享：

- AI 三栏工作区与聊天状态容器；
- SourcePanel/ChatPanel/StudioPanel 的业务逻辑；
- 认证、课程上下文和 API 客户端；
- 请求规范化、任务契约和计划编译；
- ReAct、RAG、Web、图片、深度研究服务；
- Job、幂等、状态恢复和任务中心；
- 全部资源生成器；
- 文档/资源/AI课堂预览与导出。

共享组件通过 `role/capabilities/readOnly` 等明确属性适配，不能读取路由名称猜测权限。

## 5. 角色与请求契约

### 5.1 认证角色是唯一事实来源

聊天 HTTP 层在 `_with_owner` 或等价的认证上下文组装阶段写入：

```text
owner_user_id
system_role: teacher | student
```

随后：

- `ChatRequestV2.actor_role` 由 `system_role` 派生；
- `TeachingTaskContract.actor_role` 从 request 复制；
- Fast Chat 使用 `persona_for(request.actor_role)`；
- ReAct 的 system content 使用同一 `persona_for()`；
- 资源工具目录使用认证角色过滤；
- Trace 记录角色但不记录令牌。

客户端即使提交 `actor_role=teacher` 也必须被忽略或拒绝。

### 5.2 单一 Persona 注入点

目标接口：

```text
PersonaPolicy
- actor_role
- goal
- default_style
- clarification_budget
- socratic_mode
- hint_before_full_answer
- reflection_question_budget_per_topic
- render_fast_instruction(mode, hint_level)
- render_agent_instruction(mode, hint_level)
- audit(response, context)
```

Fast 和 Agent 可以有不同的执行提示补充，但角色基础指令必须由同一策略生成，不能继续维护 `BASE_TEACHER_SYSTEM_PROMPT` 与固定教师 `AGENT_SYSTEM_PROMPT` 两个硬编码角色事实。

### 5.3 教师行为不得漂移

角色接入后，教师端仍必须满足：

- 普通问答不把教师当学生；
- 教师明确资源任务不出现学生式提示梯度；
- 教师材料包、确认、状态、取消和资源生成工具轨迹不变；
- 教师 Persona 评测和现有真实 Agent 基线不下降。

## 6. 个人知识库数据平面

### 6.1 唯一数据模型

个人文档必须统一满足：

```text
library_type = personal
scope_type = personal
scope_id = personal:<owner_user_id>
owner_user_id = authenticated user
course_id = null
course_context_id = optional, provenance only
```

`course_context_id` 只记录上传或研究发生时的课程上下文，不能参与所有权或课程检索判断。

### 6.2 索引状态机

```text
received → queued → parsing → indexing → ready
                                  └→ failed
ready → reindexing → ready | partially_ready
```

要求：

- Job 和文档状态使用同一业务结果收口；
- 索引层已经写入具体失败时，durable executor 不得用通用错误覆盖；
- `failed` 必须保存稳定错误码、用户可理解信息和内部 trace 引用；
- 重试从明确的失败状态创建新 attempt，不产生第二个文档；
- `ready` 必须有可解析的 index key、`chunk_count > 0` 和可执行检索；
- 删除个人文档同时删除个人索引，但不得触碰课程副本。

### 6.3 存量无范围文档

修复上线前执行只读审计：

- `library_type/scope_type/course_id` 全为空的旧文档；
- 深度研究产生、owner 明确但 scope 缺失的文档；
- 课程索引中错误标记为个人的文档。

迁移必须 dry-run，输出文档 ID、推断依据和目标范围。不能可靠判断范围的记录默认隔离为不可检索，禁止自动放入课程范围。

## 7. 深度研究闭环

### 7.1 后端行为

复用现有 Bocha/Tavily 搜索、抽取、图片本地化和降级能力；替换旧 RAG 直写归档路径：

```text
搜索与抽取
→ 形成结构化 ResearchResult
→ 为每个成功来源创建当前用户个人知识文档
→ 复用 PersonalKnowledgeService 的索引提交
→ 返回 personal_document_ids + job_ids + 来源质量摘要
```

深度研究不能接受客户端指定 owner。学生和教师的研究结果都只进入各自个人知识库。

### 7.2 来源质量

研究请求可以包含：

```text
min_sources
preferred_domains[]
official_sources_required
freshness_requirement
```

完成判定区分：

- `succeeded`：达到关键来源约束并完成个人索引；
- `partial`：存在可用来源，但数量、官方性或抽取成功率未达要求；
- `failed`：没有可用来源或全部归档失败。

提供商降级、rerank 失败和抽取失败必须进入结果摘要，不能只打印后端日志。

### 7.3 页面状态

共享 SourcePanel 展示：搜索、抽取、个人归档、索引四个阶段；完成后保留来源、失败项、个人文档状态和“查看个人知识库”。关闭已完成弹窗不得提示取消。

## 8. RAG 范围与引用

### 8.1 显式检索范围

RAG 请求不得只依赖 `allow_rag` 推断范围。目标契约：

```text
source_mode: none | course_auto | personal_auto | selected_documents
selected_doc_ids[]
```

过滤规则：

- `course_auto`：只检索 `library_type=course` 且 `course_id=current_course_id`；
- `personal_auto`：只检索 `library_type=personal` 且 `owner_user_id=current_user`；
- `selected_documents`：每个 ID 分别校验当前用户可访问域，允许显式组合当前课程文档和本人个人文档；
- `none`：不调用 RAG；
- 空 scope、未知 scope 和无法授权的文档：fail closed，不参与检索。

### 8.2 回答与引用门禁

- 课程模式不得引用个人资料；
- 个人模式不得引用课程资料，除非用户显式组合选择；
- 引用按稳定文档 ID/URL 去重；
- 低于相关性门槛的证据不展示；
- 强制 RAG 无合格证据时，明确返回资料不足，不能用常识伪装成知识库答案；
- 引用卡明确标注“课程知识”“个人知识”或“网络来源”。

## 9. Agent 执行与资源生成

### 9.1 共享执行内核

学生端继续使用教师端已经验收的：

- 意图规则与 `TeachingTaskContract`；
- 固定计划模板；
- 阶段工具白名单；
- required tool choice；
- 有界重试与重规划；
- ResearchBundle；
- VerificationReport；
- SQLite Agent run 和三层记忆；
- 确定性幂等键；
- Job/result_ref/材料可读性终态。

不得因学生 Persona 改变工具事实或降低自检门槛。

### 9.2 学生工具目录

本阶段沿用已通过的目录：

- 报告；
- PPT；
- 思维导图；
- 习题；
- AI课堂；
- 闪卡；
- 课堂小游戏。

学生不得使用教案、教学博客。所有生成物为 `visibility=private`，学生没有发布工具。教师与学生目录差异由现有服务端工具注册表处理，前端只呈现服务端结果。

这里的“工具目录”包含生成工厂入口，不代表要为学生单独扩展 Agent 工具。某一资源如果教师共享 Agent 当前尚未支持对话调用（例如当前阶段的 PPT），学生仍可从生成工厂使用，但学生 Agent 不得建立独立实现；后续只能在教师/学生共享 Agent 内核中统一补齐。

### 9.3 资源任务与引导语气的边界

当意图为 `generate_single/prepare_bundle/status/cancel/confirm/modify` 时，优先完成任务，不强行使用提示梯度。学生说“生成 10 张链表闪卡”时，应直接进入共享生成计划，而不是先问“你知道链表是什么吗”。

## 10. 前端状态与权限呈现

### 10.1 复用方式

AI 问答、课程详情、课程知识、AI课堂和资源管理继续复用教师端现有页面/组件。角色差异通过共享权限模型控制，不再另写不完整的学生版功能。

### 10.2 本阶段必须修复

- `StudentShell` 的课程同步 effect 不得因对象引用变化形成无限更新；
- RAG 能力选择和消息提交必须原子化，点击后立即发送也能携带正确 capability；
- SSE `result/done/error` 必须同时收口消息、计划、工具和任务状态；
- 深度研究完成态和个人知识库刷新与后端事实一致；
- 课程知识标签下隐藏个人上传入口；个人上传只出现在个人知识标签；
- 学生只读课程页面不得渲染上传、删除、重建、发布等课程写操作；
- 教师端相同组件仍保留已有管理能力。

## 11. Agent 智能评测

### 11.1 版本化数据集

建立 `student-agent-2026-08-10.v1`，至少 60 个用例：

| 类别 | 最少用例数 |
| --- | ---: |
| 概念解释与类比 | 10 |
| 分步解题与提示梯度 | 10 |
| 学生误解诊断 | 8 |
| 明确要求完整答案 | 6 |
| 课程/个人/组合 RAG | 10 |
| Web 与证据不足 | 6 |
| 资源生成与控制意图 | 6 |
| 权限、越权和注入对抗 | 4 |

每个用例记录：输入、历史、认证角色、课程、来源选择、期望模式、必需/禁止工具、Persona 规则、引用范围和结构化评分。

### 11.2 智能门槛

| 指标 | 门槛 |
| --- | ---: |
| 学生 Persona 合规率 | ≥ 95% |
| 应提示场景的有效提示率 | ≥ 95% |
| 明确要求完整答案时直接满足率 | ≥ 95% |
| 每知识点多余反问率 | ≤ 5% |
| 清晰资源任务无谓追问率 | ≤ 5% |
| 必需工具召回率 | 100% |
| 禁止工具调用率 | 0% |
| 知识范围正确率 | 100% |
| 引用访问域标注正确率 | 100% |
| 执行事实与最终陈述一致率 | 100% |
| 30 轮任务/提示等级绑定正确率 | 100% |
| 同一用例五次运行合规率 | ≥ 98% |
| 双 Provider 核心用例通过率 | ≥ 95% |

Persona 评分不能只搜索关键词。规则先检查反问数量、是否给出有效信息、是否错误阻塞明确任务、是否泄露教师语气，再由 LLM Judge 和人工抽检评价教学质量。

## 12. 可观察性与错误契约

统一 trace 增加：

```text
actor_role
interaction_mode
hint_level
knowledge_scope
authorized_document_ids
retrieved_document_scopes
persona_policy_version
persona_audit
```

禁止记录完整个人文档、令牌和隐藏推理。错误对学生显示可行动信息，对开发日志保留 trace ID 和原始分类。

## 13. 发布与迁移策略

建议使用开关分段启用：

```text
STUDENT_PERSONA_ENABLED
STRICT_KNOWLEDGE_SCOPE_ENABLED
DEEPSEARCH_PERSONAL_ARCHIVE_ENABLED
```

顺序：

1. 先修索引错误和范围元数据；
2. dry-run 审计旧文档；
3. 开启严格知识范围；
4. 切换深度研究个人归档；
5. 接通学生 Persona；
6. 完成真实 E2E 后移除临时兼容路径。

任何开关回退都不能放宽权限。严格范围关闭时，未知 scope 文档也不得进入课程检索。

## 14. 完成定义

本阶段只有同时满足以下条件才算完成：

- 教师端复用审计覆盖每个实施任务，没有新增重复 Agent 或生成器；
- 个人知识上传、索引、重试、检索、删除真实可用；
- 深度研究结果只进入发起人的个人知识库，并展示来源质量和索引状态；
- 课程、个人和显式组合 RAG 的范围与引用完全正确；
- 学生 Fast 与 Agent 两条路径均使用引导式教学 Persona；
- 教师 Fast 与 Agent 保持备课助手 Persona；
- 学生 Agent 能完成问答、RAG、Web、组合检索、状态、取消和允许的资源任务；
- 学生工具目录和资源私有性保持正确；
- 前端不存在能力开关竞争、假运行状态或重复更新；
- 60+ 用例版本化评测、五次重复、双 Provider 和 30 轮对话达到门槛；
- 真实前后端浏览器 E2E 验证实际引用、Job、材料、可见性和失败恢复；
- 教师端 Agent、课程知识、资源生成和页面主流程全部回归通过；
- 验收文档填写真实任务 ID、材料 ID、耗时、来源和失败项，不用模拟结果代替。
