# 课程知识库 Agent 需求理解与内容质量闭环 V2 设计

**日期：** 2026-09-11  
**状态：** 核心纵向切片已实施；新建与增量真实 E2E 均通过，完整 V2 上线门槛仍未全部满足  
**范围：** 新建课程知识库与增量补充的需求理解、课程规划、来源发现、内容生产、质量验收、失败恢复和教师审核。  
**基线：** 延续 V1“Agent 负责理解与推进，确定性工作流负责副作用，教师负责最终确认”的混合架构。

## 1. 决策摘要

V2 不把整个知识库构建改成由 Agent 自由调用工具的全 Agent 流程。正式抓取、写文件、建索引和发布仍由持久化工作流执行，但 Agent 不再只生成一份目录 JSON，而是生成并维护一份可验证的 `KnowledgeBuildIntent`。

每条教师要求都必须经历：

```text
教师原话
  → 需求结构化与歧义识别
  → 教师需求契约
  → 课程图谱与来源研究计划
  → 全文获取和教学材料生产
  → 需求逐项覆盖矩阵
  → 多维质量门禁
  → 教师确认或阻塞
  → 原子发布
```

核心变化：

1. 来源、受众、深度、课时、范围、案例、练习和排除项成为结构化字段，不再只是 prompt 文本；
2. 每条要求分配稳定 `requirement_id`，检索词、来源、材料和质量结论都反向引用该 ID；
3. 检索必须使用来源约束和教学要求，先找指定/权威来源，再按教师允许的范围降级；
4. “需要 3 道带解析练习”由系统生成或验证专门的练习产物，不能期待普通网页碰巧包含；
5. 质量分改成多维报告；任何硬要求未满足都不能得到 100 分或自动发布；
6. 偏好无法满足时必须明确展示差距，由教师选择继续检索、允许降级或修改要求。

## 2. V1 实测暴露的问题

2026-09-11 操作系统真实 E2E 证明主流程能够发布，但暴露了质量闭环缺口：

- 教师要求优先 Linux Kernel 和 Docker 官方资料，方案能够复述，最终 4 份增量资料却全部来自掘金、CSDN 和简书；
- 教师要求 3 道带解析练习，最终材料中没有明确练习题和答案结构；
- 构建仍得到 100 分，因为质量门禁只验证结构、数量、非 AI 覆盖、来源字段、索引和原子发布；
- 增量规划读取到的已有文档快照缺少标题与摘要，模型无法可靠判断已有覆盖；
- 搜索查询没有消费 `requested_materials`，也没有消费指定域名、来源层级和练习数量；
- 当前权威性判断主要依赖域名后缀并且权重较低，HTTPS 且有少量语义重合的社区页面即可入选；
- Bocha rerank 当前不可用时会回退原排序，进一步放大低质量首条结果。

V2 的目标不是让模型“更会说”，而是让需求在每个执行阶段都有机器可验证的落点。

截至 2026-09-11，本设计的核心纵向切片已经进入实现：结构化 intent、Agent 提案自修复、来源域名约束、结构化教学产物、硬质量门禁、教师需求确认和版本化发布均已有代码与测试。最终真实《操作系统》回归中，新建课程 build `kb-b6dbacce7ef6462a971a4b752b3619b8` 与修正后的 cgroups 增量 build `kb-8cc2c8640cfd4a28b31fee3782c5eb82` 均以全部已实现门禁通过后发布；27 个基线节点全部保留并新增 1 个节点。完整离线评测、七维报告、证据片段、权限矩阵和 SSE 断流恢复仍未完成，因此仍属于教师试用/继续优化阶段，不能视为全面上线完成。

### 2.1 真实失败驱动的最终修正

最终验收没有跳过失败样本。全新课程首次运行以 59 分被阻断，暴露出三个确定问题：常见中英知识点标题未映射、已审核教学产物在重试时未完整复用，以及信号量材料包含错误头文件和过强的顺序性结论。修正后在同一 build 上重试，12 个叶节点均达到覆盖要求，12 份教学产物独立审查分为 88～100，随后才发布 v1。

