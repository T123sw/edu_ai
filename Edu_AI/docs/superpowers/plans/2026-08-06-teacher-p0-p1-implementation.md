# 教师端 P0/P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按已确认 SPEC 完成教师端 P0 与 P1，使核心入口美观可达、后台任务可恢复、RAG 与资源结果可信、API 可由前端安全配置。

**Architecture:** 前端先收敛正式导航、资源类型和页面外壳，再由全局 JobStore 取代组件私有轮询。后端扩展现有 `EduJob`、课程资源存储和 RAG 文档状态，不另起并行系统；运行配置通过后端加密存储和版本化快照注入现有服务。

**Tech Stack:** React 18、TypeScript、Ant Design、Zustand、Vite、Node test runner、FastAPI、Pydantic、pytest、文件型持久化。

---

## 执行约束

- 每个任务严格执行 RED → GREEN → REFACTOR。
- 每个任务结束运行定向测试、相关回归、`git diff --check`。
- 每个任务独立 commit，并立即 push 到 `origin/codex/teacher-p0-p1`。
- 决策写入 `docs/superpowers/decisions/2026-08-06-teacher-p0-p1-decisions.md`。
- 不修改 OpenMAIC 渲染主线，不新增课堂全局时间线编辑器。

### Task 1：提交执行基线与文档

**Files:**
- Create: `docs/superpowers/decisions/2026-08-06-teacher-p0-p1-decisions.md`
- Create: `docs/superpowers/plans/2026-08-06-teacher-p0-p1-implementation.md`
- Add: `docs/superpowers/specs/2026-08-06-teacher-p0-usability-and-job-center-design.md`
- Add: `docs/superpowers/specs/2026-08-06-teacher-p1-trusted-generation-and-configuration-design.md`
- Add: `docs/教师端基础可用性审计与整改优先级_2026-08-06.md`

- [x] 校验文档无未决占位标记、代码围栏平衡、PPT/闪卡口径一致。
- [x] 提交 `docs(teacher): define P0 and P1 delivery baseline`。
- [x] 推送功能分支。

### Task 2：正式导航、路由和课程上下文

**Files:**
- Modify: `src/stitch/shared.tsx`
- Modify: `src/stitch/App.tsx`
- Modify: `src/stitch/pages/CourseDetail.tsx`
- Modify: `src/stitch/api/types.ts`
- Test: `tests/frontend/app.course-resources-route.test.ts`
- Create: `tests/frontend/teacher-navigation-contract.test.ts`

Desired route contract:

```ts
type TeacherCourseRoute =
  | "workspace"
  | "knowledge-base"
  | "graph"
  | "classroom-studio"
  | "resources"
  | "settings";

export function buildTeacherCourseHash(
  route: TeacherCourseRoute,
  courseId: string,
): string;
```

- [x] RED：导航顺序必须是问答、课程知识库、知识图谱、AI 课堂、课程资源、课程设置。
- [x] RED：空课程 ID 不得生成含 `undefined` 的 href。
- [x] GREEN：实现唯一的路由构造函数并替换相关字符串拼接。
- [x] GREEN：课程资源进入侧栏，“详情编辑”更名为“课程设置”。
- [x] 验证定向测试、前端测试和构建。
- [ ] 提交并 push。

### Task 3：八类资源入口和响应式工作台

**Files:**
- Create: `src/components/teacher/studioActions.ts`
- Modify: `src/components/teacher/StudioPanel.tsx`
- Modify: `src/components/teacher/StudioPanel.css`
- Modify: `src/pages/teacher/AiStudioPage.css`
- Create: `tests/frontend/studioPanel.action-registry.test.ts`
- Create: `tests/frontend/studioPanel.responsive-layout.test.ts`

Desired registry:

```ts
export const TEACHER_STUDIO_ACTIONS = [
  "report", "lesson_plan", "blog", "quiz",
  "ppt", "flashcard", "graph", "game",
] as const;
```

