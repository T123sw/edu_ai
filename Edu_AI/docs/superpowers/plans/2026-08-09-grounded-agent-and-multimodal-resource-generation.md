# Grounded Agent and Multimodal Resource Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan.

**Goal:** 完成教师端基础功能闭环，使知识来源、RAG/Web 工具、八类非 PPT 资源生成、图文链路、思维导图和资源编辑导出都真实可用并可端到端验证。

**Architecture:** 用确定性的来源与检索指令约束 Agent，模型只负责内容规划；资源生成共享来源解析和视觉资产流水线；前端配置通过类型化定义序列化到后台任务，结果统一落入课程资源中心。先修复 P0 编排，再打通来源与资源契约，最后接入图文、编辑与完整验收。

**Tech Stack:** React 18、TypeScript、Zustand、FastAPI、Pydantic、Python、现有 Agent runtime、RAG v2、Bocha、Playwright、Node test、pytest。

**Global Constraints:** PPT 与学生端后置；保留当前工作区已有知识库改动；所有行为改动必须先写失败测试；不展示不可用功能；强制检索失败时禁止伪装成已检索回答；直接写接口必须服务端鉴权。

## 执行状态（2026-08-09）

| 任务 | 状态 | 结果 |
|---|---|---|
| Task 1—6：Agent、来源与权限 | 已完成 | 检索前置、证据门禁、三种来源语义、跨课程校验、直接端点鉴权均已落地 |
| Task 7：八类配置 | 已完成 | 非 PPT 八类配置精简，所有可见字段进入真实请求或生成提示 |
| Task 8—10：通用图文链路 | 已完成 | Visual Brief、知识库/网页候选、安全本地化、去重排序、锁定图片带入正文和组装已落地 |
| Task 11：思维导图 | 已完成 | 稳定节点 ID、递归预览、缩放、增删改与 JSON 导出已落地 |
| Task 12：资源编辑导出 | 已完成 | 七类安全内容编辑；Markdown/JSON 导出；游戏 HTML 编辑明确不开放 |
| Task 13：自动化 E2E | 已完成 | 两种窗口尺寸共 18 条教师端浏览器用例通过 |
| Task 14：真实服务与回归 | 自动化完成、外部冒烟待部署 | 两个安全冒烟脚本及 6 项自测完成；后端 1252 passed、前端 216 passed、E2E 18 passed、构建与静态检查通过；当前环境无教师令牌/博查配置，未伪造真实供应商结果 |
| Task 15：交付审查 | 已完成 | `git diff --check` 通过；保留用户原有未提交知识库改动；未在共享脏工作区创建混合提交 |

实现过程中未执行各任务末尾的提交命令：当前 `main` 含用户未提交的知识库工作，自动拆分提交会混入或遗漏其改动。代码与验收证据保留在工作区，由用户统一审阅后提交。

---

## Task 1: 建立验收基线和统一测试入口

**Files:**
- Create: `api/src/tests/chat/runtime/test_grounded_tool_orchestration.py`
- Create: `tests/e2e/teacher-functional-acceptance.spec.ts`
- Modify: `docs/acceptance/2026-08-09-grounded-agent-and-multimodal-resource-generation.md`
- Interfaces: Agent runtime trace；Playwright 教师课程页；验收结果表

- [ ] 写一个复现现场问题的后端测试：计划第一步为回答、第二步为 `rag_search`，断言规范化后检索必须第一。
- [ ] 运行该测试并确认因当前错误顺序而失败：`python -m pytest api/src/tests/chat/runtime/test_grounded_tool_orchestration.py -q`。
- [ ] 写 Playwright 验收骨架，覆盖问答来源、八类非 PPT 资源和资源中心，不添加宽泛跳过。
- [ ] 运行单个 E2E 文件确认能加载现有教师工作台，并把基线结果写入验收文档。
- [ ] 提交文档与失败测试：`git add ... && git commit -m "test: establish teacher functional acceptance baseline"`。

## Task 2: 修复规划器的强制检索顺序