增量审计又发现两类语义问题：旧逻辑会因知识点目标里的宽泛词把 OSTEP/xv6 误映射到 cgroups；模型还曾因 cgroups 包含内存限制而把它挂到“虚拟内存”。最终规则只以叶节点标题及受控双语别名作强匹配，每本教材每个叶节点最多保留 4 个高相关片段，并用确定性主题族规则复核新增主题与父章节的语义一致性。最终路径为“操作系统 → 进程与线程 → Linux cgroups 与容器资源隔离”，覆盖为 `textbook_units=0`、Docker 官方全文 2 份、Linux Kernel 官方全文 3 份、经审查 AI 教学材料 1 份。另将 release notes、prior releases、changelog 和版本归档页定义为非教学证据，防止官方域名中的导航页抬高质量分。

## 3. 设计原则

### 3.1 Agent 是语义控制平面

Agent 负责：理解需求、识别歧义、生成课程方案、解释取舍、提出修订和恢复建议。

Agent 不负责：绕过确认、任意下载、直接写知识库、直接建索引、直接发布或自行降低硬约束。

### 3.2 确定性工作流是执行平面

持久化工作流接收已确认的需求契约和图谱，按固定状态机执行检索、抓取、材料生产、验证与发布。所有副作用具备 revision、checkpoint、幂等和审计记录。

### 3.3 先形成验收合同，再开始搜索

教师输入自然语言后，系统先展示“我理解的是”：对象、目标、深度、范围、来源、产物数量、保留项、禁止项和假设。影响结果的歧义必须询问；无关键歧义时允许教师一键确认。

### 3.4 硬要求与偏好分开

- “必须、只允许、不得、至少、恰好”默认是硬约束；
- “优先、尽量、建议”默认是偏好；
- 偏好未满足时不能静默忽略，必须显示差距和实际降级原因；
- 硬约束未满足时构建进入 `blocked_quality`，不得发布；
- 教师可以通过新 revision 将硬约束改为偏好，但系统不能自行修改。

### 3.5 来源文档与教学产物分层

外部网页、教材和教师文件是 `evidence_source`；基于证据整理出的讲义、案例、练习、答案和术语表是 `learning_artifact`。两者分别统计、分别展示，不能把“找到 4 篇网页”等同于“交付 3 道带解析练习”。

## 4. 教师需求契约

新增版本化对象 `KnowledgeBuildIntent`：

```json
{
  "intent_id": "kbi-...",
  "revision": 3,
  "mode": "create|supplement",
  "course_profile": {
    "audience": "计算机专业大二学生",
    "prerequisites": ["C 语言", "数据结构"],
    "language": "zh-CN",
    "difficulty": "intermediate",
    "duration_minutes": 480,
    "learning_outcomes": ["..."]
  },
  "scope": {
    "include_topics": ["Linux cgroups 与容器资源隔离"],
    "exclude_topics": [],
    "preserve_existing_graph": true,
    "preserve_existing_documents": true
  },
  "depth_profile": {
    "target_bloom_levels": ["understand", "apply", "analyze"],
    "conceptual_rigor": "本科基础",
    "example_complexity": "可运行的 Docker 配置",
    "math_or_code_expectation": "命令、参数解释和验证步骤"
  },
  "source_policy": {
    "preferred_organizations": ["Linux Kernel", "Docker"],
    "preferred_domains": ["kernel.org", "docs.docker.com"],
    "required_domains": [],
    "minimum_authoritative_sources_per_topic": 1,
    "allow_community_fallback": true,
    "allowed_languages": ["zh-CN", "en"],
    "freshness": null
  },
  "deliverables": [
    {"id": "req-content", "type": "concept_explanation", "count": 3, "hardness": "hard"},
    {"id": "req-case", "type": "worked_case", "count": 1, "hardness": "hard"},
    {"id": "req-exercises", "type": "exercise_with_solution", "count": 3, "hardness": "hard"}
  ],
  "assumptions": [],
  "clarification_questions": [],
  "original_text": "教师原始输入"
}
```

