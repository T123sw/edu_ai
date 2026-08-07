# 课程工作区可靠性与界面重构实施计划

> **执行方式：** 在当前任务中按顺序连续执行。每项使用测试先行，小步实现，小步验证；界面阶段不等待人工确认，最终统一交付用户检查。

**目标：** 修复课程工作区的任务、生成、资源排序和知识节点 RAG 契约，并完成课程概览、问答与生成、课程知识、AI 课堂、课程资源、课程设置和全局导航的统一美化。

**架构：** 保留现有 `src/stitch` 主运行路径和 hash 路由。以现有生成注册表作为资源类型真源；以后端请求时节点展开作为 RAG 真源；以后端终态收敛作为任务真源；前端只负责呈现和明确的用户交互。

**技术栈：** React 18、TypeScript、Vite 6、FastAPI、Python、SQLite 持久任务、文件型课程存储、Node Test Runner、Pytest、Playwright。

**设计文档：** `docs/superpowers/specs/2026-08-07-course-workspace-reliability-and-ui-refresh-design-cn.md`

---

## 执行约束

1. 不修改或提交用户/运行数据：
   - `Edu_AI/api/course_data/courses/computational-thinking/knowledge_base/index.json`
   - `Edu_AI/api/data/`
2. 当前未提交的生成服务和测试修改属于已有起始补丁。先审查和验证，不覆盖、不回退。
3. 所有生产修改先有失败测试；修复后运行聚焦测试，再运行阶段回归。
4. 不删除持久任务库来消除幽灵任务。
5. 每次提交只暂存当前任务涉及的代码；不得使用 `git add .`。
6. 前后端保持可启动；涉及任务存储结构时先停止后端，完成迁移测试后再重启。

## 计划文件地图

主要修改区域：

- 全局课程框架：`Edu_AI/src/stitch/course/*`、`Edu_AI/src/stitch/styles.css`
- 页面：`Edu_AI/src/stitch/pages/*`
- 问答来源：`Edu_AI/src/components/teacher/SourcePanel.tsx`、`ChatPanel.tsx`
- 生成工厂：`Edu_AI/src/components/teacher/generation/*`、`StudioPanel.tsx`
- 后台任务：`Edu_AI/src/jobs/*`
- 前端课程 API：`Edu_AI/src/stitch/api/*`、`Edu_AI/src/services/teacher/*`
- 后端课程 API：`Edu_AI/api/src/app/api/courses.py`
- 后端聊天/生成契约：`Edu_AI/api/src/app/chat/api/*`、`Edu_AI/api/src/app/services/generation_*`
- 持久任务：`Edu_AI/api/src/app/chat/tasks/task_store.py`、`Edu_AI/api/src/app/services/durable_*`
- 课程存储：`Edu_AI/api/src/core/course_storage.py`
- 验收记录：`docs/acceptance/2026-08-08-course-workspace-reliability-and-ui-refresh.md`

---

### Task 1：冻结基线并保护现有改动

**文件：**

- 读取：`AGENTS.md`
- 读取：`项目总览地图.md`
- 读取：设计文档
- 修改：无

- [ ] 记录 `git status --short`，将运行数据和已有生成补丁分类。
- [ ] 确认前端 `http://127.0.0.1:5173`、后端 `http://127.0.0.1:8001/docs` 可访问。
- [ ] 运行当前聚焦前端测试，保存通过数量。
- [ ] 运行当前聚焦后端测试，记录旧 `current_user` 测试签名失败。
- [ ] 运行前端生产构建，记录现有警告。
- [ ] 不提交任何运行数据。

**命令：**

```powershell
git status --short
cd Edu_AI
node --import tsx --test src/jobs/jobPolling.test.ts src/jobs/jobPresentation.test.ts src/stitch/pages/courseResourcesManagement.test.ts src/stitch/api/courseMaterialPresentation.test.ts tests/frontend/sourcePanel.rag-participation.test.ts tests/frontend/knowledgeGraphWorkspaceJump.test.ts
npm.cmd run build
cd api/src
D:\anaconda\envs\edu-ai\python.exe -m pytest -q tests/test_job_reconciliation_service.py tests/test_durable_executor_pool.py tests/core/test_course_storage_generated_materials.py tests/chat/test_courses_rag_v2_document_resolution.py
```