**Files:**
- Modify: `api/src/app/chat/runtime/nodes/planner.py`
- Modify: `api/src/tests/chat/runtime/test_mandatory_retrieval_plan.py`
- Modify: `api/src/tests/chat/runtime/test_grounded_tool_orchestration.py`
- Interfaces: `_ensure_mandatory_retrieval_when_enabled(plan_dict, capability)`；规范化计划步骤

- [ ] 增加失败测试：已有检索步骤位于回答后时必须移动到首个内容步骤前；RAG+Web 必须合并在同一检索步骤；重复检索步骤必须去重。
- [ ] 运行目标测试并确认 RED。
- [ ] 最小修改计划规范化逻辑：识别回答/总结/正文/资源生成步骤，合并 required tools，把检索步骤稳定移动到前面。
- [ ] 运行目标测试确认 GREEN，再运行 `api/src/tests/chat/runtime/test_mandatory_retrieval_plan.py` 全部用例。
- [ ] 将规范化后的步骤写入 UI 使用的同一个 plan 对象，禁止展示原始错误计划。
- [ ] 提交：`git commit -m "fix: place required retrieval before agent answers"`。

## Task 3: 增加执行器证据门禁和 fail-closed 语义

**Files:**
- Create: `api/src/app/chat/runtime/retrieval_directive.py`
- Modify: `api/src/app/chat/runtime/nodes/executor.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/retrieval.py`
- Modify: `api/src/app/chat/domain/state.py`（若实际状态定义位于其他文件，以搜索到的唯一 `AgentState` 为准并回填本文档）
- Create/Modify: `api/src/tests/chat/runtime/test_grounded_tool_orchestration.py`
- Interfaces: `RetrievalDirective`；`_build_mandatory_retrieval_calls`；工具结果 evidence；final answer gate

- [ ] 写失败测试：即使当前 plan step 没有 `expected_tools`，开启的 RAG/Web 仍必须先调用。
- [ ] 写失败测试：required tool 未完成、报错或零 evidence 时禁止输出 final answer；两个 required tools 都成功后才能回答。
- [ ] 运行目标测试并确认 RED。
- [ ] 建立简单不可变 `RetrievalDirective`，从 capability/request 计算 required tools、来源范围、文档 ID 和 query。
- [ ] 让 executor 在每轮 LLM 前先补齐 required tools，不再受当前步骤遗漏影响。
- [ ] 统一 RAG/Web handler 的成功结构，明确 `evidence_count`、`sources`、`status`。
- [ ] 在 final 分支加入证据门禁，失败时返回可见错误卡和可重试状态。
- [ ] 运行目标测试、chat runtime 回归并提交：`git commit -m "fix: gate agent answers on required evidence"`。

## Task 4: 统一问答来源模式与请求契约

**Files:**
- Modify: `src/components/teacher/ChatPanel.tsx`
- Modify: `api/src/app/chat/api/schemas_v2.py`
- Modify: `api/src/app/chat/api/routes_v2.py`
- Modify: `api/src/app/chat/runtime/retrieval_policy.py`
- Create/Modify: `src/components/teacher/ChatPanel.test.ts`
- Create/Modify: `api/src/tests/chat/test_course_scope_routes.py`
- Interfaces: `source_mode`、`selected_doc_ids`、`allow_rag`、`allow_web`

- [ ] 写前端失败测试：RAG 关闭=`none`；开启且有选中=`selected_documents`；开启且无选中=`course_auto`。
- [ ] 写后端失败测试：三种来源模式校验、跨课程文档拒绝、请求轨迹保存最终来源模式。
- [ ] 运行测试确认 RED。
- [ ] 给 Chat 请求增加显式 `source_mode`，保留旧 `allow_rag` 的兼容推导但以新字段为准。
- [ ] 调整 ChatPanel 请求构造与 UI 文案，让“RAG知识库”状态与来源范围一致。
- [ ] 确保 selected 模式把文档过滤传到 RAG retriever，course_auto 不传文档白名单但固定课程 scope。
- [ ] 运行前后端目标测试并提交：`git commit -m "feat: unify chat knowledge source semantics"`。

