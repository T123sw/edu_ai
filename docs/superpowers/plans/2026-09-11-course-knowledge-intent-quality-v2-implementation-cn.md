# 课程知识库 Agent 需求理解与内容质量闭环 V2 实施计划

**目标：** 把教师自然语言要求变成可确认、可执行、可逐项验收的需求契约，并让来源质量、教学深度与交付物完整性成为发布硬门禁。  
**设计：** `docs/superpowers/specs/2026-09-11-course-knowledge-intent-quality-v2-design-cn.md`  
**验收：** `docs/acceptance/2026-09-11-course-knowledge-intent-quality-v2-acceptance-cn.md`

## 全局约束

- 正式抓取、索引和发布继续走持久化工作流；Agent 无发布权限。
- 新表和新接口必须支持 V1 历史 build 只读兼容。
- 任一任务开始前先写失败测试；完成后运行该任务聚焦回归。
- 任何硬要求未满足不得发布，教师修改约束必须产生新 revision。
- 不清理或覆盖现有课程、版本、资料和未提交工作区改动。

## 当前实施进度（2026-09-11）

核心纵向切片已落地：V2 intent schema 与确定性编译、提案持久化和审查、执行节点投影、来源域名查询与筛选、结构化教学产物、硬要求/来源偏好质量门禁、Agent 状态投影及教师确认卡。Agent 提案现在会接收合法挂载目标，并在模型返回非法目标或语义错误父章节时最多自修复三次；教师要求中的来源、受众、深度、范围、案例和练习数量会进入确定性执行与门禁，而不只停留在提示词中。

真实搜索与浏览器 E2E 后补充完成 domain-constrained provider 策略：指定官方域名拆成独立短查询并优先 Tavily advanced，站外结果由候选策略拒绝；同域但标题/路径与主题不相关的页面也会被拒绝。最终操作系统 cgroups 增量场景命中 Docker 官方全文 2 篇、Linux Kernel 官方全文 3 篇，生成并审查 1 个案例和 3 道带答案、解析及评分点的练习，质量 100 并发布；27 个旧节点全部保留，新增后为 28 个节点。正文审计发现的 Docker 历史版本索引页已加入非教学来源拒绝规则。Bocha rerank 404 仍需按 Task 3.3 正式修复或下线。

本切片采用现有版本化 `plan_snapshot` 兼容存储，尚未宣称完成独立 intent 表/迁移；结构化教学产物已完成 Markdown schema 校验和按 requirement 计数的最小实现，但独立产物表/证据片段仍待完成。全新操作系统课程曾以 59 分被正确阻断，修复常见标题别名、相邻叶节点教材映射、重试产物恢复和信号量事实约束后，在同一 build 上重试并以 100 分发布。首次 Agent SSE 响应仍出现过 BrokenPipe，但持久化草稿允许页面恢复继续；完整 SSE 自动重连尚未关闭，因此默认入口仍不得切换。

## Phase 0：冻结基线与评测集

### Task 0.1 建立真实问题基线

**产物：**

- [x] 固化 2026-09-11 操作系统真实 E2E 的 course/build/version/来源和覆盖证据；
- [ ] 为 SSE 未结束、重复草稿、查询连接重置建立独立缺陷编号；
- [ ] 记录 V1 质量报告为何能在缺练习、无官方来源时得到 100 分；
- [x] 确认历史 build 读取和版本化回滚合同。

### Task 0.2 建立教师需求离线评测集

**Files：**

- Create: `backend/src/tests/fixtures/course_knowledge_intents/*.json`
- Create: `backend/src/tests/evals/test_course_knowledge_intent_eval.py`

**覆盖：**

- [ ] 至少 60 条中文教师需求，覆盖新建、增量、模糊表达、否定、数量、课时、受众、深度、来源、时效、语言、案例、实验和练习；
- [ ] 至少 15 条冲突或歧义需求，期望返回澄清问题；
- [ ] 至少 10 条提示注入或不可信课程资料样例；
- [ ] 每条样例标注 hard/preference、结构化期望和允许误差。

## Phase 1：需求契约与 Intent Compiler