**通过条件：** 基线结果可复现，工作区分类明确，没有文件被意外覆盖。

---

### Task 2：让持久任务必定收敛到终态

**文件：**

- 修改：`Edu_AI/api/src/app/chat/tasks/task_store.py`
- 修改：`Edu_AI/api/src/app/services/durable_task_executor.py`
- 修改：`Edu_AI/api/src/app/services/durable_executor_pool.py`
- 修改：`Edu_AI/api/src/app/services/job_reconciliation_service.py`
- 修改：`Edu_AI/api/src/app/services/durable_job_runtime.py`
- 测试：`Edu_AI/api/src/tests/test_durable_task_store.py`
- 测试：`Edu_AI/api/src/tests/test_durable_task_executor.py`
- 测试：`Edu_AI/api/src/tests/test_durable_executor_pool.py`
- 测试：`Edu_AI/api/src/tests/test_job_reconciliation_service.py`
- 测试：`Edu_AI/api/src/tests/test_job_worker_lifespan.py`

- [ ] 写失败测试：没有 deadline 的旧任务在协调时获得有界期限，不能永久 pending。
- [ ] 写失败测试：租约反复过期达到最大次数后转为失败，错误码稳定。
- [ ] 写失败测试：worker 单次 claim/handler 异常不会杀死整个循环。
- [ ] 写失败测试：任务账本显示 queued、持久任务已过期或不存在时能够收敛。
- [ ] 为所有新生成任务保证默认 300 秒 deadline；为旧任务做非破坏性协调。
- [ ] 在 worker 顶层循环增加异常隔离、日志和健康状态。
- [ ] 将恢复次数、截止时间和终态同步回统一任务账本。
- [ ] 用临时 SQLite 数据库构造幽灵任务，验证不需要删除数据库即可收敛。
- [ ] 运行聚焦测试和全部任务系统测试。

**通过条件：** queued/running 任务在成功、失败、取消或截止时间中择一终止；worker 异常后仍能处理下一任务。

**提交建议：** `fix(jobs): guarantee durable task convergence`

---

### Task 3：停止无意义轮询并中文化任务错误

**文件：**

- 修改：`Edu_AI/src/jobs/GlobalJobManager.tsx`
- 修改：`Edu_AI/src/jobs/jobPolling.ts`
- 修改：`Edu_AI/src/jobs/jobPresentation.ts`
- 修改：`Edu_AI/src/jobs/JobCenterDrawer.tsx`
- 修改：`Edu_AI/src/jobs/JobCenterTrigger.tsx`
- 测试：`Edu_AI/src/jobs/jobPolling.test.ts`
- 测试：`Edu_AI/src/jobs/jobPresentation.test.ts`
- 测试：`Edu_AI/src/jobs/jobCenterLayout.test.ts`
- 测试：`Edu_AI/api/src/tests/test_jobs_api_v2.py`

- [ ] 写失败测试：全部任务终态后 `nextDelay` 返回空，不再定时请求。
- [ ] 写失败测试：英文技术错误按 `error_code` 映射为中文原因与建议。
- [ ] 写失败测试：未知错误不显示原始堆栈，只显示稳定兜底和任务 ID。
- [ ] 如接口需要，给任务列表增加 `active_only` 查询；首次加载取完整摘要，后续只轮询活动任务。
- [ ] 任务终态变化后做一次最终刷新，然后停止轮询。
- [ ] 将通知、抽屉卡片和重试提示统一接入错误呈现器。
- [ ] 在日志中保留原始技术错误，界面只消费用户错误对象。
- [ ] 运行任务前后端测试。

**通过条件：** 浏览器网络面板在无活动任务时保持安静；用户界面不出现 `selected_doc_ids is required` 等英文原文。

