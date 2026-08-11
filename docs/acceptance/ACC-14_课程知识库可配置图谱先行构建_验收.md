# ACC-14 课程知识库可配置、图谱先行构建验收

> **状态**：待实施、待验收
> **日期**：2026-08-12
> **对应规格**：[SPEC-14](../spec/SPEC-14_课程知识库可配置图谱先行构建.md)
> **实施计划**：[2026-08-12-configurable-graph-first-course-knowledge-build.md](../superpowers/plans/2026-08-12-configurable-graph-first-course-knowledge-build.md)
> **基线关系**：不得破坏现有课程权限、知识点范围 RAG、统一后台任务、图谱版本和知识库文档读取能力。

## 1. 验收目标

本验收判定课程知识库是否真正形成以下闭环：

1. 用户先配置规模和资料策略，教材可传可不传。
2. 无论有无教材，知识图谱草案都由模型生成并经过结构校验。
3. 有教材时，模型参考教材结构生成草案，确认后教材拆分内容参与节点级知识库。
4. 用户能够编辑并确认图谱；确认前没有网络搜索、抓取、正式索引、AI 补充或发布。
5. 网络资料不再因缺少开放许可或不在固定许可域名白名单中被拒绝。
6. 教材、网络、AI 资料分别计数，网络最低数和 AI 上限作为硬门禁。
7. 后台任务可恢复、可取消、可重试，发布是原子的，完成后页面自动显示新图谱和资料。
8. 初次构建和三种更新策略不会破坏历史版本或现有用户数据。

## 2. 验收环境与前置条件

- 使用包含 SPEC-14 实现的同一提交运行前端、FastAPI 后端、PostgreSQL 和所需 RAG/解析服务。
- 前端默认 `http://localhost:5173`，后端默认 `http://localhost:8001`；记录实际端口。
- 准备一个有课程 generate/edit 权限的教师账号和一个只读账号。
- 使用专门的临时验收课程，不使用 `computational-thinking` 或用户现有课程作为写入 fixture。
- 准备两份教材：
  - 一份结构清晰、至少两章四节的 Markdown/DOCX；
  - 一份可由当前 MinerU 成功解析的 PDF。
- 准备一个可控 Web fixture：相关正文超过最低长度、没有许可证元数据、可正常访问。
- 准备一个搜索结果为空或抓取全部失败的 provider fixture。
- 准备可记录调用次数和输入摘要的 LLM stub；真实 E2E 再使用运行时配置的真实模型。
- 数据库测试使用临时 schema/engine；E2E 临时课程有独立前缀和明确清理记录。

## 3. 通过规则

- AC14-01～AC14-14 全部为强制项；任一失败则 ACC-14 不通过。
- 自动化命令必须返回 0；静态无匹配检查可返回 1，但必须无输出。
- 人工/真实 E2E 的 B1～B7 全部执行并保存 build ID、course ID、graph version、截图和日志摘要。
- 外部 LLM、搜索或 MinerU 短时不可用只能记录为环境阻塞；恢复后必须重跑，不能跳过对应强制项。
- 不能用 mock 静态图、直接写数据库或手工刷新页面代替真实产品路径。
- 不能为了通过测试清空用户知识库、构建表、任务表或图谱版本表。
- 许可字段可以存在于兼容 schema，但任何缺失许可证的测试来源都不得因此失败。

## 4. 验收矩阵