## Task 5: 左侧选择自动驱动资源生成来源

**Files:**
- Modify: `src/components/teacher/generation/GenerationFactory.tsx`
- Modify: `src/components/teacher/generation/GenerationSourceSelector.tsx`
- Modify: `src/components/teacher/generation/generationFactory.css`
- Modify: `src/components/teacher/generation/GenerationSourceSelector.test.ts`
- Modify: `tests/e2e/generation-factory-shell.spec.ts`
- Interfaces: teacher store `selectedDocs`；`GenerationSourceSelection`

- [ ] 写失败测试：打开弹窗时有左侧选择则默认 selected 并带入 ID，无选择则默认 none；重新打开重取快照。
- [ ] 写失败测试：显式“使用课程全部资料”清空 selected IDs；切回 selected 恢复当前打开时快照。
- [ ] 运行测试确认 RED。
- [ ] GenerationFactory 读取 teacher store，在 `open()` 时构造来源快照，不在组件挂载时默认 course_auto。
- [ ] 把资料范围摘要改为“已选 N 份 / 使用课程全部资料 / 不使用知识库”，减少展开前的不确定性。
- [ ] 保留弹窗内文档选择，但只显示 ready 文档并清楚标识左侧自动带入。
- [ ] 运行单元和工厂 E2E，提交：`git commit -m "fix: carry selected knowledge into resource generation"`。

## Task 6: 服务端统一预检、直接端点权限与检索式来源解析

**Files:**
- Modify: `api/src/app/services/generation_source_resolver.py`
- Modify: `api/src/app/services/generation_command.py`
- Modify: `api/src/app/chat/api/routes_v2.py`
- Modify: `api/src/app/api/courses.py`
- Modify: `api/src/tests/services/test_generation_source_resolver.py`
- Modify: `api/src/tests/chat/test_course_scope_routes.py`
- Interfaces: generation preflight；direct endpoints；course permission service；RAG query

- [ ] 写失败测试：course_auto 不能把所有文档全文拼成 context，而应形成可检索 scope；selected 只检索指定文档。
- [ ] 写失败测试：绕过 preflight 直接调用八类生成端点时，无权限和跨课程文档均被拒绝。
- [ ] 运行测试确认 RED。
- [ ] 把来源 resolver 拆成“验证/快照”和“按 query 检索上下文”，禁止 course_auto 读取全部全文。
- [ ] 抽取直接生成端点共用的课程生成权限依赖，并应用到 report、lesson-plan、blog、quiz、flashcard、graph、game、classroom。
- [ ] 确保任务 payload 保存 source snapshot 与实际检索结果摘要。
- [ ] 运行服务与路由测试并提交：`git commit -m "fix: enforce generation source and course permissions"`。

## Task 7: 精简并验证八类非 PPT 资源配置

**Files:**
- Modify: `src/components/teacher/generation/definitions/{report,lessonPlan,blog,quiz,flashcard,game,mindMap,classroom}.ts`
- Modify: `src/components/teacher/generation/forms/{ReportForm,LessonPlanForm,BlogForm,QuizForm,FlashcardForm,GameForm,MindMapForm,ClassroomForm}.tsx`
- Modify: `src/components/teacher/generation/GenerationConfigShell.tsx`
- Modify: `src/components/teacher/generation/generationFactory.css`
- Modify: `api/src/app/chat/api/schemas_v2.py`
- Modify: `api/src/app/services/generation_task_handlers.py`
- Create/Modify: `src/components/teacher/generation/definitions/generationDefinitions.test.ts`
- Modify: `api/src/tests/chat/test_generation_direct_routes.py`
- Interfaces: TypeScript config definitions；Pydantic direct request models；job payload