- [ ] RED：断言八个正式资源类型和固定顺序。
- [ ] RED：断言 AI 课堂主卡在资源网格之前，网格不固定为两行。
- [ ] RED：断言容器允许 `min-width: 0`，卡片网格使用自适应列，页面无横向溢出。
- [ ] GREEN：抽取注册表并恢复 PPT、闪卡卡片。
- [ ] GREEN：实现 3/2/1 列容器响应式、单一纵向滚动和键盘操作。
- [ ] GREEN：更新空状态，去除“只有六个功能”的硬编码。
- [ ] 验证 1280/1366/1440/1600/1920 源码断言与浏览器截图。
- [ ] 提交并 push。

### Task 4：课程资源统一列表

**Files:**
- Modify: `src/stitch/api/types.ts`
- Modify: `src/stitch/api/courses.ts`
- Modify: `src/stitch/pages/CourseResources.tsx`
- Modify: `src/stitch/styles.css`
- Modify: `src/services/teacher/materials.helpers.ts`
- Test: `tests/frontend/courseResources.scroll-layout.test.ts`
- Create: `tests/frontend/courseResources.material-routing.test.ts`

Routing contract:

```ts
export function getCourseMaterialOpenTarget(
  material: CourseMaterial,
): { kind: "route" | "preview"; value: string };
```

- [ ] RED：`classroom`、`ppt`、`flashcard`、`graph`、`game` 均有明确标签和打开行为。
- [ ] RED：未知类型不得跳到视频页。
- [ ] GREEN：AI 课堂和其他资源进入同一列表，保留独立筛选。
- [ ] GREEN：PPT/闪卡拥有独立筛选与正确预览。
- [ ] GREEN：补齐加载、空、失败和重试状态。
- [ ] 验证定向测试、前端测试、构建与浏览器操作。
- [ ] 提交并 push。

### Task 5：在线课堂教师控制台

**Files:**
- Modify: `src/stitch/pages/ClassroomPlayer.tsx`
- Modify: `src/stitch/pages/ClassroomStudio.tsx`
- Modify: `src/stitch/styles.css`
- Modify: `src/openmaic/classroomScene.ts`
- Create: `src/openmaic/pagePlaybackController.ts`
- Create: `src/openmaic/pagePlaybackController.test.ts`

Controller contract:

```ts
export interface PagePlaybackController {
  enter(sceneIndex: number): Promise<void>;
  play(): Promise<void>;
  pause(): void;
  replay(): Promise<void>;
  leave(): void;
  dispose(): void;
}
```

- [ ] RED：翻页停止上一页语音、媒体、焦点和计时器。
- [ ] RED：重播只重播当前页；不暴露全课程 scrubber。
- [ ] GREEN：实现目录 + 自适应 16:9 舞台 + 当前页辅助面板。
- [ ] GREEN：实现浏览、演示、全屏及当前页播放控制。
- [ ] GREEN：保留内部 LessonTimeline 供 MP4 导出使用。
- [ ] 验证单元测试、PPTX/视频既有回归和浏览器操作。
- [ ] 提交并 push。

### Task 6：后端 EduJob 账本

**Files:**
- Modify: `api/src/app/services/job_store.py`
- Modify: `api/src/app/api/jobs.py`
- Modify: `api/src/app/services/classroom_job_service.py`
- Modify: `api/src/app/services/classroom_video_export.py`
- Create: `api/src/tests/test_job_store_v2.py`
- Create: `api/src/tests/test_jobs_api_v2.py`

Target model:

```py
class EduJob(BaseModel):
    schema_version: int = 2
    edu_job_id: str
    kind: JobKind
    status: JobStatus
    owner_user_id: str
    course_id: str | None = None
    input_summary: dict[str, object] = {}
    result_ref: dict[str, object] | None = None
    retry_of: str | None = None
    parent_job_id: str | None = None
```

- [ ] RED：状态转换、owner 过滤、列表分页、取消、重试和旧记录兼容。
- [ ] RED：并发写入和故障注入不能产生半个 JSON。
- [ ] GREEN：原子写入、目录锁、版本化兼容读取。
- [ ] GREEN：实现列表、详情、取消、重试接口；身份从后端注入。
- [ ] 验证定向 pytest 与课堂任务回归。
- [ ] 提交并 push。

### Task 7：前端全局任务管理器