| ID | 验收点 | 判定标准 | 主要证据 | 结果 |
| --- | --- | --- | --- | --- |
| AC14-01 | 可配置规模 | 小/标准/大预设和高级字段可编辑；后端保存规范化值并校验边界 | A1、A6、B1 | 待验收 |
| AC14-02 | 无教材模型图谱 | 无教材构建真实调用 LLM；结果来自模型输出；失败时无硬编码 fallback 发布 | A2、B1 | 待验收 |
| AC14-03 | 教材影响图谱 | 有教材时 LLM 输入含目录/摘要，草案覆盖教材章节或明确列出未映射项 | A2、A3、B2 | 待验收 |
| AC14-04 | 教材参与知识库 | 原教材、解析块、节点映射和 RAG metadata 可追溯；低置信度块不乱挂 | A3、B2 | 待验收 |
| AC14-05 | 确认硬门禁 | 未确认时 start=422，且无搜索、抓取、索引、AI 或发布调用 | A1、A4、B3 | 待验收 |
| AC14-06 | 图谱审核与修订 | 可编辑、局部重生成、revision 冲突保护、确认后冻结；修改后需重新确认 | A1、A2、A6、B3 | 待验收 |
| AC14-07 | 取消许可拒绝 | 缺失许可、非旧白名单域名的相关可访问网页能抓取并入库 | A4、B4 | 待验收 |
| AC14-08 | 来源分类统计 | 每叶展示教材、网络、AI、失败、未映射数量，且总数可由文档核对 | A4、A6、B1、B2 | 待验收 |
| AC14-09 | 资料与 AI 门禁 | 总资料、网络最低数、AI 上限逐叶执行；AI 不计入网络最低数 | A4、B5 | 待验收 |
| AC14-10 | 零网络不伪成功 | 配置要求网络且实际为 0 时 blocked、不发布、不满分；配置显式为 0 时按其他门禁判断 | A4、B5 | 待验收 |
| AC14-11 | 自动刷新 | 成功、回滚和资料更新后图谱、资料、统计、版本自动刷新，无手工 reload | A6、A7、B1 | 待验收 |
| AC14-12 | 更新与原子版本 | incremental/merge/full 语义成立；故障注入无半发布；回滚恢复图谱和文档集合 | A5、B6 | 待验收 |
| AC14-13 | 任务恢复与幂等 | 取消、失败重试、刷新恢复不重复搜索成果、文档、AI 资料或图谱版本 | A5、A6、A7、B7 | 待验收 |
| AC14-14 | 权限与数据保护 | 只读用户不能构建；路径/类型/密钥边界通过；现有课程数据和历史读取无回归 | A1、A3、A8、B7 | 待验收 |

## 5. 自动化与静态验收

所有命令从仓库根目录执行，除非小节另有 `Set-Location`。

### A1. 配置、持久草案、revision 与权限

```powershell
Set-Location Edu_AI/api
D:\anaconda\envs\edu-ai\python.exe -m pytest -q `
  src/tests/test_course_knowledge_build_workflow.py `
  src/tests/persistence/test_postgres_knowledge_repository.py `
  src/tests/test_course_crud_permissions.py
```

必须覆盖：

- 三个预设的默认值和所有高级字段范围。
- `POST /knowledge-builds` 只创建草案，不创建正式 job。
- PATCH/PUT 使用 revision；过期 revision 返回 409 且不覆盖新值。
- 未确认、确认 revision 过期或确认人缺失时 start 返回 422 `GRAPH_CONFIRMATION_REQUIRED`。
- 只读角色对创建、教材上传、编辑、确认、start、cancel 和 rollback 返回 403。
- 刷新后从数据库恢复 config、textbooks、graph draft、confirmation 和 warnings。

### A2. 强制模型图谱与结构修复

```powershell
Set-Location Edu_AI/api
D:\anaconda\envs\edu-ai\python.exe -m pytest -q `
  src/tests/services/test_course_knowledge_graph_generator.py `
  src/tests/services/test_course_knowledge_planner.py
```

必须覆盖：

- 无教材输入时 LLM adapter 被调用，返回树与 fake model 输出一致。
- 有教材输入时 prompt/结构化 input 包含教材章节、摘要和规模配置。
- ID 唯一、节点类型、深度、循环、空标签、同级重复和规模偏差校验。
- 无语义叶节点“1”“知识点”不会成为可确认草案。
- 首次错误后携带 validation details 修复，最多两次。
- 连续无效或模型不可用时返回稳定错误，不生成/发布 fallback graph。
- 局部重生成保持其他模块 ID 和内容不变。

静态补充检查：

```powershell
rg -n "_fallback_graph|build_course_graph_draft\(" `
  Edu_AI/api/src/app/services/course_knowledge_plan_builder.py `
  Edu_AI/api/src/app/services/course_knowledge_graph_generator.py
```

预期：生产图谱生成/发布链路无硬编码 fallback 调用；若保留兼容 helper，必须不被上述生产路径引用并有弃用说明。

### A3. 教材暂存、解析、拆分和映射

```powershell
Set-Location Edu_AI/api
D:\anaconda\envs\edu-ai\python.exe -m pytest -q `
  src/tests/services/test_course_knowledge_textbook_inputs.py `
  src/tests/test_textbook_knowledge_graph.py `
  src/tests/core/test_course_storage_scope_filters.py
```