- [ ] 为每类资源写 serializer 契约测试，断言所有 UI 字段进入请求且后端 schema 接受。
- [ ] 为后端 handler 写字段消费测试，确保每个字段改变都会改变任务输入/提示或结构输出。
- [ ] 运行测试确认现有装饰性或不一致字段导致 RED。
- [ ] 表单统一为核心区和折叠“更多设置”，只把主题设为必填；有安全范围的数值做前后端一致校验。
- [ ] 修复实际契约差异，特别是 lesson type、mind_map/graph 别名、classroom 配置和 flashcard 主题语义。
- [ ] PPT 卡片增加“后续升级”说明但不修改生成链路。
- [ ] 运行 Node 测试、后端路由测试和 `pnpm build`，提交：`git commit -m "feat: simplify effective teacher generation configs"`。

## Task 8: 建立 Visual Brief 与视觉资产领域模型

**Files:**
- Create: `api/src/app/services/visual_assets/models.py`
- Create: `api/src/app/services/visual_assets/planner.py`
- Create: `api/src/app/services/visual_assets/pipeline.py`
- Create: `api/src/app/services/visual_assets/__init__.py`
- Create: `api/src/tests/services/visual_assets/test_visual_planner.py`
- Interfaces: `VisualBrief`、`VisualSlot`、`VisualCandidate`、`SelectedVisual`、`VisualPlan`

- [ ] 写失败测试：模型输出被解析为稳定 slot ID；无效/重复槽位被拒绝；资源策略限制最大图片数。
- [ ] 运行测试确认 RED。
- [ ] 用 dataclass/Pydantic 建立最小领域模型和序列化快照。
- [ ] 实现 planner：根据资源类型、主题和内容大纲生成结构化 Visual Brief；解析失败返回空计划而不阻塞纯文本资源。
- [ ] 为 report/blog/lesson_plan/classroom 定义默认图片上限和偏好类型，其他资源默认为可选。
- [ ] 运行测试并提交：`git commit -m "feat: add visual brief planning contract"`。

## Task 9: 实现知识库与博查图片候选、下载和质量门槛

**Files:**
- Create: `api/src/app/services/visual_assets/retrievers.py`
- Create: `api/src/app/services/visual_assets/localizer.py`
- Create: `api/src/app/services/visual_assets/quality.py`
- Modify: `api/src/app/chat/providers/bocha_provider.py`
- Reuse/Modify: `api/src/app/chat/workflows/report/image_downloader.py`
- Reuse/Modify: `api/src/app/chat/runtime/agent_tools/handlers/image_search.py`
- Create: `api/src/tests/services/visual_assets/test_visual_retrieval.py`
- Create: `api/src/tests/services/visual_assets/test_visual_security.py`
- Interfaces: KB asset search；Bocha image search；safe downloader；candidate quality result

- [ ] 写失败测试：知识库媒体只在选定 scope 内返回；博查结果保留来源页；重复和低分辨率图片被过滤。
- [ ] 写安全失败测试：内网 URL、非图片 MIME、超大响应、过多重定向和路径逃逸被拒绝。
- [ ] 运行测试确认 RED。
- [ ] 把现有 report downloader 的通用部分迁入 visual assets localizer，旧调用保留兼容适配。
- [ ] 实现 KB 优先、Web 补充的候选聚合；并行查询但按 slot 独立限流。
- [ ] 实现尺寸/MIME/哈希/感知重复硬门槛和可解释 rejection reason。
- [ ] 运行测试并提交：`git commit -m "feat: retrieve and validate reusable visual assets"`。

## Task 10: 多模态排序、带图正文和最终组装

**Files:**
- Create: `api/src/app/services/visual_assets/ranker.py`
- Create: `api/src/app/services/visual_assets/assembler.py`
- Create: `api/src/tests/services/visual_assets/test_visual_ranking_and_assembly.py`
- Modify: `api/src/app/chat/workflows/report/image_injector.py`
- Modify: `api/src/app/chat/agents/universal_report_engine.py`
- Modify: `api/src/app/blog_agent/engine.py`
- Modify: lesson plan generation service located by `rg "generate_lesson_plan" api/src/app`
- Modify: `api/src/app/services/classroom_service.py`
- Interfaces: multimodal model adapter；selected visuals prompt payload；markdown/scene assembler