### Task 1.1 定义 schema 和迁移

**Files：**

- Create: `backend/src/app/services/course_knowledge_intent.py`
- Modify: `backend/src/app/database/models.py`
- Create: `backend/src/alembic/versions/*_knowledge_build_intent_v2.py`
- Modify: `backend/src/app/persistence/postgres_knowledge_repository.py`
- Test: `backend/src/tests/services/test_course_knowledge_intent.py`
- Test: `backend/src/tests/persistence/test_postgres_knowledge_repository.py`

- [x] 实现 `KnowledgeBuildIntent`、`Requirement`、`CourseProfile`、`DepthProfile`、`SourcePolicy` 和 `DeliverableSpec`；
- [ ] 保存原文片段、hardness、confidence、verification 和 revision；
- [ ] 建立 `(course_id, intent_revision)` 幂等和关联约束；
- [ ] baseline、资料快照和 intent revision 同时冻结；
- [ ] 历史 `plan_snapshot` 可投影为最低兼容 intent，但不得伪造字段。

### Task 1.2 实现需求提取、审查与澄清

**Files：**

- Create: `backend/src/app/services/course_knowledge_intent_compiler.py`
- Create: `backend/src/app/chat/harness/skills/edu-course-knowledge/references/intent.md`
- Test: `backend/src/tests/services/test_course_knowledge_intent_compiler.py`

- [ ] 第一次模型调用只负责 schema 提取；
- [x] 确定性解析“必须/仅/不得/至少/恰好/优先/尽量”等硬度；
- [x] 校验数量、课时、域名、互斥范围、增量保留和 AI 降级策略；
- [ ] 第二次独立模型对比原文，返回遗漏、擅增和硬度错误；
- [x] 关键歧义最多返回 3 个具体问题；
- [x] 增量新增节点必须通过主题与父章节语义一致性检查，并把建议 target 反馈给模型自修复；
- [ ] 连续两次不合法时稳定失败，不生成 fallback intent。

### Task 1.3 Agent 工具与状态投影

**Files：**

- Modify: `backend/src/app/chat/harness/knowledge_tools.py`
- Modify: `backend/src/app/chat/harness/skills/edu-course-knowledge/SKILL.md`
- Modify: `backend/src/app/chat/harness/runtime.py`
- Test: `backend/src/tests/chat/test_course_knowledge_agent_tools.py`

- [ ] 新增 analyze/revise/quality explain 工具；
- [ ] 每次调用重新校验 generate 权限；
- [ ] 修改必须携带 build ID 和 revision；
- [ ] SSE 重连复用已有 build，不重复创建草稿；
- [ ] 模型文本不能覆盖 needs_clarification、blocked 或 published 等事实状态。

## Phase 2：需求确认 UI

### Task 2.1 新建课程字段完整化

**Files：**

- Modify: `frontend/src/stitch/course/CourseCreateDialog.tsx`
- Modify: `frontend/src/stitch/course/courseCreation.ts`
- Modify: `backend/src/app/schemas/course.py`
- Test: corresponding frontend/backend tests

- [x] 增加结构化课时和前置知识，避免只藏在简介；
- [x] 保留教学对象、难度、语言和可观察目标；
- [x] placeholder 继续提供具体示例，但不写入真实值；
- [x] 课程快照完整传入 intent compiler。

### Task 2.2 需求确认步骤

**Files：**

- Create: `frontend/src/stitch/course/knowledge/CourseKnowledgeIntentReview.tsx`
- Modify: `frontend/src/stitch/course/knowledge/CourseKnowledgeBuildWizard.tsx`
- Modify: `frontend/src/stitch/api/types.ts`
- Test: component/integration tests

- [x] 展示原始输入、结构化字段、hard/preference、假设和澄清问题；
- [ ] 教师可以逐项修改，保存生成新 revision；
- [x] 未回答关键澄清问题不能进入图谱规划；
- [ ] 需求已确认后清晰显示后续每项验收方法。

## Phase 3：Research Plan 与高质量来源

### Task 3.1 来源权威注册表

**Files：**