每个字段保存：原文片段、规范化值、硬度、提取置信度、验证方法和最后修改者。教师修改结构化字段时生成新 revision，不能覆盖旧版。

### 4.1 需求提取

使用“模型提取 + 确定性校验 + 独立审查”三层：

1. 模型把自然语言转为 schema；
2. 确定性校验数量、枚举、冲突、域名格式、增量保留要求和课时范围；
3. 独立审查对比原文与 schema，检查是否遗漏、擅自增加或错误软化硬约束；
4. 检测到关键歧义时返回最多 3 个聚焦问题，不生成虚假确定方案；
5. 教师确认后冻结 `intent_revision`，后续图谱、搜索和质量报告必须绑定该 revision。

### 4.2 深度定义

“深度”不能只用入门/进阶/高阶标签。每个知识点必须包含：

- 可观察学习目标；
- Bloom 目标层级；
- 前置知识；
- 必须讲清的概念、机制和边界；
- 案例或实践复杂度；
- 评价方式及通过标准；
- 与总课时的预算关系。

三档方案应比较时间、深度、应用和舍弃项，而不仅是节点数量。

## 5. V2 状态机

```text
draft_intent
  ├─ needs_clarification
  └─ intent_review
       → source_feasibility
       → proposal_review
       → graph_review
       → confirmed
       → researching
       → materializing
       → verifying
          ├─ blocked_quality
          ├─ needs_teacher_decision
          └─ ready_to_publish
               → publishing
               → published
```

关键约束：

- `source_feasibility` 只进行有上限的搜索和元数据预检，不写正式知识库；
- `confirmed` 前不得全文抓取、生成正式教学产物、建立正式索引或发布；
- `verifying` 输出逐项覆盖矩阵，不能只输出单一分数；
- `needs_teacher_decision` 只用于未满足的偏好或可接受降级，教师选择会创建新 revision；
- 任何硬要求未满足进入 `blocked_quality`。

## 6. 来源发现与质量架构

### 6.1 分层检索

每个知识点按顺序执行：

1. 已上传教材与教师指定资料；
2. `required_domains` 和指定 URL；
3. `preferred_domains` / `preferred_organizations`；
4. 学科权威来源注册表；
5. 可信教育来源；
6. 教师允许时才搜索社区来源；
7. 仍有缺口且允许时使用 AI 生成，并明确标识。

每一层有独立搜索轮数、候选上限和停止条件。高质量来源已经满足要求时不继续堆积低质量候选。

### 6.2 查询计划

新增 `ResearchPlan`，每条查询绑定：

- `requirement_ids`；
- topic、受众、深度与产物类型；
- 指定域名或组织；
- 语言和时间范围；
- 搜索意图：概念、机制、案例、实验、练习依据或反例；
- 期望证据数量和退出条件。

例如：

```text
site:docs.kernel.org admin-guide cgroup-v2 cpu memory io controller
site:docs.docker.com engine containers resource_constraints --cpus --memory --device-read-bps
```

不能再只使用“知识点 + 教程 + 讲义”作为统一查询。

### 6.3 来源权威性

引入可版本化 `SourceAuthorityRegistry`：

- A：官方文档、标准组织、政府、大学课程、同行评审或公认开放教材；
- B：有编辑责任的专业出版物和教育平台；
- C：可追溯作者的技术社区文章，仅作补充；
- D：SEO 聚合、文档下载站、无作者转载、正文异常或来源不可追溯，默认拒绝。

权威性不能再由 `.org`、`.edu` 后缀单独决定。每条记录包含组织、域名、学科范围、证据、维护者和生效版本。教师指定域名优先于通用注册表，但仍执行安全和正文质量检查。

### 6.4 全文与证据质量

候选必须经过：