- [ ] 写失败测试：相关图片胜出、无合格图留空、正文只能引用已选 slot、组装结果包含本地图片与来源。
- [ ] 运行测试确认 RED。
- [ ] 实现可注入的 ranker；生产使用多模态模型，测试使用确定性评分器。
- [ ] 将图片视觉描述和 slot 映射传给正文模型，再由 assembler 替换为真实本地资源引用。
- [ ] 先接入 report，再以共享 adapter 接入 blog、lesson plan 和 classroom，禁止复制四套下载逻辑。
- [ ] 保存 Visual Plan、候选统计、rejection reasons 和最终使用图片到任务结果。
- [ ] 运行目标测试和四类生成回归，提交：`git commit -m "feat: generate resource bodies around selected visuals"`。

## Task 11: 补齐思维导图生成、预览和基础编辑

**Files:**
- Modify: `api/src/app/chat/application/knowledge_base_direct_graph_service_v2.py`
- Modify: `api/src/app/services/generation_task_handlers.py`
- Modify: `api/src/core/course_storage.py`
- Modify: `src/stitch/components/CourseMaterialArtifactPreview.tsx`
- Create: `src/stitch/components/MindMapEditor.tsx`
- Modify: `src/stitch/pages/CourseResources.tsx`
- Create/Modify: `api/src/tests/chat/test_direct_graph_generation.py`
- Modify: `tests/e2e/generation-visual-resources.spec.ts`
- Interfaces: graph direct job；mind_map material alias；tree patch；JSON export

- [ ] 写失败测试：graph job 生成统一树、以 mind map 显示并落库；非法树拒绝保存；根节点不可删除。
- [ ] 写 E2E 失败测试：生成后从最近任务打开资源，预览、缩放、改节点、保存、刷新仍存在、下载 JSON。
- [ ] 运行测试确认 RED。
- [ ] 规范化 LLM 图结构，为所有节点补稳定 ID，限制深度和节点数。
- [ ] 后端兼容 `graph` 存储别名，前端统一显示“思维导图”。
- [ ] 实现轻量节点编辑器和 JSON 导出；PNG 仅在自动化稳定后开放。
- [ ] 运行目标测试和 E2E，提交：`git commit -m "feat: complete editable mind map resources"`。

## Task 12: 提供最小资源内容编辑与真实导出

**Files:**
- Modify: `api/src/app/api/courses.py`
- Modify: `api/src/app/schemas/course.py`
- Modify: `api/src/app/services/material_publication_service.py`
- Modify: `src/stitch/api/courses.ts`
- Modify: `src/stitch/api/types.ts`
- Modify: `src/stitch/pages/CourseResources.tsx`
- Create: `src/stitch/components/MaterialContentEditor.tsx`
- Modify: `src/stitch/components/CourseMaterialArtifactPreview.tsx`
- Create/Modify: `api/src/tests/test_course_material_editing.py`
- Modify: `tests/e2e/resources-and-classroom.spec.ts`
- Interfaces: `PATCH /api/courses/{course_id}/materials/{material_type}/{material_id}/content`；export response

- [ ] 写权限失败测试：教师可改有权限课程资源，跨课程/无权限拒绝；结构化资源无效数据返回 422。
- [ ] 写 E2E 失败测试：报告/博客/教案 Markdown 编辑保存；习题/闪卡结构编辑；游戏数据编辑后重组；AI 课堂安全字段编辑。
- [ ] 运行测试确认 RED。
- [ ] 实现按资源类型白名单校验的 PATCH，不开放任意文件路径或任意 HTML 写入。
- [ ] 实现统一简洁编辑抽屉，文本 Markdown 双栏预览，结构化资源使用最小字段编辑。
- [ ] 只显示并验证 Markdown、JSON、HTML 和已有 AI 课堂导出；删除或隐藏假按钮。
- [ ] 运行 API、E2E 和构建，提交：`git commit -m "feat: add simple material editing and real exports"`。