**提交建议：** `fix(jobs): stop terminal polling and localize errors`

---

### Task 4：统一九类生成来源契约并验证可靠性矩阵

**文件：**

- 审查/修改：`Edu_AI/api/src/app/chat/api/routes_v2.py`
- 审查/修改：`Edu_AI/api/src/app/chat/application/knowledge_base_direct_*_service_v2.py`
- 审查/修改：`Edu_AI/api/src/app/services/generation_task_handlers.py`
- 修改：`Edu_AI/api/src/app/services/generation_source_resolver.py`
- 修改：`Edu_AI/api/src/app/services/generation_command.py`
- 修改：`Edu_AI/src/components/teacher/generation/generationSourceSelection.ts`
- 测试：现有 `test_direct_*_service_v2.py`
- 测试：`Edu_AI/api/src/tests/test_generation_task_handlers.py`
- 测试：`Edu_AI/api/src/tests/acceptance/test_generation_reliability_matrix.py`

- [ ] 审查当前未提交的报告、PPT、习题、闪卡、思维导图和游戏修复差异。
- [ ] 写/补失败测试：空显式文档选择但存在合法课程范围时，各类生成不会错误要求 `selected_doc_ids`。
- [ ] 写/补失败测试：确实需要来源但没有任何可用来源时，返回稳定 `SOURCE_SELECTION_REQUIRED`。
- [ ] 让九类生成命令共用同一来源解析和 provenance 结构。
- [ ] 确认请求成功返回 202，任务结果保存真实 material target。
- [ ] 使用 fake providers 跑九类可靠性矩阵，不依赖真实大模型费用。
- [ ] 选择一类文本资源和 AI 课堂做真实本地冒烟测试。
- [ ] 只暂存已审查且通过测试的现有起始补丁。

**通过条件：** 九类资源均能从请求进入后台任务并形成可定位的结果；失败时错误码一致且可读。

**提交建议：** `fix(generation): unify source resolution across resource types`

---

### Task 5：建立真实资源目录与服务端排序

**文件：**

- 修改：`Edu_AI/src/components/teacher/generation/generationRegistry.ts`
- 修改：`Edu_AI/src/stitch/api/courseMaterialPresentation.ts`
- 修改：`Edu_AI/src/stitch/api/courses.ts`
- 修改：`Edu_AI/src/stitch/pages/CourseResources.tsx`
- 修改：`Edu_AI/api/src/app/api/courses.py`
- 修改：`Edu_AI/api/src/core/course_storage.py`
- 测试：`Edu_AI/src/stitch/api/courseMaterialPresentation.test.ts`
- 测试：`Edu_AI/src/stitch/pages/courseResourcesManagement.test.ts`
- 测试：`Edu_AI/api/src/tests/core/test_course_storage_generated_materials.py`
- 测试：`Edu_AI/tests/e2e/resources-and-classroom.spec.ts`

- [ ] 写失败测试：筛选项与九类注册表一一对应，不包含“互动”。
- [ ] 写失败测试：`updated_desc` 严格按更新时间，置顶不改变顺序。
- [ ] 写失败测试：`name_asc/name_desc` 对中文、数字和同名资源结果稳定。
- [ ] 后端材料接口增加显式 sort 参数并验证非法值。
- [ ] 将置顶改为独立筛选/标记，前端删除二次排序。
- [ ] 统一概览、任务结果和资源页的 material target 深链接。
- [ ] 验证“最近更新”和“按名称”在至少五条乱序夹具上有明显差异。

**通过条件：** 分类、排序和跳转均由测试及实机数据证明有效。

**提交建议：** `fix(resources): align catalog and deterministic sorting`

---

### Task 6：重构共享课程顶栏和左侧导航

**文件：**

- 修改：`Edu_AI/src/stitch/course/CourseShell.tsx`
- 修改：`Edu_AI/src/stitch/course/courseNavigation.ts`
- 修改：`Edu_AI/src/stitch/styles.css`
- 测试：`Edu_AI/src/stitch/course/courseNavigation.test.ts`
- 测试：`Edu_AI/tests/frontend/coursePermissionRendering.test.ts`
- 测试：`Edu_AI/tests/e2e/course-shell.spec.ts`
- 测试：`Edu_AI/tests/e2e/keyboard-accessibility.spec.ts`

