# 课程知识库可配置、图谱先行构建实施计划

> **日期**：2026-08-12
> **状态**：待实施
> **对应规格**：[SPEC-14](../../spec/SPEC-14_课程知识库可配置图谱先行构建.md)
> **验收文档**：[ACC-14](../../acceptance/ACC-14_课程知识库可配置图谱先行构建_验收.md)

**目标：** 将当前“一键预览后立即构建”的课程知识库路径重构为“用户配置—可选教材—模型图谱—用户确认—网络/教材构建—受约束 AI 补充—质量门禁—原子发布”的持久工作流。

**架构：** 保留 PostgreSQL 知识库、统一 job store、RAG 导入、图谱版本和课程知识页主路径。以持久 `knowledge_build` 为工作流事实源；以已确认图谱 revision 为正式构建输入；以教材暂存输入和网络抓取文档为非 AI 证据；以质量硬门禁控制原子发布。

**技术栈：** React 18、TypeScript、Vite、FastAPI、Pydantic、SQLAlchemy、PostgreSQL、现有 LLM runtime resolver、Bocha/Tavily/Web 抽取层、MinerU、RAG v2、Node Test Runner、Pytest、Playwright。

---

## 1. 执行约束

1. 所有生产修改测试先行；每个任务先增加能暴露当前行为的失败测试，再实现，再运行聚焦回归。
2. 不修改、删除或提交现有运行数据，尤其是：
   - `Edu_AI/api/course_data/courses/**`
   - `Edu_AI/api/data/**`
   - 当前 PostgreSQL 中的用户课程、构建、文档和图谱版本
3. 数据库变更通过 Alembic 或仓库当前迁移机制完成；测试使用临时 PostgreSQL/测试 engine，不手改生产表。
4. 不回退工作区已有未提交修改；提交时只暂存本任务涉及文件，禁止 `git add .`。
5. 旧图谱版本和旧文档必须继续可读、可回滚；新流程不得要求清空知识库。
6. 许可字段可以保留兼容，但任何新代码和测试都不得用其阻止候选、抓取或发布。
7. 图谱模型失败时不得调用硬编码发布 fallback。
8. `graph_review` 是等待用户的业务状态，不占用 worker、不被任务中心当作运行中任务轮询。
9. 每个阶段结束先运行本阶段聚焦测试；数据库/API/前端三个纵向切片完成后再运行全量门禁。
10. 实施完成前 SPEC-14 和 ACC-14 保持“待实施/待验收”，不得预先写成通过。

## 2. 起始实现证据

实施前记录并用测试固定以下现状：

- `CourseKnowledgeBuildCard.buildKnowledgeBase()` 连续调用 `previewCourseKnowledgeBuild` 和 `startCourseKnowledgeBuild`。
- `CourseKnowledgeBuildPreviewRequest` 只有 `discover_sources` 和 `max_results_per_topic`。
- `derive_course_topics()` 直接从 `objectives[:12]` 生成主题；`build_course_graph_draft()` 使用固定根—模块—叶结构。
- planner 只搜索 `topics[:6]`，并以固定域名许可策略批准来源。
- `MIN_DOCUMENTS_PER_LEAF = 3`，零外部来源时 builder 自动生成 AI 补充。
- 质量评分允许全 AI 文档获得满分。
- `KnowledgeDocumentsView` 只在 course ID 变化时加载图谱，job 成功后不刷新。
- 普通上传资料不会进入构建计划；旧 textbook-import 会直接保存图谱。

这些测试是回归保护，不是保留旧行为；后续任务应逐项替换断言。

## 3. 计划文件地图

### 3.1 后端主要修改

- API 与 schema：
  - `Edu_AI/api/src/app/api/courses.py`
  - `Edu_AI/api/src/app/schemas/course.py`
- 持久化与迁移：
  - `Edu_AI/api/src/app/database/models.py`
  - `Edu_AI/api/src/app/persistence/postgres_knowledge_repository.py`
  - `Edu_AI/api/src/app/database/migrations/*` 或当前 Alembic revisions
- 构建服务：
  - `Edu_AI/api/src/app/services/course_knowledge_planner.py`
  - `Edu_AI/api/src/app/services/course_knowledge_plan_builder.py`
  - 新增 `course_knowledge_graph_generator.py`
  - 新增 `course_knowledge_textbook_inputs.py`
  - 新增 `course_knowledge_source_discovery.py`
  - 新增 `course_knowledge_quality_gate.py`
  - `Edu_AI/api/src/app/services/platform_task_handlers.py`
