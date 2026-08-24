# 课程内容体系前端收口（阶段一）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不修改数据库和后端接口的前提下，双端移除独立知识图谱页面，把原“课程资源”收口为仅展示当前用户内容的“个人资源”，并将主题切换入口迁入个人中心。

**Architecture:** 保留知识结构后端和旧路由兼容层，只缩减前端可达页面与查询范围。个人资源继续使用现有材料接口，但所有聚合入口都显式传递 `space: "mine"`；AI课堂仍保留自己的个人/课程空间。主题仍由 `AppShellContext` 和 `stitch-theme` 本地存储驱动，只改变交互入口。

**Tech Stack:** React 18、TypeScript、Vite、Node test runner、ESLint、pnpm。

**Design source:** `docs/superpowers/specs/2026-08-24-course-content-frontend-phase1-design-cn.md`

**Acceptance source:** `docs/superpowers/acceptance/2026-08-24-course-content-frontend-phase1-acceptance.md`

---

## Task 1：移除双端知识图谱前端视图

**Files:**

- Modify: `Edu_AI/src/stitch/teacherRoutes.test.ts`
- Modify: `Edu_AI/src/stitch/student/routes/studentRoutes.test.ts`
- Modify: `Edu_AI/src/stitch/legacyRetirement.test.ts`
- Modify: `Edu_AI/src/stitch/pages/CourseKnowledge.tsx`
- Modify: `Edu_AI/src/stitch/teacherRoutes.ts`
- Modify: `Edu_AI/src/stitch/student/routes/studentRoutes.ts`
- Modify: `Edu_AI/src/stitch/shared/routes/roleCourseRouteResolver.ts`
- Modify: `Edu_AI/src/stitch/student/shell/StudentShell.tsx`
- Modify: `Edu_AI/src/stitch/pages/CourseDetail.tsx`

- [ ] **Step 1：先写路由与页面失败测试**

  在教师、学生路由测试中把知识入口预期改为不带 `view`：

  ```ts
  assert.equal(
    buildTeacherCourseHash("knowledge", "c1"),
    "#knowledge?course_id=c1",
  );
  assert.deepEqual(
    readTeacherCourseLocation("#knowledge?course_id=c1&view=structure"),
    { route: "knowledge", courseId: "c1" },
  );
  ```

  ```ts
  assert.equal(
    buildStudentHash("student-course-knowledge", { courseId: "course-1" }),
    "#student-course-knowledge?course_id=course-1",
  );
  ```

  在 `legacyRetirement.test.ts` 增加源码契约：`CourseKnowledge.tsx` 不含 `KnowledgeStructureView`、`知识图谱` 或 `view === "structure"`，仍含 `KnowledgeDocumentsView`；历史 `routes.graph` 仍由重定向组件处理。

- [ ] **Step 2：运行定向测试，确认先失败**

  Run:

  ```powershell
  pnpm exec node --import tsx --test src/stitch/teacherRoutes.test.ts src/stitch/student/routes/studentRoutes.test.ts src/stitch/legacyRetirement.test.ts
  ```

  Expected: 因旧实现仍编码 `view=structure/documents`、课程知识页仍导入图谱组件而失败。

- [ ] **Step 3：实现最小路由收口**

  - `CourseKnowledgePage` 删除 tab 状态、`KnowledgeStructureView` 导入和条件渲染，直接渲染：

    ```tsx
    <KnowledgeDocumentsView readOnly={isStudent} />
    ```

  - `LegacyKnowledgeGraphRedirect` 只构造 `buildTeacherCourseHash("knowledge", courseId)`。
  - 删除教师、学生路由中的知识视图联合类型及 `view` 编解码；历史查询参数由 URL 解析自然忽略。
  - `roleCourseRouteResolver` 不再接受或转发知识视图。
  - `StudentShell` 与 `CourseDetail` 不再向课程知识链接注入 `view`。
  - 保留教师 `graph` 路由解析及 `LegacyKnowledgeGraphRedirect`，不删除后端图结构代码。

- [ ] **Step 4：运行定向测试，确认通过**

  Run:

  ```powershell
  pnpm exec node --import tsx --test src/stitch/teacherRoutes.test.ts src/stitch/student/routes/studentRoutes.test.ts src/stitch/legacyRetirement.test.ts
  ```

  Expected: 全部通过。

- [ ] **Step 5：检查前端不可达性**

  Run:

  ```powershell
  rg -n 'KnowledgeStructureView|知识图谱|view:\s*"structure"' src/stitch/pages/CourseKnowledge.tsx src/stitch/student/shell/StudentShell.tsx src/stitch/pages/CourseDetail.tsx
  ```

  Expected: 无匹配；`KnowledgeGraph.tsx` 和后端知识结构接口不在删除范围内。