**Files:**
- Create: `src/jobs/types.ts`
- Create: `src/jobs/api.ts`
- Create: `src/jobs/jobStore.ts`
- Create: `src/jobs/GlobalJobManager.tsx`
- Create: `src/jobs/JobCenterDrawer.tsx`
- Modify: `src/stitch/App.tsx`
- Create: `src/jobs/jobStore.test.ts`

- [ ] RED：启动恢复、去重轮询、退避、终态通知和课程资源失效刷新。
- [ ] RED：多标签页只有一个活动轮询领导者或等效去重保证。
- [ ] GREEN：实现后端任务为唯一事实来源的 Zustand store。
- [ ] GREEN：实现全局调度器、任务中心抽屉和页面查询 hook。
- [ ] GREEN：组件卸载不删除任务，重新登录按用户恢复。
- [ ] 验证定向测试、前端测试和浏览器刷新恢复。
- [ ] 提交并 push。

### Task 8：迁移现有长任务并统一状态

**Files:**
- Modify: `src/components/teacher/ClassroomGenerationEntry.tsx`
- Modify: `src/stitch/pages/ClassroomStudio.tsx`
- Modify: `src/components/teacher/StudioPanel.tsx`
- Modify: `src/components/teacher/ChatPanel.tsx`
- Modify: `src/components/teacher/SourcePanel.tsx`
- Create: `src/components/shared/AsyncState.tsx`
- Create: `tests/frontend/teacher-global-job-migration.test.ts`

- [ ] RED：核心组件不得再以私有 interval 作为任务权威。
- [ ] RED：加载、空、失败、部分成功、无权限均有教师可读文案和恢复动作。
- [ ] GREEN：课堂、视频、报告、习题、游戏、博客、PPT、闪卡、RAG 接入全局任务。
- [ ] GREEN：删除重复通知和本地任务权威状态。
- [ ] 验证全局任务与核心页面回归。
- [ ] 提交并 push，完成 P0 代码冻结。

### Task 9：RAG 文档状态和测试检索

**Files:**
- Modify: `api/src/modules/rag_v2/document_resolver.py`
- Modify: `api/src/modules/rag_v2/rag_main/system.py`
- Modify: `api/src/app/api/courses.py`
- Modify: `src/components/teacher/SourcePanel.tsx`
- Modify: `src/services/knowledgeBase.ts`
- Create: `api/src/tests/test_rag_document_lifecycle.py`
- Create: `tests/frontend/sourcePanel.rag-status.test.ts`

Lifecycle:

```text
uploaded -> parsing -> chunking -> embedding -> ready
                                      \-> failed
ready -> rebuilding -> ready (old index remains active until swap)
```

- [ ] RED：上传返回 document + job，失败不标 ready。
- [ ] RED：重建失败保留旧索引，删除清理 chunk 和派生物。
- [ ] GREEN：持久化状态、阶段、错误、索引版本和统计。
- [ ] GREEN：实现失败重试、单文档测试检索和引用定位。
- [ ] 验证权限、生命周期和前端状态。
- [ ] 提交并 push。

### Task 10：统一课程资源与原子存储

**Files:**
- Modify: `api/src/core/course_storage.py`
- Modify: `api/src/app/api/courses.py`
- Modify: `src/stitch/api/types.ts`
- Modify: `src/stitch/api/courses.ts`
- Create: `api/src/tests/core/test_course_material_manifest.py`
- Create: `api/src/tests/core/test_course_material_permissions.py`

- [ ] RED：统一 ID、owner、版本、来源、任务、配置快照和 manifest。
- [ ] RED：并发写入、保存失败、完整删除、越权和旧数据读取。
- [ ] GREEN：临时目录写入、校验、原子发布、索引更新。
- [ ] GREEN：正式类型不落入 `others`，AI 课堂 ID 同源。
- [ ] GREEN：列表、详情、重命名、置顶、删除和完整性检查。
- [ ] 验证存储故障注入与 API 权限。
- [ ] 提交并 push。

### Task 11：八类可信生成与 PPT/闪卡闭环