- Create: `backend/src/app/services/source_authority_registry.py`
- Create: `backend/src/app/data/source_authority_registry.v1.json`
- Test: `backend/src/tests/services/test_source_authority_registry.py`

- [ ] 支持组织、域名、学科范围、tier、证据和版本；
- [ ] 首批覆盖计算机、数学、基础科学常用官方/大学/开放教材来源；
- [ ] 移除仅凭 `.org/.edu` 后缀判权威的逻辑；
- [ ] D 级聚合、下载和转载站默认拒绝；
- [ ] 教师指定来源覆盖通用排序，但不绕过安全检查。

### Task 3.2 查询规划器

**Files：**

- Create: `backend/src/app/services/course_knowledge_research_plan.py`
- Modify: `backend/src/app/services/course_knowledge_source_policy.py`
- Modify: `backend/src/app/services/course_knowledge_source_discovery.py`
- Test: source policy/discovery tests

- [x] 查询显式消费 audience、depth、deliverable、requested_materials 和 source policy；
- [x] required/preferred domains 生成 domain 限制查询；
- [ ] 概念、案例、实验、练习依据分别搜索；
- [x] 分层执行并在高质量来源满足时停止；
- [ ] 记录每条查询对应 requirement IDs 和退出原因。

### Task 3.3 搜索、rerank 与全文抽取

**Files：**

- Modify: `backend/src/app/services/deepsearch_service.py`
- Modify: `backend/src/app/integrations/websearch/*`
- Test: deepsearch integration tests

- [ ] 修复或替换当前 Bocha rerank 404；
- [ ] provider 接口支持 domains、raw content、search depth 和超时；
- [ ] full 抽取与 basic 摘要在数据模型和 UI 中严格区分；
- [ ] Tavily 失败降级必须产生 warning，关键事实不能用摘要冒充全文；
- [ ] 搜索和全文结果按 query/domain/content hash 缓存；
- [ ] 记录 provider 失败率与熔断状态。

### Task 3.4 候选来源质量评估

**Files：**

- Create: `backend/src/app/services/course_knowledge_source_evaluator.py`
- Modify: `backend/src/app/services/course_knowledge_plan_builder.py`
- Test: source evaluator/builder tests

- [x] 校验最终 URL、MIME、正文相关性、语言和重复内容；
- [x] 清除导航、广告、评论和提示注入；
- [ ] 保存 tier、相关 requirement、选择/拒绝理由和证据片段；
- [x] 默认不让已识别的低质量来源进入正式知识库；
- [x] 官方域名中的 release notes、changelog、历史版本归档等非教学导航页在抓取前拒绝；
- [x] preferred 来源不足时阻塞或进入教师决策，不静默继续。

## Phase 4：教学产物编译

### Task 4.1 产物 schema 与持久化

**Files：**

- Create: `backend/src/app/services/course_knowledge_artifacts.py`
- Modify: database models/repository/migration
- Test: artifact tests

- [x] 定义 concept、case、exercise_with_solution、lab、comparison、glossary；
- [ ] 每个产物引用 requirement、topic、source 和证据片段；
- [ ] 来源原文与 AI 整理产物分表或分类型保存；
- [ ] 保留生成模型、prompt、审查和版本信息。

### Task 4.2 按需求生成缺失产物

- [ ] 外部来源直接满足 schema 时可复用；
- [x] 外部来源只提供证据时生成教学化产物；
- [x] 精确满足数量，不以网页数量代替产物数量；
- [x] 练习必须有题目、答案、解析、评分点和目标难度；
- [x] 案例必须有步骤、输入、输出和验证；
- [x] AI 生成内容必须标记并经过结构审查。

## Phase 5：覆盖矩阵与质量门禁

### Task 5.1 Requirement Coverage Engine

**Files：**

- Create: `backend/src/app/services/course_knowledge_requirement_coverage.py`
- Test: coverage tests

- [ ] 生成 requirement → source/chunk → artifact → check 的完整关系；
- [x] 数量、域名和节点保留使用确定性验证；
- [ ] 概念覆盖、深度和证据蕴含使用独立审查并保存理由；
- [ ] 未证实、部分覆盖和通过严格区分；
- [ ] 修复只针对未通过 requirement。