- [ ] **Step 6：提交任务**

  ```powershell
  git add Edu_AI/src/stitch/pages/CourseKnowledge.tsx Edu_AI/src/stitch/teacherRoutes.ts Edu_AI/src/stitch/teacherRoutes.test.ts Edu_AI/src/stitch/student/routes/studentRoutes.ts Edu_AI/src/stitch/student/routes/studentRoutes.test.ts Edu_AI/src/stitch/shared/routes/roleCourseRouteResolver.ts Edu_AI/src/stitch/student/shell/StudentShell.tsx Edu_AI/src/stitch/pages/CourseDetail.tsx Edu_AI/src/stitch/legacyRetirement.test.ts
  git commit -m "feat: retire course knowledge graph frontend"
  ```

## Task 2：统一“个人资源”命名与统计口径

**Files:**

- Modify: `Edu_AI/src/stitch/teacherRoutes.test.ts`
- Modify: `Edu_AI/src/stitch/student/routes/studentRoutes.test.ts`
- Modify: `Edu_AI/src/stitch/course/courseNavigation.test.ts`
- Modify: `Edu_AI/src/stitch/pages/courseCardPresentation.test.ts`
- Modify: `Edu_AI/src/stitch/teacherRoutes.ts`
- Modify: `Edu_AI/src/stitch/student/shell/studentNavigation.ts`
- Modify: `Edu_AI/src/stitch/student/shell/StudentShell.tsx`
- Modify: `Edu_AI/src/stitch/course/CourseShell.tsx`
- Modify: `Edu_AI/src/stitch/course/courseNavigation.ts`
- Modify: `Edu_AI/src/stitch/pages/CourseDetail.tsx`
- Modify: `Edu_AI/src/stitch/pages/HomeDashboard.tsx`
- Modify: `Edu_AI/src/stitch/pages/courseCardPresentation.ts`
- Modify: `Edu_AI/src/stitch/pages/CourseMaterialArtifactPreview.tsx`
- Modify: `Edu_AI/src/stitch/App.tsx`

- [ ] **Step 1：先把导航和指标测试改为新产品语言**

  教师、学生导航都断言资源入口为“个人资源”，课程卡断言：

  ```ts
  { label: "个人资源", value: 7 }
  ```

  在课程导航测试中增加：

  ```ts
  assert.equal(
    getCourseNavigation("editor").find((item) => item.id === "resources")?.label,
    "个人资源",
  );
  ```

- [ ] **Step 2：运行测试，确认旧文案导致失败**

  Run:

  ```powershell
  pnpm exec node --import tsx --test src/stitch/teacherRoutes.test.ts src/stitch/student/routes/studentRoutes.test.ts src/stitch/course/courseNavigation.test.ts src/stitch/pages/courseCardPresentation.test.ts
  ```

  Expected: 旧“课程资源/资源管理”断言不一致而失败。

- [ ] **Step 3：修改所有个人资源入口和概览口径**

  - 教师侧栏、学生侧栏、课程壳导航、页面标题统一为“个人资源”。
  - `CourseDetail` 与 `HomeDashboard` 的材料统计调用显式传递：

    ```ts
    getCourseMaterials(course.id, { space: "mine", sort: "updated_desc" })
    ```

    未传排序的首页调用使用 `{ space: "mine" }`。
  - 课程概览中的“最新课程资源”、共享说明、快捷入口文案改为个人资源语义。
  - `courseCardPresentation.ts` 指标标签改为“个人资源”。
  - 预览返回文案改为“返回个人资源列表”。
  - `App.tsx` 内部页面标题改为 `Personal Resources`；内部 route key 不改。

- [ ] **Step 4：运行测试与文本检查**

  Run:

  ```powershell
  pnpm exec node --import tsx --test src/stitch/teacherRoutes.test.ts src/stitch/student/routes/studentRoutes.test.ts src/stitch/course/courseNavigation.test.ts src/stitch/pages/courseCardPresentation.test.ts
  rg -n '课程资源|资源管理' src/stitch/teacherRoutes.ts src/stitch/student/shell src/stitch/course/CourseShell.tsx src/stitch/course/courseNavigation.ts src/stitch/pages/CourseDetail.tsx src/stitch/pages/HomeDashboard.tsx src/stitch/pages/courseCardPresentation.ts src/stitch/pages/CourseMaterialArtifactPreview.tsx
  ```

  Expected: 测试通过；列出的个人资源页面与导航无旧称。学习任务内部如果仍以“课程资源”描述任务分发内容，不在本次机械替换范围内。