必须覆盖：

- `.pdf/.docx/.txt/.md` 前后端契约；未实现格式明确拒绝。
- 上传保存不可变原文件、hash、build ID、用户和解析状态。
- 同 build 重复内容去重；不同 build 可独立引用。
- 解析失败保留原文件，可重试、替换或移除。
- 确认前解析结果不进入 ready 课程知识库和 RAG。
- 确认后章节/页码块映射到叶节点，保存 method/confidence。
- 低置信度块进入 unmapped，不计入覆盖率。
- 预览能从节点资料回到原教材章节/页码。
- 文件路径 containment、大小、类型和危险文件名测试继续通过。

### A4. 网络发现、许可取消、AI 配额与质量门禁

```powershell
Set-Location Edu_AI/api
D:\anaconda\envs\edu-ai\python.exe -m pytest -q `
  src/tests/services/test_course_knowledge_source_discovery.py `
  src/tests/services/test_course_knowledge_plan_builder.py `
  src/tests/services/test_course_knowledge_quality_gate.py
```

必须覆盖：

- 搜索遍历 confirmed graph 的全部叶节点，不只前 6 个。
- 缺失 `license_name/license_url` 且域名不在旧白名单的相关来源仍 selected 并可抓取。
- 非相关、空正文、失败抓取仍按技术/质量原因拒绝。
- URL、最终 URL 和内容 hash 去重。
- 每叶 `textbook/web/model_generated/failure/unmapped` 分开计数。
- `minimum_web=1, web=0`：`web_minimum` 失败、build blocked、无 publish、score 非 100。
- `minimum_web=0, web=0`：`web_minimum` 通过，由总覆盖和 AI 上限继续判定。
- AI 只补真实缺口且不超过每叶上限；关闭 AI 时不调用模型。
- 达到 AI 上限仍缺资料时 blocked。

静态补充检查：

```powershell
rg -n "未找到可验证的开放许可|license_name.*approved|license_url.*approved|_REVIEWED_DOMAIN_POLICIES" `
  Edu_AI/api/src/app/services/course_knowledge_source_discovery.py `
  Edu_AI/api/src/app/services/course_knowledge_plan_builder.py
```

预期：没有把许可/固定许可域名作为批准或发布条件的代码。兼容元数据读取不算失败，但必须由测试证明不影响决策。

### A5. 原子发布、更新策略、取消和幂等

```powershell
Set-Location Edu_AI/api
D:\anaconda\envs\edu-ai\python.exe -m pytest -q `
  src/tests/persistence/test_postgres_knowledge_repository.py `
  src/tests/services/test_course_knowledge_plan_builder.py `
  src/tests/test_course_knowledge_build_workflow.py `
  src/tests/test_job_reconciliation_service.py
```

必须覆盖：

- publish 事务中故障时 graph version、ready 文档和 build 当前版本均不变。
- 重试相同 publish 不重复版本或文档。
- incremental 不删除旧节点；merge 保存迁移映射；full 创建新版本并保留旧版。
- rollback 恢复目标图谱和对应文档可见集合。
- 取消/超时/租约恢复进入稳定终态。
- 重试从 checkpoint 继续，不重复已成功抓取、教材块、AI 资料和索引。

### A6. 前端配置、图谱审核、进度与刷新

```powershell
Set-Location Edu_AI
node --import tsx --test `
  src/stitch/course/knowledge/courseKnowledgeBuildConfig.test.ts `
  src/stitch/course/knowledge/courseKnowledgeBuildState.test.ts `
  src/stitch/course/knowledge/courseKnowledgeGraphDraft.test.ts `
  src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts `
  src/stitch/course/knowledge/courseKnowledgeBuildRefresh.test.ts
```

组件测试如使用 Vitest/React 测试环境，运行仓库对应脚本并在验收记录中写明真实命令。

必须覆盖：

- 预设、手工配置、预计规模和边界错误。
- 教材步骤可跳过，多文件状态、重试和移除。
- 单击创建草案不会立即 start。
- 图谱树编辑、移动、局部重生成、保存、revision 409 和确认提示。
- 未确认时正式构建按钮禁用；后端 422 仍有中文映射。
- 正式进度显示真实阶段和各来源计数。
- blocked 显示具体叶节点缺口与可行动入口。
- job success、rollback、document update 触发 graph/documents/versions/build 重新请求。
- 新数据加载成功后才显示“可用”，不残留空占位根节点。