- [ ] 写失败测试：六个课程页面顶栏都包含后台任务和个人中心。
- [ ] 写失败测试：导航不再渲染课程身份卡和说明小字。
- [ ] 写失败测试：移动端抽屉和桌面侧栏使用相同菜单数据。
- [ ] 把个人中心入口放进共享顶栏，和任务按钮统一尺寸。
- [ ] 删除身份卡和导航描述，放大字体及点击区域。
- [ ] 调整共享字体、间距、焦点、悬停和选中状态。
- [ ] 在 1024、1366、1440、1920 宽度检查顶栏不换行、不遮挡。

**通过条件：** 所有课程页只存在一套课程上下文和一套顶栏操作。

**提交建议：** `feat(course-shell): unify header and navigation`

---

### Task 7：完成课程概览与课程设置

**文件：**

- 修改：`Edu_AI/src/stitch/pages/CourseDetail.tsx`
- 修改：`Edu_AI/src/stitch/pages/CourseEdit.tsx`
- 修改：`Edu_AI/src/stitch/styles.css`
- 修改：`Edu_AI/src/stitch/api/courses.ts`
- 测试：`Edu_AI/tests/frontend/courseRouteAcceptance.test.ts`
- 测试：`Edu_AI/tests/frontend/profile-kb-courseedit-replacement.test.ts`
- 测试：`Edu_AI/tests/e2e/core-pages.spec.ts`

- [ ] 写失败测试：课程概览无角色提示、无课程版本、常用入口无课程概览。
- [ ] 写失败测试：五张统计卡显示课程资料、课程资源和已完成/进行中/失败任务，课程资料卡同时显示可检索数。
- [ ] 写失败测试：最近资源限制数量、严格最新优先并包含可点击 target。
- [ ] 删除重复和冗余内容，按设计提高正文、目标和入口字号。
- [ ] 给最新资源容器固定尺寸和内部边界，数据增加不拉长页面。
- [ ] 重构设置页分组、保存状态、冲突和错误提示，不改变 PUT 语义。
- [ ] 实机修改名称、简介和目标，刷新概览验证同步。

**通过条件：** 概览所有业务数字可由接口核对；设置保存后跨页面一致。

**提交建议：** `feat(courses): refresh overview and settings`

---

### Task 8：实现后端知识节点资料与 RAG 递归契约

**文件：**

- 修改：`Edu_AI/api/src/app/api/courses.py`
- 修改：`Edu_AI/api/src/app/chat/api/schemas_v2.py`
- 修改：`Edu_AI/api/src/app/chat/api/routes_v2.py`
- 修改：`Edu_AI/api/src/app/chat/application/*` 中公共请求归一化路径
- 修改：`Edu_AI/api/src/app/services/generation_source_resolver.py`
- 修改：`Edu_AI/api/src/core/course_storage.py`
- 测试：`Edu_AI/api/src/tests/core/test_course_storage_scope_filters.py`
- 测试：`Edu_AI/api/src/tests/chat/test_courses_rag_v2_document_resolution.py`
- 测试：`Edu_AI/api/src/tests/chat/test_main_query_selected_doc_resolution.py`
- 新增：`Edu_AI/api/src/tests/chat/test_knowledge_point_selection_resolution.py`

- [ ] 先修复旧 `current_user` 测试调用与当前 principal 契约不一致的基线问题。
- [ ] 写三层树失败测试：父节点包含自身和全部后代。
- [ ] 写失败测试：子节点不包含父节点和兄弟节点。
- [ ] 写失败测试：父子重叠选择按稳定文档 ID 去重。
- [ ] 写失败测试：父节点被保存后新增子节点资料，下一次请求自动包含。
- [ ] 写失败测试：跨课程节点和无权限节点被拒绝。
- [ ] 给问答/生成契约增加 `selected_knowledge_point_ids`。
- [ ] 在请求时统一展开节点并解析当前可检索资料，不持久化扁平快照作为唯一真源。
- [ ] 保存原始节点选择和实际证据清单。
- [ ] 验证上传课程节点仍由 `require_course_edit` 保护。