- [ ] **Step 5：提交任务**

  ```powershell
  git add Edu_AI/src/stitch/teacherRoutes.ts Edu_AI/src/stitch/teacherRoutes.test.ts Edu_AI/src/stitch/student/routes/studentRoutes.test.ts Edu_AI/src/stitch/student/shell/studentNavigation.ts Edu_AI/src/stitch/student/shell/StudentShell.tsx Edu_AI/src/stitch/course/CourseShell.tsx Edu_AI/src/stitch/course/courseNavigation.ts Edu_AI/src/stitch/course/courseNavigation.test.ts Edu_AI/src/stitch/pages/CourseDetail.tsx Edu_AI/src/stitch/pages/HomeDashboard.tsx Edu_AI/src/stitch/pages/courseCardPresentation.ts Edu_AI/src/stitch/pages/courseCardPresentation.test.ts Edu_AI/src/stitch/pages/CourseMaterialArtifactPreview.tsx Edu_AI/src/stitch/App.tsx
  git commit -m "feat: rename personal resource workspace"
  ```

## Task 3：将资源页收口为个人单空间

**Files:**

- Modify: `Edu_AI/src/stitch/pages/courseResourcesManagement.test.ts`
- Modify: `Edu_AI/src/stitch/pages/CourseResources.tsx`

- [ ] **Step 1：增加个人单空间失败测试**

  在 `courseResourcesManagement.test.ts` 增加源码契约：

  ```ts
  test("personal resources load only the current user's private space", async () => {
    const source = await readFile(new URL("./CourseResources.tsx", import.meta.url), "utf8");
    assert.match(source, /getCourseMaterials\(course\.id,\s*\{[\s\S]*space:\s*["']mine["']/);
    assert.doesNotMatch(source, /RESOURCE_SPACES|sharedMaterials|space:\s*["']course["']/);
    assert.doesNotMatch(source, /publishCourseMaterial|withdrawCourseMaterial/);
    assert.doesNotMatch(source, /applyPublicationResult|applyWithdrawalResult/);
    assert.match(source, /不在个人资源中或无权访问/);
  });
  ```

- [ ] **Step 2：运行测试，确认共享空间仍存在而失败**

  Run:

  ```powershell
  pnpm exec node --import tsx --test src/stitch/pages/courseResourcesManagement.test.ts
  ```

  Expected: 因共享数组、课程空间请求和发布/撤回处理仍存在而失败。

- [ ] **Step 3：实现个人资源单空间**

  - 删除 `CourseMaterialSpace`、`RESOURCE_SPACES`、`resourceSpace`、`sharedMaterials`。
  - `loadMaterials` 只请求一次：

    ```ts
    const materials = await getCourseMaterials(course.id, {
      space: "mine",
      sort: "updated_desc",
    });
    setPersonalMaterials(materials);
    ```

  - 删除空间标签、共享数量、课程共享空状态、发布/更新/撤回事件和展示。
  - 搜索、类型筛选、排序、置顶、预览、编辑、重命名、删除均继续只更新 `personalMaterials`。
  - 深链接恢复后必须验证 `detail.visibility === "private"`；否则展示“该资源不在个人资源中或无权访问”。
  - 保留 AI课堂打开逻辑，不改 AI课堂自己的 `mine/course` 空间。

- [ ] **Step 4：运行个人资源测试**

  Run:

  ```powershell
  pnpm exec node --import tsx --test src/stitch/pages/courseResourcesManagement.test.ts
  ```

  Expected: 全部通过。

- [ ] **Step 5：静态确认发布能力只从本页移除**

  Run:

  ```powershell
  rg -n 'publishCourseMaterial|withdrawCourseMaterial|space:\s*"course"|sharedMaterials|RESOURCE_SPACES' src/stitch/pages/CourseResources.tsx
  ```

  Expected: 无匹配。不得据此删除 API 客户端或 AI课堂中的共享能力。

- [ ] **Step 6：提交任务**

  ```powershell
  git add Edu_AI/src/stitch/pages/CourseResources.tsx Edu_AI/src/stitch/pages/courseResourcesManagement.test.ts
  git commit -m "feat: make personal resources private-only"
  ```

## Task 4：把主题设置迁入个人中心

**Files:**

- Create: `Edu_AI/src/stitch/theme/ThemeAppearanceSettings.tsx`
- Create: `Edu_AI/src/stitch/theme/ThemeAppearanceSettings.test.ts`
- Modify: `Edu_AI/src/stitch/pages/Profile.tsx`
- Modify: `Edu_AI/src/stitch/shared.tsx`
- Modify: `Edu_AI/src/stitch/App.tsx`
- Modify: `Edu_AI/src/stitch/legacyRetirement.test.ts`