静态补充检查：

```powershell
rg -n "previewCourseKnowledgeBuild\(courseId\)[\s\S]*startCourseKnowledgeBuild" `
  Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx
```

预期：无匹配。

### A7. 确定性浏览器验收

```powershell
Set-Location Edu_AI
$env:PLAYWRIGHT_PORT='5187'
$env:VITE_API_BASE_URL='http://localhost:8001'
pnpm exec playwright test tests/e2e/course-knowledge-build-wizard.spec.ts --project=desktop1366
```

fixture/stub 场景必须覆盖：

1. 标准配置、无教材、模型图谱、编辑确认、正式构建、成功刷新。
2. 上传 Markdown 教材、显示解析章节、教材影响图谱、教材节点资料可预览。
3. 修改高级规模后刷新恢复相同草案。
4. 未确认直接 start 被阻止，Network 中无 search/crawl 请求。
5. 缺失许可证网络来源入库。
6. 网络为 0 且 minimum=1 时 blocked；调整为 0 并重新确认后可继续。
7. job success 后不 reload 浏览器即可看到新图谱。
8. 只读用户看不到写操作。

### A8. 全量质量门禁

```powershell
Set-Location Edu_AI
npm test
npm run lint
npm run build
```

```powershell
Set-Location Edu_AI/api
D:\anaconda\envs\edu-ai\python.exe -m pytest -q src/tests
```

预期：命令退出码为 0。若仓库既有失败存在，必须在本文件实施结果区记录：完整命令、失败测试、基线提交复现、与 SPEC-14 的隔离结论和本轮专项全绿证据；不能直接写“通过”。

## 6. 真实浏览器与服务端端到端验收

### B1. 无教材标准构建

1. 创建临时课程，填写有语义的名称、简介、教学对象和至少 3 个目标。
2. 新建标准构建方案，不上传教材。
3. 点击生成图谱，记录服务端 LLM 调用事件。
4. 在草案中重命名一个叶节点并移动到另一个模块，保存并确认。
5. 启动正式构建，等待发布。

通过标准：

- 图谱不是课程目标的简单平铺，符合标准规模允许偏差。
- 服务端记录真实模型、prompt version 和 graph revision，不含密钥。
- 确认前无搜索/抓取；确认后对全部叶节点执行搜索。
- 结果逐节点显示来源分类和质量门禁。
- 发布后无需刷新页面即可看到已编辑的真实图谱和资料。

### B2. 含教材构建

1. 新建另一个临时课程，选择小型预设。
2. 上传结构清晰的 Markdown/DOCX 教材和 PDF 教材。
3. 等待逐文件解析完成，检查章节、页码和警告。
4. 生成图谱并检查教材章节在草案中的覆盖/未映射说明。
5. 确认后完成正式构建，从一个叶节点打开教材资料预览。
6. 使用课程问答或检索测试命中该教材内容。

通过标准：

- 教材内容在模型调用前已解析，但确认前不进入 ready RAG。
- 草案能体现教材结构，不是固定模板。
- 原教材、章节/页码、拆分块、节点和检索结果可追溯。
- 低置信度块若存在，只出现在未映射列表。

### B3. 图谱确认硬门禁与修订冲突

1. 打开同一草案的两个浏览器标签。
2. 标签 A 修改并保存图谱。
3. 标签 B 使用旧 revision 保存，随后尝试 start。
4. 标签 A 确认图谱；再次修改配置。

通过标准：

- 标签 B 收到 409，不覆盖 A。
- 未确认 revision 不能 start，后台没有正式 job。
- 确认后修改配置会清除确认状态并返回 graph review。
- 重新确认前没有任何网络、抓取或 AI 动作。

### B4. 无许可元数据网络来源

1. 让搜索 fixture 返回一个相关、可访问、无 `license_name/license_url`、域名不在旧白名单的页面。
2. 正式构建并打开该资料。

通过标准：

- 候选不因许可缺失被拒绝。
- 正文被抓取、清洗、索引并归档到正确叶节点。
- 文档保留标题、URL、域名、抓取时间、查询和内容 hash。
- UI 不显示误导性的“已验证开放许可”；许可字段可为空。

### B5. 网络不足与 AI 上限

执行两次小型构建：

1. `minimum_web_materials_per_leaf=1`、搜索为空、AI 上限 1。
2. 从阻塞结果复制/修订配置，将 minimum web 显式改为 0 并重新确认。

通过标准：

- 第一次构建 blocked，不发布、不显示质量通过、不产生 100 分；AI 不超过每叶 1 份。
- UI 明确指出哪些叶节点缺网络资料。
- 第二次只有在新 revision 被确认后才能重试；是否通过取决于总覆盖和 AI 上限，不受许可检查影响。

### B6. 更新策略、故障与回滚

1. 对 B1 已发布课程执行 incremental，新增一个知识点和网络资料。
2. 执行 merge rebuild，上传新教材并检查节点迁移。
3. 执行 full rebuild，并在发布事务测试环境注入一次失败。
4. 重试成功后回滚到 B1 初始版本。

通过标准：

- incremental 不删除原节点和资料。
- merge 能说明旧节点到新节点的迁移，未匹配资料不被静默错挂。
- 故障时当前版本不变，无半 ready 文档。
- full rebuild 成功创建新版本且旧版本仍在。
- 回滚后图谱和资料集合都与目标版本一致。

### B7. 刷新恢复、取消、权限和数据保护

1. 在网络抓取阶段刷新浏览器，随后离开课程页再回来。
2. 取消一次可取消构建，再重试/新建构建。
3. 用只读用户打开同一课程。
4. 对比验收前后一个不相关现有课程的图谱版本和文档计数。

通过标准：

- 草案和正式任务从后端恢复，不重复创建 build/job。
- 取消进入稳定终态，重试不重复已完成文档或版本。
- 只读用户只能看已发布内容，不能看到可执行写操作，直接 API 调用返回 403。
- 不相关课程数据、历史版本和文档计数没有变化。

## 7. 证据清单

实施完成时必须附上：

- 待验收提交哈希和工作区状态。
- 自动化命令、退出码、通过/失败/跳过数量。
- 无教材和含教材两个 build ID、course ID、graph version。
- 两次构建的规范化 config 和 confirmed graph revision。
- LLM 调用摘要：模型、prompt version、教材输入数量；不得含教材全文或密钥。
- 每个叶节点的 textbook/web/AI/failure/unmapped 统计导出。
- 无许可来源的 URL、document ID 和抓取/索引状态。
- 网络不足 blocked 的 quality checks 和非 100 分证据。
- 原子发布故障前后版本/文档计数。
- 自动刷新前后截图、图谱审核截图、教材预览截图、blocked 截图和回滚截图。
- 临时课程清理或保留说明；不得删除用户课程作为验收清理。

## 8. 实施结果记录模板

> 本节在实现和验收时填写；设计阶段不得预填“通过”。

### 8.1 自动化结果

| 命令 | 结果 | 通过/失败/跳过 | 备注 |
| --- | --- | --- | --- |
| A1 | 待执行 | - | - |
| A2 | 待执行 | - | - |
| A3 | 待执行 | - | - |
| A4 | 待执行 | - | - |
| A5 | 待执行 | - | - |
| A6 | 待执行 | - | - |
| A7 | 待执行 | - | - |
| A8 | 待执行 | - | - |

### 8.2 真实 E2E 结果

| 场景 | Course ID | Build ID | Graph Version | 结果 | 证据 |
| --- | --- | --- | --- | --- | --- |
| B1 无教材 | 待填 | 待填 | 待填 | 待执行 | - |
| B2 含教材 | 待填 | 待填 | 待填 | 待执行 | - |
| B3 确认/冲突 | 待填 | 待填 | - | 待执行 | - |
| B4 无许可来源 | 待填 | 待填 | 待填 | 待执行 | - |
| B5 网络不足 | 待填 | 待填 | - | 待执行 | - |
| B6 更新/回滚 | 待填 | 待填 | 待填 | 待执行 | - |
| B7 恢复/权限 | 待填 | 待填 | - | 待执行 | - |

### 8.3 已知限制

- 待实施后填写。

## 9. 签收规则

只有 AC14-01～AC14-14 全部通过、B1～B7 证据完整且无用户数据破坏时，才能：

1. 将本文件状态改为“通过”；
2. 将 SPEC-14 状态改为“完成，ACC-14 通过”；
3. 更新 `docs/spec/README.md`、`docs/acceptance/README.md` 和 `项目总览地图.md`；
4. 把旧预览即启动和旧教材直改图谱路径标记为已退休。