**Files:**
- Create: `api/src/app/services/generation_command.py`
- Modify: `api/src/app/chat/api/routes_v2.py`
- Modify: `api/src/app/chat/application/reply_service_v2.py`
- Modify: `src/components/teacher/StudioPanel.tsx`
- Create: `src/components/teacher/FlashcardArtifactPreview.tsx`
- Create: `src/components/teacher/FlashcardEntryModal.tsx`
- Create: `api/src/tests/chat/test_generation_command.py`
- Create: `tests/frontend/studioPanel.flashcard.test.ts`

- [ ] RED：统一命令校验来源、权限、幂等键和参数。
- [ ] RED：PPT 和闪卡必须生成正式资源，禁止占位成功。
- [ ] GREEN：八类生成器适配 EduJob 与 CourseMaterial，不重写业务引擎。
- [ ] GREEN：恢复 PPT 配置/大纲确认，补闪卡配置和逐张预览。
- [ ] GREEN：保存失败返回 `partially_succeeded` 并允许重新保存。
- [ ] 验证每类固定样例、刷新恢复和结果来源。
- [ ] 提交并 push。

### Task 12：运行配置后端与密钥安全

**Files:**
- Create: `api/src/app/services/runtime_config_store.py`
- Create: `api/src/app/services/runtime_config_resolver.py`
- Create: `api/src/app/api/runtime_config.py`
- Modify: `api/src/app/bootstrap.py`
- Modify: `api/src/core/config.py`
- Create: `api/src/tests/test_runtime_config_store.py`
- Create: `api/src/tests/test_runtime_config_api.py`

Configuration state:

```text
draft -> verifying -> verified -> active
                      \-> invalid
active -> rollback to previous active
```

- [ ] RED：密钥加密、响应掩码、owner 隔离、角色权限和日志脱敏。
- [ ] RED：未验证配置不能激活，激活失败自动回滚。
- [ ] GREEN：实现系统默认 + 用户覆盖 + 任务快照解析。
- [ ] GREEN：先接入对话模型、Embedding、TTS，再接入 SPEC 其余服务。
- [ ] 验证新任务使用新配置，旧任务保持原快照。
- [ ] 提交并 push。

### Task 13：配置中心前端

**Files:**
- Create: `src/stitch/pages/RuntimeSettings.tsx`
- Create: `src/stitch/api/runtimeConfig.ts`
- Modify: `src/stitch/App.tsx`
- Modify: `src/stitch/pages/Profile.tsx`
- Create: `tests/frontend/runtimeSettings.contract.test.ts`

- [ ] RED：密钥不可回显，测试成功后才能启用。
- [ ] RED：角色决定系统配置/个人配置可见性。
- [ ] GREEN：实现模型、RAG、语音、搜索、PDF、课堂服务分组。
- [ ] GREEN：实现草稿、测试、启用、回滚和健康状态。
- [ ] 验证键盘操作、错误恢复和实际请求配置版本。
- [ ] 提交并 push。

### Task 14：真实用户中心

**Files:**
- Modify: `api/src/app/auth.py`
- Modify: `api/src/app/schemas/auth.py`
- Modify: `src/stitch/pages/Profile.tsx`
- Modify: `src/stitch/api/client.ts`
- Modify: `api/src/tests/test_auth.py`
- Create: `tests/frontend/profile.real-data.test.ts`

- [ ] RED：错误旧密码不能成功，资料刷新来自后端。
- [ ] GREEN：移除模拟资料和假改密，接真实账户接口。
- [ ] GREEN：配置入口按角色显示。
- [ ] 验证认证、错误文案和刷新恢复。
- [ ] 提交并 push。

### Task 15：P0/P1 总体验收与发布记录

**Files:**
- Update: `docs/superpowers/decisions/2026-08-06-teacher-p0-p1-decisions.md`
- Create: `docs/acceptance/2026-08-06-teacher-p0-p1-acceptance.md`

- [ ] 运行全部前端测试、lint、生产构建。
- [ ] 运行全部后端测试。
- [ ] 运行 1280/1366/1440/1600/1920 浏览器验收并保存截图。
- [ ] 执行权限、密钥泄漏、并发写入和任务恢复检查。
- [ ] 对照 P0/P1 SPEC 每一项完成定义并记录证据。
- [ ] 提交并 push 最终验收记录。