- 最终 URL、HTTP 状态、robots、MIME 和内容长度检查；
- 标题、作者/组织、发布日期、正文、语言和 canonical URL 提取；
- 导航、广告、评论、重复段落和提示注入清洗；
- URL 与正文 hash 去重；
- 与知识点、深度和 requirement 的语义相关性判断；
- 关键事实保存可引用证据片段，不把搜索摘要当作全文；
- 抽取失败与降级模式显式记录。

## 7. 教学材料生产

### 7.1 产物编译器

根据 `deliverables` 创建明确产物：

- `concept_explanation`：概念、机制、适用边界、误区；
- `worked_case`：上下文、步骤、输入、输出、验证和解释；
- `exercise_with_solution`：题目、难度、考查目标、答案、解析和评分点；
- `lab`：环境、步骤、预期结果、故障排查；
- `glossary`、`comparison` 等其他结构化类型。

直接抓取的来源文档可以提供证据，但只有符合产物 schema 的内容才计入对应交付数量。若外部资料不能直接满足，允许基于合格证据生成教学产物，并把它标记为 AI 整理内容而不是外部原文。

### 7.2 受众与深度适配

材料生成器必须接收完整 `course_profile` 和 `depth_profile`。审查项至少包括：

- 前置知识是否超出受众；
- 术语是否有定义；
- 示例是否达到指定复杂度但不越级；
- 练习难度分布与目标 Bloom 层级是否一致；
- 总内容量是否可在课时预算内使用；
- 结论是否有证据支持，推断是否明确标记。

## 8. 逐项覆盖矩阵

新增 `RequirementCoverageReport`：

| requirement | 证据来源 | 教学产物 | 验证方法 | 结果 | 差距 |
| --- | --- | --- | --- | --- | --- |
| CPU/内存/I/O 机制 | Kernel/Docker 文档 | 概念讲义 | 证据蕴含审查 | passed | 无 |
| Docker 案例 1 个 | Docker 文档 | worked_case ×1 | schema + 命令检查 | passed | 无 |
| 带解析练习 3 道 | 上述证据 | exercise_with_solution ×3 | 数量 + 答案一致性 | passed | 无 |
| 优先官方来源 | 来源注册表 | 4 个来源 | 域名与 tier 检查 | warning/failed | 官方来源不足 |

覆盖报告必须能从 requirement 追溯到 topic、source、chunk、artifact、review 和最终文档。未引用证据的模型判断不能把 requirement 标记为通过。

## 9. 多维质量门禁

废除“单一 100 分代表全部质量”的表达。保留综合分用于排序，但 UI 必须同时显示以下维度：

1. `intent_adherence`：教师硬要求与偏好满足度；
2. `source_authority`：权威来源比例、指定来源命中和来源多样性；
3. `evidence_grounding`：正文证据、引用和关键事实支持；
4. `content_correctness`：概念、命令、计算和答案正确性；
5. `pedagogical_fit`：受众、深度、目标、案例与评价匹配；
6. `coverage`：每个知识点和每类交付物覆盖；
7. `technical_integrity`：图谱、索引、来源字段、版本和发布原子性。

门禁规则：

- 任一硬 requirement 未通过：阻塞；
- 指定 required domain 为 0：阻塞；
- preferred domain 为 0：进入教师决策，不静默通过；
- D 级来源：默认不得发布；
- 只拿到摘要、没有全文证据：不能用于关键事实通过；
- 练习缺答案或答案审查失败：不计入数量；
- 多维任一阻断项存在：综合分上限 59，不能显示 100；
- 发布前保存完整质量报告和评审模型/规则版本。

## 10. Agent 工具与权限

V2 工具建议：

```text
analyze_course_knowledge_intent
revise_course_knowledge_intent
preview_course_source_feasibility
plan_course_knowledge
query_course_knowledge_build
explain_course_knowledge_quality
retry_course_knowledge_build
```

- 分析与预检工具无正式知识库副作用；
- 修改 intent 必须携带 build ID 和 revision；
- Agent 可以解释质量差距和提出修订，但不能替教师接受降级；
- Agent 没有确认、发布、回滚和删除工具；
- 权限每次重新检查，不能信任会话缓存身份；
- 工具结果提供固定结构化状态，模型文案不能覆盖事实。