**通过条件：** 父子语义完全由后端测试证明；前端不能通过伪造文档 ID 绕过课程权限。

**提交建议：** `feat(rag): resolve knowledge point selections server-side`

---

### Task 9：重构课程知识图谱与课程知识库页面

**文件：**

- 修改：`Edu_AI/src/stitch/pages/CourseKnowledge.tsx`
- 修改：`Edu_AI/src/stitch/pages/KnowledgeGraph.tsx`
- 修改：`Edu_AI/src/stitch/pages/CourseKnowledgeBase.tsx`
- 修改：`Edu_AI/src/stitch/styles.css`
- 修改：`Edu_AI/src/stitch/api/courses.ts`
- 测试：`Edu_AI/tests/frontend/stitchKnowledgeGraph.scope-link.test.ts`
- 测试：`Edu_AI/tests/frontend/knowledgeGraph.node-course-kb-upload.test.ts`
- 测试：`Edu_AI/tests/frontend/knowledgeBase.dual-library.test.ts`
- 测试：`Edu_AI/tests/e2e/course-knowledge.spec.ts`
- 测试：`Edu_AI/tests/e2e/overflow-regression.spec.ts`

- [ ] 写失败测试：默认 view 是知识图谱，标签顺序正确。
- [ ] 写失败测试：图谱页不显示课程学时/编辑/上传区。
- [ ] 写失败测试：节点资料区聚合后代、显示实际所属节点并内部滚动。
- [ ] 写失败测试：上传入口仅教师可见，上传请求携带节点 scope。
- [ ] 删除重复课程知识库标题和“已接收”状态。
- [ ] 将课程资料页的类型分类改为知识节点选择和最新在前列表。
- [ ] 保留“和 AI 聊一聊”，生成带节点选择的问答工作台地址。
- [ ] 实机上传父节点和叶子节点资料，验证父节点聚合展示。

**通过条件：** 进入课程知识即看到图谱；图谱只展示；课程知识库负责节点资料管理。

**提交建议：** `feat(knowledge): organize course materials by graph node`

---

### Task 10：重构问答知识库选择与节点跳转

**文件：**

- 修改：`Edu_AI/src/components/teacher/SourcePanel.tsx`
- 修改：`Edu_AI/src/components/teacher/ChatPanel.tsx`
- 修改：`Edu_AI/src/stitch/pages/AIWorkspace.tsx`
- 修改：`Edu_AI/src/services/teacher/chatV2.ts`
- 修改：`Edu_AI/src/stitch/styles.css`
- 测试：`Edu_AI/tests/frontend/sourcePanel.workspace-scope.test.ts`
- 测试：`Edu_AI/tests/frontend/sourcePanel.rag-participation.test.ts`
- 测试：`Edu_AI/tests/frontend/chatPanel.scoped-default-docs.test.ts`
- 测试：`Edu_AI/tests/frontend/stitchAIWorkspace.scope.test.ts`

- [ ] 写失败测试：课程库/个人库使用顶部标签切换而非上下堆叠。
- [ ] 写失败测试：课程节点勾选发送 `selected_knowledge_point_ids`，不只发送展开后的文档快照。
- [ ] 写失败测试：图谱跳转后预选节点并保持其 RAG 参与状态。
- [ ] 写失败测试：新资料按时间倒序，“已接收”不出现。
- [ ] 重构 SourcePanel 状态模型，区分节点选择、显式文档选择和个人库选择。
- [ ] ChatPanel 请求同时发送节点选择与显式文档选择。
- [ ] 对话历史恢复保留选择器，旧记录继续兼容 selected_doc_ids。
- [ ] 单个对话详情加载失败只影响该区域，不破坏整个页面。