- 教材与解析复用：
  - `Edu_AI/api/src/app/textbook_knowledge_graph.py`
  - `Edu_AI/api/src/core/course_storage.py`
- Web 与模型运行配置：
  - `Edu_AI/api/src/app/services/deepsearch_service.py`
  - `Edu_AI/api/src/app/services/runtime_config_resolver.py`

### 3.2 前端主要修改

- API 与类型：
  - `Edu_AI/src/stitch/api/courses.ts`
  - `Edu_AI/src/stitch/api/types.ts`
- 当前课程知识页：
  - `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx`
  - `Edu_AI/src/stitch/course/knowledge/KnowledgeDocumentsView.tsx`
  - `Edu_AI/src/stitch/course/knowledge/KnowledgeStructureView.tsx`
- 新增构建向导组件：
  - `CourseKnowledgeBuildWizard.tsx`
  - `CourseKnowledgeBuildConfigStep.tsx`
  - `CourseKnowledgeTextbookStep.tsx`
  - `CourseKnowledgeGraphReviewStep.tsx`
  - `CourseKnowledgeBuildProgress.tsx`
  - `CourseKnowledgeBuildQualitySummary.tsx`
- 状态与样式：
  - 新增 `courseKnowledgeBuildState.ts`
  - `CourseKnowledgeBuildCard.css` 或拆分后的 wizard CSS
- 统一后台任务：
  - `Edu_AI/src/jobs/jobStore.ts`
  - `Edu_AI/src/jobs/types.ts`

### 3.3 主要测试

- 后端：`Edu_AI/api/src/tests/services/test_course_knowledge_*.py`
- API：新增 `Edu_AI/api/src/tests/test_course_knowledge_build_workflow.py`
- 持久化：`Edu_AI/api/src/tests/persistence/test_postgres_knowledge_repository.py`
- 前端：`Edu_AI/src/stitch/course/knowledge/*.test.ts(x)`
- E2E：新增 `Edu_AI/tests/e2e/course-knowledge-build-wizard.spec.ts`

---

## Task 1：冻结基线并增加问题复现测试

**修改：** 仅测试与验收 fixture，不修改生产行为。

- [ ] 记录 `git status --short --branch` 并分类用户修改、运行数据和本任务文档。
- [ ] 增加前端失败测试：点击一次不应同时创建草案并启动正式任务。
- [ ] 增加 API 失败测试：未确认图谱时 `/start` 应返回 422。
- [ ] 增加 planner 失败测试：课程目标不能直接成为发布图谱，必须调用模型适配器。
- [ ] 增加来源失败测试：相关来源缺少许可信息仍应可选。
- [ ] 增加质量失败测试：配置要求网络且网络为 0 时不得发布或得到 100 分。
- [ ] 增加刷新失败测试：job 成功事件应触发图谱和文档重新加载。
- [ ] 使用临时课程 fixture 复现“课程目标为 1”的无效输入边界，不读取或改写真实课程。

**聚焦命令：**

```powershell
Set-Location Edu_AI
node --import tsx --test src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts

Set-Location api
D:\anaconda\envs\edu-ai\python.exe -m pytest -q `
  src/tests/services/test_course_knowledge_planner.py `
  src/tests/services/test_course_knowledge_plan_builder.py `
  src/tests/persistence/test_postgres_knowledge_repository.py