## 11. 教师界面

向导调整为四个可理解阶段：

1. **需求确认**：原始输入、结构化需求、假设和澄清问题；
2. **目录与来源策略**：三档课程方案、来源层级、指定域名和可用性预检；
3. **确认执行**：编辑图谱、查看预计产物与成本、冻结 revision；
4. **质量与发布结果**：逐项覆盖矩阵、来源分布、失败原因和版本差异。

页面必须直接展示：

- “已理解”和“待确认”的要求；
- 硬要求与偏好；
- 每个知识点计划生成什么，而不只是找几份资料；
- 实际命中的 A/B/C/D 来源及被拒原因；
- 未满足项和可选动作：继续检索、允许社区来源、允许 AI 整理、修改范围；
- 增量更新前后节点与文档差异。

## 12. 数据与接口

建议新增或扩展：

- `knowledge_build_intents`：版本化需求契约；
- `knowledge_requirements`：原文、规范值、硬度和验证器；
- `knowledge_research_plans`：查询和退出条件；
- `knowledge_source_evaluations`：来源层级、全文状态和拒绝原因；
- `knowledge_learning_artifacts`：教学产物类型、数量、来源引用和审核状态；
- `knowledge_requirement_coverage`：逐项覆盖结果；
- `knowledge_quality_reports`：多维分数、硬阻断项和评审版本。

所有记录包含 `course_id`、`build_id`、`intent_revision`、创建者、时间和配置快照。对现有 `plan_snapshot` 保持只读兼容，V2 发布记录必须指向 intent 和 quality report。

## 13. 恢复、幂等与并发

- 每个 intent revision 只能创建一个活动 build，使用 `(course_id, intent_revision)` 幂等键；
- Agent SSE 中断后由结构化 build 状态恢复，不重复创建草稿；
- 查询、抓取、抽取、材料生成和验证分别保存 checkpoint；
- 相同 canonical URL 和内容 hash 不重复下载或索引；
- baseline 或资料快照变化时旧 intent 进入 stale，不自动覆盖；
- provider 失败时记录具体阶段和降级，不把摘要模式伪装成全文模式；
- 质量修复只重跑未通过 requirement，不重新构建全部课程。

## 14. 可观测性

每次构建至少记录：

- 原始需求、结构化需求和确认 revision；
- 澄清问题、假设和教师选择；
- 每条查询、provider、域名过滤、搜索轮次和退出原因；
- 候选来源 tier、选择/拒绝原因、全文字符数和 hash；
- requirement → source → artifact → quality check 链路；
- 模型、prompt、规则和来源注册表版本；
- 各阶段耗时、token、外部调用数、失败率和缓存命中率；
- 发布版本和增量保留检查。

运营指标应优先观察硬要求遗漏率、偏好降级率、A/B 来源占比、教师退回率和发布后删除率，而不是只观察构建成功率。

## 15. 迁移与上线

1. **Shadow**：V1 正常发布，V2 只生成 intent、覆盖矩阵和来源评分，用真实课程对比漏报；
2. **教师试用**：新课程可选择 V2，硬门禁启用，保留 V1 回退开关；
3. **默认 V2**：达到验收阈值后新建和增量默认使用 V2；
4. **关闭 V1 新入口**：历史 build 只读兼容，V1 仅用于恢复既有任务；
5. **持续评测**：固定离线需求集每日跑，真实外网代表课程每周跑，来源注册表定期维护。

## 16. 本期不做

- 不允许 Agent 无教师确认直接发布；
- 不用单个大模型调用同时完成需求理解、搜索、写作和评分；
- 不以域名后缀或网页热度代替学术/官方权威性；
- 不承诺绕过 robots、付费墙或版权限制；
- 不自动把社区来源洗写成“官方结论”；
- 不在硬约束失败时用 AI 内容静默填满数量。