## Task 13: 八类资源端到端矩阵

**Files:**
- Modify: `tests/e2e/generation-text-resources.spec.ts`
- Modify: `tests/e2e/generation-practice-resources.spec.ts`
- Modify: `tests/e2e/generation-visual-resources.spec.ts`
- Modify: `tests/e2e/resources-and-classroom.spec.ts`
- Create: `api/src/tests/integration/test_teacher_generation_matrix.py`
- Modify: `docs/acceptance/2026-08-09-grounded-agent-and-multimodal-resource-generation.md`
- Interfaces: config → preflight → job → handler → material → preview

- [ ] 为 report、lesson_plan、blog、quiz、flashcard、mind_map、game、classroom 建立参数化后端集成测试。
- [ ] 每类断言正确 handler、source snapshot、config snapshot、成功 job、material ID 和可读取 artifact。
- [ ] Playwright 分组验证三种来源默认/切换、后台任务状态、最近生成跳转和资源预览。
- [ ] 使用固定唯一知识事实验证 selected 与 course_auto 真正影响输出和引用；none 不出现该事实。
- [ ] 运行完整矩阵并将通过数、耗时和失败截图路径写入验收报告。
- [ ] 提交：`git commit -m "test: cover teacher resource generation end to end"`。

## Task 14: 真实服务冒烟与最终回归

**Files:**
- Create: `api/src/scripts/smoke_teacher_agent_tools.py`
- Create: `api/src/scripts/smoke_teacher_generation.py`
- Modify: `docs/acceptance/2026-08-09-grounded-agent-and-multimodal-resource-generation.md`
- Interfaces: real RAG index；Bocha；configured LLM/multimodal model；durable jobs

- [x] 冒烟脚本默认只预览矩阵且要求显式 `--execute`，不打印密钥。
- [ ] 用种子课程验证 selected RAG、course_auto RAG、Web、RAG+Web 的工具顺序和来源。
- [ ] 对八类资源各提交一份最小真实任务并等待终态；PPT 明确跳过并记录后置。
- [ ] 对至少一个图文报告验证 Visual Brief、候选、本地图片、正文 slot 和最终预览一致。
- [x] 运行后端完整测试集、前端 `pnpm test`、`pnpm build` 和教师端核心 Playwright 项目。
- [x] 将所有实际结果、环境限制、剩余风险写入验收文档；未把缺少供应商密钥写成通过。
- [x] 运行 `rg -n "TODO|PLACEHOLDER|待补|假数据"` 扫描本次新增生产文件，所有目标文件无命中。
- [ ] 提交：`git commit -m "docs: record grounded teacher acceptance results"`。

## Task 15: 完成分支与交付审查

**Files:**
- Review: 本计划涉及的全部文件
- Modify: `docs/acceptance/2026-08-09-grounded-agent-and-multimodal-resource-generation.md`
- Interfaces: git diff；测试报告；验收清单

- [ ] 对照 SPEC 逐条检查 15 条完成定义和验收矩阵，不以“已编码”替代“已验证”。
- [ ] 检查 `git diff --check`、工作区中用户原有改动是否保留、本次提交是否没有意外数据文件。
- [ ] 运行 Superpowers `verification-before-completion`，引用新的实际命令输出。
- [ ] 使用 `finishing-a-development-branch` 完成最终审查；因用户已明确授权在当前 main 执行，不自动推送远端。
- [ ] 验收文档标记最终状态并列出可直接复验的命令与入口。

## 执行顺序与停止条件

严格按 Task 1→15 执行。若某个真实供应商因缺少密钥不可用，自动化替身测试仍继续，但最终验收必须明确标记“真实冒烟未通过”，不得伪造成功。仅当遇到需要新增付费服务、改变数据模型且会破坏现有资源、或扩大到 PPT/学生端等越界决策时才暂停请求授权；其他实现选择按 SPEC 的决策记录采用最小可靠方案并回填验收文档。