```

**通过条件：** 新测试准确暴露当前五类缺陷；已有无关测试结果被记录而未被掩盖。

---

## Task 2：建立配置、修订和确认数据契约

**文件：**

- 修改 `app/schemas/course.py`
- 修改 `app/database/models.py`
- 修改 `app/persistence/postgres_knowledge_repository.py`
- 新增数据库迁移
- 新增/修改 schema、repository 测试

- [ ] 定义 `CourseKnowledgeBuildConfig`，实现小型/标准/大型预设规范化和数值边界。
- [ ] 扩展构建记录：`revision`、`graph_confirmed_at`、`confirmed_graph_revision`、`confirmed_by`。
- [ ] 新增教材输入持久模型，保存 build、文件元数据、内容哈希、解析状态、解析结果引用和错误。
- [ ] 设计暂存文档与 build ID 的关联，确保发布前不进入 ready 课程检索。
- [ ] repository 支持创建草案、更新配置、保存图谱草案、确认 revision、读取完整快照。
- [ ] 使用条件更新实现 revision 乐观锁；冲突返回可识别异常。
- [ ] 同一课程允许未确认草案，但正式活动构建仍保持唯一。
- [ ] 迁移对既有构建记录提供兼容默认值，不修改既有图谱版本。

**测试必须覆盖：**

- 三个预设和手工覆盖；非法范围 422。
- revision 从 1 开始并单调递增。
- stale revision 更新失败且数据不被覆盖。
- 未确认/确认信息完整性。
- 教材内容哈希在同一 build 内去重。
- 旧构建记录可读。

**通过条件：** 所有后续阶段都可以从数据库恢复，不依赖 localStorage 或进程内存。

---

## Task 3：重构构建草案 API，切断自动启动

**文件：**

- 修改 `app/api/courses.py`
- 修改 `app/schemas/course.py`
- 修改 `src/stitch/api/courses.ts`
- 修改 `src/stitch/api/types.ts`
- 新增 `test_course_knowledge_build_workflow.py`

- [ ] 实现 `POST /knowledge-builds`，只创建配置草案，不搜索网络、不创建正式 job。
- [ ] 实现 GET/PATCH 草案接口和 revision 409 映射。
- [ ] 实现图谱保存、确认、取消和重试 API 壳层。
- [ ] `/start` 校验确认人、确认时间和 confirmed revision 与当前 revision 一致。
- [ ] 旧 `/preview` 暂时转发为“创建草案”，响应带 deprecation 元数据；不得 start。
- [ ] 前端 API 去掉 `previewCourseKnowledgeBuild(courseId)` 的固定参数，改为显式 config payload。
- [ ] 删除 `buildKnowledgeBase()` 中 preview 后立即 start 的连续调用。
- [ ] 所有 mutation 继续使用课程 generate/edit principal，GET 使用 read principal。

**通过条件：** 创建草案后后端没有网络查询、抓取、RAG 导入、AI 补充或正式 job；直接 start 稳定失败。

---

## Task 4：实现强制 LLM 图谱生成器

**文件：**

- 新增 `app/services/course_knowledge_graph_generator.py`
- 精简 `course_knowledge_planner.py`，移除发布用硬编码 graph builder
- 修改 `platform_task_handlers.py`
- 新增 `test_course_knowledge_graph_generator.py`

- [ ] 定义独立 graph model adapter，从 `runtime_config_resolver` 解析当前用户 LLM。
- [ ] 构建模型输入：课程元数据、规范化配置、当前图谱摘要、更新策略、可选教材目录和摘要。
- [ ] 使用明确 JSON Schema 解析模型输出，拒绝自由文本和代码围栏残留。
- [ ] 确定性验证 ID 唯一、层级、节点类型、空标签、重复标签、循环和规模偏差。
- [ ] 最多执行两次带结构化错误的模型修复。
- [ ] 支持模块级重生成，并保持未选择模块节点 ID 不变。
- [ ] 模型不可用或修复失败时保存稳定错误，不调用 `_fallback_graph`。
- [ ] 在 graph draft 中保存 `generation_model`、`prompt_version`、`generated_at` 和 validation 摘要，但不保存密钥。

**测试必须覆盖：**

- 无教材课程真实调用 fake model 一次并使用其结构。
- 有教材课程 prompt 含目录/摘要且输出包含教材章节映射。
- 目标规模 ±20% 校验。
- “1”“知识点”等无语义叶节点被拒绝或修复。
- 模型连续无效时不产生可发布 fallback。
- 局部重生成不改变其他模块 ID。

**通过条件：** 生产图谱草案的唯一入口是模型生成器加确定性校验器。

---

## Task 5：把教材改造成构建输入，而不是旁路图谱导入

**文件：**

- 新增 `app/services/course_knowledge_textbook_inputs.py`
- 重构复用 `app/textbook_knowledge_graph.py` 的解析函数
- 修改 `app/api/courses.py`
- 修改 `core/course_storage.py`
- 修改 `platform_task_handlers.py`
- 新增教材输入/解析测试

- [ ] 支持 `.pdf/.docx/.txt/.md`，前后端格式声明一致。
- [ ] 上传后保存原始不可变文件和数据库记录，再创建有期限的解析 job。
- [ ] 抽取目录候选、章节、正文块、页码/标题锚点、警告和受限长度摘要。
- [ ] 解析结果只写暂存区，不调用 `save_knowledge_graph`，不导入当前 ready RAG。
- [ ] 解析失败保留原文件；实现重试、移除和替换。
- [ ] 多教材按内容哈希去重，允许不同教材共同参与模型图谱。
- [ ] 旧 `/knowledge-graph/textbook-import` 从新页面移除；后端添加弃用提示并内部复用解析层，禁止直接覆盖新流程草案。
- [ ] 修复旧前端声称支持 PPT/PPTX 而后端不支持的不一致。

**通过条件：** 上传教材只改变当前 build draft；当前已发布图谱、文档列表和 RAG 检索结果保持不变。

---

## Task 6：实现配置与教材步骤前端

**文件：**

- 新增 `CourseKnowledgeBuildWizard.tsx`
- 新增 `CourseKnowledgeBuildConfigStep.tsx`
- 新增 `CourseKnowledgeTextbookStep.tsx`
- 新增 `courseKnowledgeBuildState.ts`
- 修改 `CourseKnowledgeBuildCard.tsx`
- 修改相关 CSS 与组件测试

- [ ] 主按钮改为“新建构建方案”或“继续构建方案”。
- [ ] 实现三个预设、所有高级字段、即时边界校验和预计叶节点/资料总量。
- [ ] 教材步骤明确“可跳过”，支持多文件、逐文件解析状态、重试、移除和警告。
- [ ] 创建草案后 URL/localStorage 只记录 build ID；刷新后完整状态从后端恢复。
- [ ] 保存配置时携带 revision，409 时提示重新加载或对比，不自动覆盖。
- [ ] 没有教材时“生成图谱草案”仍可用。
- [ ] 配置/教材阶段不注册正式 build_knowledge_index job。

**测试必须覆盖：**

- 标准预设默认值和自定义覆盖。
- 教材可跳过。
- 文件格式与后端一致。
- 刷新恢复和 stale revision 冲突。
- 创建草案不会调用 start。

**通过条件：** 用户能在不上传教材的情况下完成配置，也能等待所有已上传教材解析后生成图谱。

---

## Task 7：实现图谱审核、编辑与确认界面

**文件：**

- 新增 `CourseKnowledgeGraphReviewStep.tsx`
- 新增图谱草案编辑 helper 与测试
- 修改 wizard 状态与 API

- [ ] 展示完整树、配置目标、实际规模、教材章节映射和 validation 警告。
- [ ] 支持节点增删、重命名、summary 编辑、同级排序和父子移动。
- [ ] 只允许合法层级移动；客户端预校验不替代后端 schema 校验。
- [ ] 支持全量和模块级重新生成，显示模型处理中状态。
- [ ] 保存与确认使用 revision；确认前显示正式构建影响提示。
- [ ] 确认成功后界面冻结当前结构并显示确认时间/修订；任何再次修改回到 review。
- [ ] 键盘可操作主要编辑与确认动作，错误不能只用颜色表示。

**通过条件：** 用户可以明确指出正式构建将使用的每一个叶节点；未确认时无法进入下一阶段。

---

## Task 8：重写网络发现，取消许可拒绝

**文件：**

- 新增 `course_knowledge_source_discovery.py`
- 修改/收口 `course_knowledge_planner.py`
- 复用 `deepsearch_service.py`
- 修改 source candidate 持久化映射
- 新增 discovery 测试

- [ ] 只对 confirmed graph 的全部叶节点执行搜索，不再限制 `topics[:6]`。
- [ ] 每叶生成中文优先、配置语言补充的语义查询。
- [ ] 候选按 URL、规范化最终 URL 和内容哈希去重。
- [ ] 取消 `_REVIEWED_DOMAIN_POLICIES` 对批准状态的控制；许可缺失不影响 selected。
- [ ] `review_status` 改为 `discovered/relevant/rejected_irrelevant/fetch_failed/ready` 等技术和质量语义。
- [ ] relevance、空 URL、不支持协议等仍可拒绝，并保存明确原因。
- [ ] 保存查询、节点、标题、URL、域名、时间和来源 provider。
- [ ] 许可字段保持可空兼容，不进入质量门禁。
- [ ] 来源搜索错误按叶节点隔离，不因一个 query 中断整次构建。

**通过条件：** 缺失许可元数据但相关、HTTPS 可访问的测试页面能够进入抓取；无固定域名白名单依赖。

---

## Task 9：教材拆分映射、网页抓取与统一入库

**文件：**

- 修改 `course_knowledge_plan_builder.py`
- 扩展 `course_knowledge_textbook_inputs.py`
- 修改 `course_storage.py` 和 RAG import metadata
- 新增 builder/mapping 测试

- [ ] 正式任务从 confirmed graph snapshot 读取不可变叶节点列表。
- [ ] 抓取相关网络候选，保存正文、来源和内容哈希；单 URL 失败可继续。
- [ ] 按确认图谱拆分教材内容，保存原教材—章节—块—节点映射。
- [ ] 映射采用结构锚点优先、语义匹配补充；保存方法和置信度。
- [ ] 低置信度块进入 unmapped，不计覆盖率、不随意归档。
- [ ] 教材原文件作为课程级来源，映射块作为节点级 RAG 证据；UI 文档列表不被块记录淹没。
- [ ] 所有 staged 文档带 build ID；失败/取消前不 ready。
- [ ] 重试按内容哈希和 idempotency key 去重，不重复导入。

**通过条件：** 给定两章教材和四个叶节点，测试能够从资料预览追溯到原章节/页码，RAG metadata 含正确节点 ID。

---

## Task 10：实现受配置约束的 AI 补充与质量硬门禁

**文件：**

- 新增 `course_knowledge_quality_gate.py`
- 修改 `course_knowledge_plan_builder.py`
- 修改 `course_generated_material.py`
- 修改 quality repository/tests

- [ ] 先统计每叶教材、网络、AI、失败和未映射数量，再计算缺口。
- [ ] 只有 `ai_supplement_enabled` 且未达 AI 上限时生成补充。
- [ ] AI 数量不得超过 `maximum_ai_materials_per_leaf`，不计入 web minimum。
- [ ] 实现 SPEC-14 的八项硬门禁并逐项落库。
- [ ] 移除当前“model_generated 自动 provenance_ok”的满分路径。
- [ ] 总分如保留，必须由硬门禁约束；blocked 结果不能展示为质量通过。
- [ ] web minimum 为 0 时允许纯教材或用户明确接受的 AI 组合；配置大于 0 时网络不足必须 blocked。
- [ ] blocked 结果保留 staged 资产和稳定重试点，允许重新搜索或调整配置后生成新 revision。

**通过条件：** `minimum_web=1`、实际 web=0、AI=3 的构建稳定 blocked；`minimum_web=0` 的同类显式配置按其他门禁判定。

---

## Task 11：原子发布、更新策略与版本回滚

**文件：**

- 修改 `postgres_knowledge_repository.py`
- 修改 `course_knowledge_plan_builder.py`
- 修改图谱版本和文档发布测试

- [ ] 在同一事务内校验 staged 文档、写图谱版本、提升参与文档、更新 build 终态。
- [ ] 发布失败回滚事务，当前 graph version 和 ready 文档集合不变。
- [ ] `incremental` 保持既有节点和资料；新增内容去重合并。
- [ ] `merge_rebuild` 保存节点迁移表，能够把仍匹配的既有资料关联到新节点。
- [ ] `full_rebuild` 创建全新版本但不删除旧版本。
- [ ] rollback 恢复目标图谱及对应可见文档集合，不只切换图谱 JSON。
- [ ] 重复 publish/retry 不增加第二个相同版本。

**通过条件：** 使用故障注入证明发布中断不会产生半个图谱版本或部分 ready 文档。

---

## Task 12：正式构建进度、阻塞处理与自动刷新

**文件：**

- 新增 `CourseKnowledgeBuildProgress.tsx`
- 新增 `CourseKnowledgeBuildQualitySummary.tsx`
- 修改 `KnowledgeDocumentsView.tsx`
- 修改 `KnowledgeStructureView.tsx`
- 修改 `CourseKnowledgeBuildCard.tsx`
- 修改 job store 集成测试

- [ ] 显示教材解析、图谱审核、搜索、抓取、教材映射、索引、AI 补充、质量、发布等真实阶段。
- [ ] 正式 start 后才注册 `build_knowledge_index` job。
- [ ] 逐来源显示数量，不再只显示模糊“资料查找自动完成”。
- [ ] blocked 显示具体节点缺口，并提供重新搜索、调整配置、重试。
- [ ] 支持取消；离开页面后由全局 job center 继续跟踪。
- [ ] job 成功、回滚或知识文档更新统一派发 course knowledge refresh 事件。
- [ ] 两个知识视图都监听 refresh，重新拉取 graph、documents、versions 和 build summary。
- [ ] 成功提示只有在新数据成功读取后才显示“图谱和资料可用”。

**通过条件：** 构建前看到占位图的浏览器在任务成功后无需手工刷新即可显示新图谱和正确资料。

---

## Task 13：弃用旧路径并完成兼容迁移

**文件：**

- 修改旧 `KnowledgeGraphPage.tsx` 可达入口或路由
- 修改 `/knowledge-graph/textbook-import`
- 修改 `CourseKnowledgeBase.tsx` 旧开放教材按钮
- 更新相关替换/路由测试

- [ ] 当前主界面不再暴露直接覆盖图谱的教材导入。
- [ ] 当前主界面不再暴露与 SPEC-14 冲突的“一键开放教材重建”。
- [ ] 旧路由如仍需兼容，导航到新构建向导并携带动作参数。
- [ ] 旧 API 返回 deprecation header/字段，不删除历史调用方所需读取能力。
- [ ] 删除或改写“primary experience simple”测试中禁止图谱/来源审核的旧断言。
- [ ] 保留已发布旧图谱和教材衍生材料的读取兼容。

**通过条件：** 用户从任何当前可达课程知识入口发起构建时都进入同一 SPEC-14 工作流。

---

## Task 14：自动化、真实 E2E 与文档收口

**文件：**

- 新增 `tests/e2e/course-knowledge-build-wizard.spec.ts`
- 更新 SPEC-14、ACC-14、索引和项目地图
- 不使用真实用户课程作为自动化 fixture

- [ ] 运行所有新增后端单元、API、持久化和任务测试。
- [ ] 运行所有新增前端状态、组件、API 和刷新测试。
- [ ] 运行课程知识、RAG、任务、上传、权限和版本回滚相关既有回归。
- [ ] 运行前端 lint/build 和后端相关全量测试。
- [ ] 使用 stub provider 完成无教材、有教材、自定义规模、网络不足、许可缺失、刷新恢复 E2E。
- [ ] 使用真实配置完成一门无教材和一门含教材临时课程的端到端验收。
- [ ] 记录 build ID、graph version、来源统计、质量检查和截图。
- [ ] 删除临时课程必须由测试 fixture 的可恢复清理完成；不得清理用户课程。
- [ ] 所有 ACC-14 强制项有证据后才更新为“通过”。

**全量门禁建议：**

```powershell
Set-Location Edu_AI
npm test
npm run lint
npm run build
pnpm exec playwright test tests/e2e/course-knowledge-build-wizard.spec.ts