- [ ] **Step 1：先写主题入口失败测试**

  新测试读取组件源码并断言：

  ```ts
  assert.match(source, /海蓝/);
  assert.match(source, /森绿/);
  assert.match(source, /日落/);
  assert.match(source, /暗色/);
  assert.match(source, /setTheme/);
  assert.match(source, /palette/);
  assert.match(source, /aria-pressed/);
  ```

  同时在 `legacyRetirement.test.ts` 断言 `App.tsx` 不再导入或渲染 `ThemeCustomizer`，`Profile.tsx` 包含 `ThemeAppearanceSettings`。

- [ ] **Step 2：运行测试，确认组件尚不存在而失败**

  Run:

  ```powershell
  pnpm exec node --import tsx --test src/stitch/theme/ThemeAppearanceSettings.test.ts src/stitch/legacyRetirement.test.ts
  ```

  Expected: 新组件不存在或 App 仍有悬浮组件而失败。

- [ ] **Step 3：实现可访问的个人中心外观卡片**

  - 新建 `ThemeAppearanceSettings`，复用 `useAppShell()` 返回的 `theme/setTheme`。
  - 四个选项使用 `button type="button"`、`aria-pressed={theme === item.id}`、可见名称与选中标记；颜色样本只作辅助信息。
  - 标题使用 `MaterialIcon name="palette"`，并在 `shared.tsx` 的字形映射增加 `palette`。
  - 在 `Profile.tsx` 的资料/账号区域后渲染共享外观卡片，教师、学生、管理员均可见。
  - 从 `App.tsx` 删除 `ThemeCustomizer` 导入与根级挂载；从 `shared.tsx` 删除无消费者的悬浮组件实现。
  - 不改 `AppShellContext`、`stitch-theme` 写入和非法主题回落逻辑。

- [ ] **Step 4：运行主题测试**

  Run:

  ```powershell
  pnpm exec node --import tsx --test src/stitch/theme/ThemeAppearanceSettings.test.ts src/stitch/legacyRetirement.test.ts
  ```

  Expected: 全部通过。

- [ ] **Step 5：提交任务**

  ```powershell
  git add Edu_AI/src/stitch/theme/ThemeAppearanceSettings.tsx Edu_AI/src/stitch/theme/ThemeAppearanceSettings.test.ts Edu_AI/src/stitch/pages/Profile.tsx Edu_AI/src/stitch/shared.tsx Edu_AI/src/stitch/App.tsx Edu_AI/src/stitch/legacyRetirement.test.ts
  git commit -m "feat: move theme controls to profile"
  ```

## Task 5：阶段一整体验收

**Files:**

- Modify: `docs/superpowers/acceptance/2026-08-24-course-content-frontend-phase1-acceptance.md`

- [ ] **Step 1：运行完整前端自动化验证**

  Run from `Edu_AI/`:

  ```powershell
  pnpm test
  pnpm lint
  pnpm build
  ```

  Expected: 三条命令退出码均为 0。若出现既有失败，先按系统化调试流程确认与本次差异的因果关系，不得直接忽略。

- [ ] **Step 2：验证修改边界**

  Run from repository root:

  ```powershell
  git diff --name-only a4749c4..HEAD
  git status --short
  ```

  Expected: 实施差异只包含阶段一前端、测试和文档；不包含 `Edu_AI/api/`、Alembic、数据库文件、`storage/`、`course_data/` 或密钥文件。

- [ ] **Step 3：手工烟雾验收**

  - 教师进入课程知识：直接看到课程知识库，无图谱标签；旧 `#graph` 链接跳至知识库。
  - 学生进入课程知识：只读浏览课程知识库，无图谱标签。
  - 双端进入个人资源：只显示本人资源；可筛选、预览、置顶、重命名、编辑和删除；无课程共享切换和发布按钮。
  - 双端 AI课堂入口和个人/课程列表仍可访问。
  - 个人中心可用键盘选择四个主题，刷新后主题仍保持；右下角不再出现齿轮主题按钮。
  - 在窄屏下检查导航、资源列表和外观卡片无水平溢出。

- [ ] **Step 4：记录验收证据**

  在验收文档“执行记录”中填写命令、退出码、测试数量和手工验收结论；失败项必须保持未勾选并注明原因。

- [ ] **Step 5：提交验收记录**

  ```powershell
  git add docs/superpowers/acceptance/2026-08-24-course-content-frontend-phase1-acceptance.md
  git commit -m "docs: record frontend phase one acceptance"
  ```

## 明日阶段二启动条件

本计划不执行数据库相关工作。明天收到数据库、`storage`、`course_data` 和向量索引后，必须先做只读备份与一致性盘点，再为标准资源模型、叶子知识点批量生成、审核发布、任务快照和学习证据另写设计与实施计划。旧课程共享副本在完成引用关系证明前不得删除。