**通过条件：** 父节点选择的请求契约可在网络请求和后端解析测试中同时确认。

**提交建议：** `feat(workspace): add node-aware rag source selection`

---

### Task 11：把生成工厂改成卡片入口与简洁弹窗

**文件：**

- 修改：`Edu_AI/src/components/teacher/generation/GenerationFactory.tsx`
- 修改：`Edu_AI/src/components/teacher/generation/generationRegistry.ts`
- 修改：`Edu_AI/src/components/teacher/generation/definitions/*.tsx`
- 修改：`Edu_AI/src/components/teacher/StudioPanel.tsx`
- 修改：`Edu_AI/src/stitch/pages/AIWorkspace.tsx`
- 修改：`Edu_AI/src/stitch/styles.css`
- 测试：`Edu_AI/src/components/teacher/generation/generationRegistry.test.ts`
- 测试：`Edu_AI/src/components/teacher/generation/definitions/*.test.ts`
- 测试：`Edu_AI/tests/frontend/studioPanel.*.test.ts`
- 测试：`Edu_AI/tests/e2e/generation-factory-shell.spec.ts`

- [ ] 写失败测试：不存在步骤 1/4、上一步和下一步交互。
- [ ] 写失败测试：九类工具均为独立入口，桌面端每行三个。
- [ ] 写失败测试：每类配置只展示现有必需/高频字段，高级字段有真实默认值。
- [ ] 提取统一 GenerationToolModal；点击卡片直接打开对应定义。
- [ ] 提交后关闭弹窗并把任务加入最近生成列表。
- [ ] 最近列表严格最新在前，包含排队、进行中、完成和失败，固定高度内部滚动。
- [ ] 删除卡片小字说明，放大工具名称。
- [ ] 对九个工具逐一做打开、校验、提交测试。

**通过条件：** 九个入口都能以一次弹窗完成配置并转入后台任务，不再出现向导。

**提交建议：** `feat(generation): replace wizard with tool modals`

---

### Task 12：完成固定问答工作台布局

**文件：**

- 修改：`Edu_AI/src/stitch/pages/AIWorkspace.tsx`
- 修改：`Edu_AI/src/components/teacher/SourcePanel.tsx`
- 修改：`Edu_AI/src/components/teacher/ChatPanel.tsx`
- 修改：`Edu_AI/src/components/teacher/StudioPanel.tsx`
- 修改：`Edu_AI/src/stitch/styles.css`
- 测试：`Edu_AI/tests/frontend/aiWorkspaceEntryLayout.test.ts`
- 测试：`Edu_AI/tests/frontend/chatPanel.layout.test.ts`
- 测试：`Edu_AI/tests/frontend/studioPanel.responsive-layout.test.ts`
- 测试：`Edu_AI/tests/e2e/overflow-regression.spec.ts`

- [ ] 写失败测试：删除内部课程信息横条和生成工厂/个人中心重复按钮。
- [ ] 写失败测试：页面级容器固定为顶栏以下高度且 overflow hidden。
- [ ] 写失败测试：三个面板分别具有内部滚动边界。
- [ ] 调整列宽，优先扩大对话区；在较窄桌面宽度使用可折叠左右栏。
- [ ] 保证消息列表、资料列表和最近生成列表独立滚动，输入区始终可见。
- [ ] 在 1366×768、1440×900、1920×1080 实机检查。

**通过条件：** 1366×768 及以上桌面视口没有页面级纵向滚动，核心操作无需滚动页面即可使用。

**提交建议：** `feat(workspace): deliver fixed three-panel layout`

---

### Task 13：简化 AI 课堂生成入口

**文件：**

- 修改：`Edu_AI/src/stitch/pages/ClassroomStudio.tsx`
- 修改：`Edu_AI/src/components/teacher/ClassroomGenerationEntry.tsx`
- 修改：`Edu_AI/src/openmaic/classroomGenerationFlow.ts`
- 修改：`Edu_AI/src/stitch/styles.css`
- 测试：`Edu_AI/src/openmaic/classroomGenerationFlow.test.ts`
- 测试：`Edu_AI/src/openmaic/classroomGenerationRecovery.test.ts`
- 测试：`Edu_AI/tests/e2e/resources-and-classroom.spec.ts`