Set-Location api
D:\anaconda\envs\edu-ai\python.exe -m pytest -q src/tests
```

若全仓存在既有失败，必须记录命令、失败项、基线复现和与 SPEC-14 的隔离结论；不得将非零退出码写成通过。

**通过条件：** ACC-14 全部强制项通过，规格、计划、验收、索引和项目地图互相引用且状态一致。

---

## 4. 推荐提交边界

按以下顺序小步提交，提交信息仅为建议：

1. `test(knowledge): capture graph-first build gaps`
2. `feat(knowledge): add configurable build draft contract`
3. `feat(knowledge): generate graph drafts with llm`
4. `feat(knowledge): stage and parse textbook inputs`
5. `feat(knowledge): add build configuration and graph review wizard`
6. `feat(knowledge): discover sources without license gate`
7. `feat(knowledge): map textbook and web evidence to graph`
8. `fix(knowledge): enforce source and ai quality gates`
9. `feat(knowledge): publish graph builds atomically`
10. `feat(knowledge): refresh build results and retire legacy entrypoints`
11. `test(knowledge): complete spec 14 acceptance coverage`

## 5. 风险与回退

| 风险 | 控制措施 | 回退 |
| --- | --- | --- |
| 模型图谱不稳定 | JSON Schema、确定性验证、两次修复、人工确认 | 保留草案与错误，不发布 fallback |
| 教材解析耗时或失败 | 独立 job、逐文件状态、重试/移除 | 跳过失败教材后重新生成草案 |
| 网络候选噪声增加 | 相关性、正文长度、去重、抓取成功门槛 | 调整搜索/相关性配置，不恢复许可白名单 |
| AI 补充成本扩大 | 每叶硬上限、缺口后置计算、并发限制 | 禁用 AI 或降低上限 |
| 更新图谱导致资料错挂 | 节点迁移表、映射置信度、原子版本 | 回滚旧图谱与文档集合 |
| 迁移破坏旧构建 | nullable/default 兼容、迁移测试 | 关闭新入口，旧已发布读取保持可用 |
| 前端草案状态丢失 | 后端事实源、revision、刷新恢复 | 重新读取 build，不创建重复草案 |

## 6. 阶段验收门槛

- **阶段 A（Task 1–4）**：持久草案、配置、确认门禁和模型图谱后端成立。
- **阶段 B（Task 5–7）**：教材暂存、配置 UI 和图谱审核闭环成立。
- **阶段 C（Task 8–10）**：网络、教材、AI 资料构建和质量门禁成立。
- **阶段 D（Task 11–13）**：原子发布、版本、刷新和旧路径收口成立。
- **阶段 E（Task 14）**：自动化与真实 E2E 证据完成。

任一阶段未通过不得把后续阶段的静态界面或 mock 结果描述为功能完成。

## 7. 实施决策记录

实施中遇到规格未穷尽、但不需要扩大产品范围的决策时，按“安全、可恢复、兼容现有数据、便于验证”的优先级选择最优解，并在此表追加记录。若决策会改变 SPEC-14 的产品语义，则必须先更新规格和 ACC-14，不能只改代码。

| ID | 日期 | 决策 | 理由 | 影响 |
| --- | --- | --- | --- | --- |
| D14-001 | 2026-08-12 | 设计基线单独提交并推送；实现从该提交创建隔离功能 worktree，按可测试小阶段提交和推送 | 主工作区可能包含用户修改；隔离后可避免夹带、便于逐阶段回退 | 仅影响版本控制，不改变产品语义 |
| D14-002 | 2026-08-12 | 图谱确认不递增 revision；确认记录绑定当前 revision，任何配置或图谱编辑都会递增 revision 并清除确认 | 避免“确认动作本身让刚确认版本立即过期”，同时让并发编辑和确认门禁具有确定语义 | 正式启动必须满足 `confirmed_graph_revision == revision` |
| D14-003 | 2026-08-12 | revision 与图谱确认元数据使用独立数据库列，配置和图谱草稿继续保存在 `plan_snapshot` JSON | 并发门禁需要数据库原子条件；草稿内容仍在快速演进，JSON 更利于兼容旧数据 | 新迁移保持旧构建可读，旧构建必须重新进入新草稿流程后才能启动 |
| D14-004 | 2026-08-12 | 前端主按钮第一阶段只创建草稿，不再串联预览和正式启动 | 在完整向导上线前先消除绕过图谱确认的旧入口，保证后端和界面行为一致 | 后续阶段在同一草稿上补充配置、教材与图谱审核界面 |
| D14-005 | 2026-08-12 | 图谱模型输出采用严格 JSON 对象、确定性校验和最多两次模型修复；禁止本地 fallback | 结构正确性可重复验证，模型失败不能伪装为成功图谱 | 失败保留 `GRAPH_MODEL_UNAVAILABLE`、`GRAPH_SCHEMA_INVALID` 或 `GRAPH_SCALE_UNSATISFIED` |
| D14-006 | 2026-08-12 | 全量和模块级图谱生成使用独立 `generate_graph` 后台任务，生成成功后才以 expected revision 原子写入草稿 | 模型调用可能耗时，且生成期间用户仍可能编辑配置；完成时的 revision 检查可阻止旧结果覆盖新配置 | 局部生成保持未选择模块 ID；冲突时任务失败并要求按最新草稿重试 |
| D14-007 | 2026-08-12 | 旧 `/knowledge-builds/preview` 仅转发为默认配置草稿并返回弃用信息，不再搜索或生成硬编码图谱 | 防止旧客户端绕过图谱先行流程，同时保留迁移期兼容入口 | 前端删除旧 preview 调用；正式图谱唯一来源为模型生成器或用户审核编辑 |
| D14-008 | 2026-08-12 | 教材原文件按 build/textbook ID 保存为不可变暂存文件，元数据和受限解析结果保存在构建草稿 JSON；解析任务写回时按最新 revision 合并 | 原文件与已发布知识库隔离，支持多教材并发解析，又避免解析任务用旧快照覆盖配置编辑 | 移除教材只移出草稿，原文件暂时保留以便恢复；构建清理策略在发布阶段统一处理 |
| D14-009 | 2026-08-12 | 旧 `/knowledge-graph/textbook-import` 返回 410，不再允许直接覆盖课程图谱 | 该入口缺少 build/revision，无法安全转发到新草稿；继续保留会绕过模型图谱审核门禁 | 客户端必须先创建构建草稿，再通过 `/knowledge-builds/{build_id}/textbooks` 上传 |
| D14-010 | 2026-08-12 | 前端仅在 localStorage 保存 build ID；向导打开、后台教材解析或图谱任务变化后重新读取后端草稿 | 避免浏览器缓存成为配置、教材状态或 revision 的事实源 | 刷新可恢复完整向导；后台任务完成后的 revision 不会被本地旧对象覆盖 |
| D14-011 | 2026-08-12 | 多教材上传、重试、移除和生成图谱前先读取最新草稿 revision，409 明确要求刷新而不自动覆盖 | 教材解析任务可能并发递增 revision，静默重放旧配置会造成数据丢失 | 前端保留用户输入并展示冲突提示，用户可在最新草稿上再次提交 |
| D14-012 | 2026-08-12 | 图谱编辑允许改名、说明、同层换父、同级排序和增删节点；结构操作后统一重算 level/type/hasChildren，保存与确认时服务端再次执行完整校验 | 前端即时规范化可减少无效草案，服务端校验则防止绕过界面提交或深浅不一致的叶节点 | 同层换父保证子树深度不变；规模、深度、教材映射不合格时拒绝保存或确认 |
| D14-013 | 2026-08-12 | 图谱重新生成不会自动保存当前编辑；若存在未保存修改，必须明确确认丢弃，确认并启动则先按最新 revision 保存、再确认、最后创建正式任务 | 模型重生成和人工编辑都是有损分支，需要显式边界；三步串联可保证启动绑定的正是用户看到的修订 | 任一步失败都停止后续动作并保留向导，409 不做静默覆盖 |
| D14-014 | 2026-08-12 | 网络发现从正式任务启动后执行，以确认图谱实时提取全部叶节点并替换旧的空 `topics/source_candidates`；不再依赖配置阶段预搜索 | 本次 0 网络资料的直接根因是新草稿将候选置空，而旧 builder 只消费预候选、从未重新检索 | 每个叶节点独立执行中文优先与配置语言补充查询；单节点搜索失败只记录 warning，不中断其他节点 |
| D14-015 | 2026-08-12 | 来源准入只保留 HTTPS、语义相关性、robots、正文长度、最终 URL/内容哈希去重和索引成功；许可证字段仅在来源明确提供时记录，缺失不拒绝 | 个人练习项目不需要开放许可白名单，同时仍需尊重技术访问边界并保证资料真实抓取成功 | 状态改用 `relevant → ready/fetch_failed` 等技术语义；固定域名表只可补充元数据，不参与 selected 或质量门禁 |
| D14-016 | 2026-08-12 | 教材原件发布为课程级可见文档；解析块按目录锚点优先、语义重合补充映射，并按“教材×叶节点”合并为隐藏索引文档 | 既要保留章节/页码/块级溯源，也要避免每个解析块占据一张资料卡 | 低于 0.12 置信度的块进入 unmapped；计入覆盖的映射保存方法、置信度和原块元数据 |
| D14-017 | 2026-08-12 | AI 缺口以网络和教材实际入库数为起点，严格受 `ai_supplement_enabled` 与每叶上限约束；质量判定改为 8 项硬门禁逐项落库 | AI 不能补偿强制网络最低数量，也不能凭旧综合分掩盖单项失败 | 任一门禁失败均进入 blocked；总分仅表示通过项比例，不再存在 model-generated 自动 provenance 满分路径 |
| D14-018 | 2026-08-12 | failed/blocked 构建保留确认修订和 staged 资产，可原构建 ID 重新排队；重试仍重新执行逐叶发现，但按来源、教材和 AI 暂存元数据幂等复用 | 重试必须有稳定检查点且不能重复发布或重复生成已合格资料 | UI 同时提供“重试本方案”和“新建方案调整配置”；只有确认修订仍匹配时允许 requeue |
| D14-019 | 2026-08-12 | 发布事务接收本次图谱引用的全部文档 ID，包括重试时复用的 received/ready 文档，而不是只接收新建文档 | 只提交新文档会让重试复用的暂存教材保持 received，造成图谱引用与可见状态不一致 | repository 在同一事务内校验并提升完整文档集合；ready 文档重复提升保持幂等 |