### Task 5.2 多维质量报告

**Files：**

- Modify: `backend/src/app/services/course_knowledge_quality_gate.py`
- Modify: API schemas/types
- Test: quality gate tests

- [ ] 输出 intent、authority、grounding、correctness、pedagogy、coverage、integrity 七维；
- [x] 硬要求失败阻塞且综合分上限 59；
- [x] preferred 来源为 0 进入 needs_teacher_decision；
- [ ] D 来源、无全文关键证据、错误练习答案分别阻塞；
- [x] 只有当前已实现的全部硬门禁通过才能进入 ready_to_publish。

### Task 5.3 质量结果 UI

- [ ] 显示逐项覆盖矩阵和来源分布；
- [ ] 显示每个失败项的继续检索、修改要求或接受降级入口；
- [ ] 接受降级必须明确说明影响并生成新 revision；
- [ ] 不再单独用绿色“100 分”代表内容已完全合格。

## Phase 6：恢复、性能和观测

### Task 6.1 状态机与幂等

- [ ] intent、source feasibility、research、materialize、verify 分别 checkpoint；
- [ ] 同一 intent revision 只有一个活动 build；
- [ ] SSE 中断后恢复，不产生额外空草稿；
- [x] 同一 build 的模型与索引重试不会复用其他 build 的生成文档；
- [x] 质量阻断后复用同一 build、已审核来源和教学产物，只重做缺失或被拒绝项；
- [ ] baseline 变化后旧方案稳定标记 stale。

### Task 6.2 成本与性能

- [ ] 先权威后社区并设置满足即停，降低候选浪费；
- [ ] 缓存搜索、抽取和来源质量评估；
- [x] 已审核教学产物和同 build 来源可恢复，失败重试只补缺口；
- [x] 教材到单叶节点的持久化片段上限收敛为 4，减少重复向量化；
- [ ] 建立 P50/P95 规划和构建耗时、外部调用数、token 和落地率指标；
- [ ] 20 个叶节点真实构建 P95 目标由基线压测确定，不能用无依据常量。

### Task 6.3 审计与运营指标

- [ ] trace 可还原每条 requirement 的完整执行路径；
- [ ] 仪表盘显示硬要求遗漏率、来源降级率、A/B 来源占比、教师退回率和发布后删除率；
- [ ] 告警覆盖 rerank 失效、全文抽取降级、官方来源命中为 0 和异常满分；
- [ ] 日志和证据不包含密钥或完整私有教材。

## Phase 7：测试、迁移和上线

### Task 7.1 自动化测试

- [ ] intent 单元/评测集全部通过；
- [x] source policy、正文相关性、产物和质量门禁聚焦测试全部通过；
- [ ] PostgreSQL 迁移、并发、幂等和回滚测试通过；
- [x] 本模块后端核心回归 156 项通过（1 项共享数据库夹具用例取消选择）；
- [x] 本模块前端交互测试 51 项、生产构建和真实浏览器新建+增量 E2E 通过；
- [ ] 全仓回归无本功能新增失败。

### Task 7.2 真实端到端

- [x] 使用操作系统课程实际执行新建与 cgroups 增量场景；新建先被 59 分门禁阻断，修复后同 build 重试发布，增量随后发布；
- [x] 保存需求确认、来源策略、构建阶段、质量结果和发布结果截图及 JSON；
- [x] 对增量场景的官方来源、案例和练习逐项核验；
- [x] 核验增量 `textbook_units=0`，确认未把 OSTEP/xv6 错挂到 cgroups；
- [ ] 使用严格 required-domain 场景验证找不到时阻塞；
- [ ] 使用偏好场景验证降级前需要教师决定；
- [ ] 使用学生和只读教师验证权限。

### Task 7.3 渐进上线

- [ ] Shadow 模式至少覆盖代表性课程且不影响 V1 发布；
- [ ] 指标达到验收阈值后开放教师试用；
- [ ] 保留 feature flag、V1 历史恢复和回滚方案；
- [ ] 默认切换 V2 后关闭 V1 新入口；
- [ ] 更新项目地图、运维手册和验收索引。