- [ ] 写失败测试：首屏只要求研究主题，其他字段使用 schema 默认值。
- [ ] 写失败测试：不再渲染返回课程详情、重复课程名、AI 课件生成标题和内嵌完成进度块。
- [ ] 让简洁入口复用现有后台任务提交与恢复链路。
- [ ] 任务状态只在全局任务中心和最近生成区域展示。
- [ ] 保留已生成课堂列表和播放器跳转。
- [ ] 实机只填写主题提交一次，验证资源最终可播放。

**通过条件：** 用户只填写研究主题即可开始；页面不再像长表单。

**提交建议：** `feat(classroom): simplify generation to topic-first flow`

---

### Task 14：整体验收、浏览器巡检与交付记录

**文件：**

- 新增：`docs/acceptance/2026-08-08-course-workspace-reliability-and-ui-refresh.md`
- 更新：必要的 Playwright 测试和有意变更的视觉快照

- [ ] 运行全部前端单元测试。
- [ ] 运行前端 lint 和生产构建。
- [ ] 运行全部相关后端测试，再运行完整 Pytest；将非本轮遗留失败单独记录。
- [ ] 运行课程壳层、知识页、生成、资源、AI 课堂、溢出和键盘 E2E。
- [ ] 用真实本地前后端逐页巡检：课程概览、问答与生成、知识图谱、课程知识库、AI 课堂、课程资源、课程设置。
- [ ] 在 1920、1440、1366、1024 宽度检查；问答页额外检查 1366×768。
- [ ] 核对空状态、加载状态、权限不足、生成失败、长标题、大量资料和大量资源。
- [ ] 确认没有持续任务轮询，没有 raw English errors，没有非预期页面滚动。
- [ ] 记录每个页面的访问地址、完成项、测试结果和仍需用户审美判断的内容。
- [ ] 运行 `git diff --check` 和 `git status --short`，确认运行数据仍未被提交。

**最终命令：**

```powershell
cd Edu_AI
npm.cmd test
$frontendTestFiles = Get-ChildItem tests/frontend -Filter *.test.ts | ForEach-Object { $_.FullName }
node --import tsx --test $frontendTestFiles
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e -- tests/e2e/course-shell.spec.ts tests/e2e/course-knowledge.spec.ts tests/e2e/generation-factory-shell.spec.ts tests/e2e/resources-and-classroom.spec.ts tests/e2e/overflow-regression.spec.ts tests/e2e/keyboard-accessibility.spec.ts
cd api/src
D:\anaconda\envs\edu-ai\python.exe -m pytest -q
cd ../../..
git diff --check
git status --short
```

**通过条件：** 自动化验收和实机巡检完成；验收文档足以让用户次日一次性检查完整前端。

**提交建议：** `test(course-workspace): complete integrated acceptance`

---

## 阶段门禁汇总

| 阶段 | 自动门禁 | 是否等待人工确认 |
|---|---|---|
| 0 基线 | 状态、构建、聚焦测试可复现 | 否 |
| 1 可靠性 | 九类生成矩阵、任务终态、轮询、中文错误、排序 | 否 |
| 2 框架与基础页 | 共享壳层、概览/设置/资源 E2E、多宽度 | 否 |
| 3 知识与 RAG | 三层树递归、去重、权限、跳转和内部滚动 | 否 |
| 4 问答与生成 | 九入口、固定三栏、AI 课堂主题生成 | 否 |
| 5 整体 | 全部测试、构建、逐页浏览器巡检和验收记录 | 最终统一检查 |

## 交付物

1. 设计 Spec。
2. 本实施计划及勾选进度。
3. 分阶段代码提交。
4. 自动化测试和生成可靠性矩阵。
5. 最终验收记录。
6. 保持运行的本地前后端，供用户次日直接检查。
