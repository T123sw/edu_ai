# 学习资源生成入口与独立配置页实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在课程知识页“更新知识库”旁增加“学习资源生成”入口，并将教师端按知识点生成能力迁移到课程内独立配置页。

**Architecture:** 增加一个仍归属于“课程知识”导航分组的教师课程路由，由轻量页面组件复用现有 `StandardLearningResources`。入口直接使用当前课程标识构造 hash 链接；教师端课程知识页移除内联配置区，学生端继续保留已发布资源视图。现有后台批次、子任务、轮询、审核和重试逻辑不变。

**Tech Stack:** React 18、TypeScript、Vite、Node test runner、Playwright、现有 hash 路由和课程工作区组件。

---

## 文件结构

- 新建 `Edu_AI/src/stitch/pages/LearningResourceGeneration.tsx`：独立配置页外壳、返回入口及标准资源组件复用。
- 新建 `Edu_AI/src/stitch/pages/learningResourceGeneration.css`：独立配置页布局和返回链接样式。
- 新建 `Edu_AI/src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`：入口、路由归属和教师/学生页面分流的集成约束。
- 修改 `Edu_AI/src/stitch/shared.tsx`：注册路由常量。
- 修改 `Edu_AI/src/stitch/teacherRoutes.ts`：扩展教师课程路由类型与解析白名单。
- 修改 `Edu_AI/src/stitch/course/courseNavigation.ts`：把新路由归入课程知识导航分组。
- 修改 `Edu_AI/src/stitch/App.tsx`：懒加载并挂载独立配置页。
- 修改 `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx`：增加“学习资源生成”入口。
- 修改 `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.css`：为次级入口添加与现有操作区一致的按钮样式。
- 修改 `Edu_AI/src/stitch/pages/CourseKnowledge.tsx`：教师端移除内联配置区，学生端保留只读发布资源。
- 修改 `Edu_AI/tests/e2e/fixtures/apiRoutes.ts`：为独立配置页提供标准资源目录响应。
- 修改 `Edu_AI/tests/e2e/course-knowledge.spec.ts`：验证按钮跳转和配置页关键内容。

### Task 1: 用失败测试锁定入口、路由和页面分流

**Files:**
- Create: `Edu_AI/src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`

- [ ] **Step 1: 写入口和路由约束测试**

```ts
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (relativePath: string) => readFile(new URL(relativePath, import.meta.url), "utf8");

test("course knowledge exposes learning resource generation as a dedicated route", async () => {
  const [shared, teacherRoutes, navigation, app] = await Promise.all([
    source("../../shared.tsx"),
    source("../../teacherRoutes.ts"),
    source("../courseNavigation.ts"),
    source("../../App.tsx"),
  ]);

  assert.match(shared, /learningResourceGeneration:\s*["']learning-resource-generation["']/);
  assert.match(teacherRoutes, /["']learning-resource-generation["']/);
  assert.match(navigation, /routes:\s*\[[^\]]*["']learning-resource-generation["'][^\]]*\]/s);
  assert.match(app, /routes\.learningResourceGeneration/);
  assert.match(app, /LearningResourceGenerationPage/);
});

test("knowledge build card links editors to learning resource generation", async () => {
  const card = await source("./CourseKnowledgeBuildCard.tsx");
  assert.match(card, /buildTeacherCourseHash\(["']learning-resource-generation["'],\s*courseId\)/);
  assert.match(card, />\s*学习资源生成\s*</);
});

test("teachers configure resources on the dedicated page while students keep read-only resources", async () => {
  const [knowledgePage, generationPage] = await Promise.all([
    source("../../pages/CourseKnowledge.tsx"),
    source("../../pages/LearningResourceGeneration.tsx"),
  ]);

  assert.match(knowledgePage, /isStudent\s*\?\s*<StandardLearningResources\s+readOnly/);
  assert.match(generationPage, /<StandardLearningResources\s*\/>/);
  assert.match(generationPage, /学习资源生成/);
  assert.match(generationPage, /返回课程知识/);
});
```

- [ ] **Step 2: 运行测试并确认因功能缺失而失败**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`

Expected: FAIL，错误指出缺少 `learning-resource-generation` 路由、入口或页面文件。

- [ ] **Step 3: 提交失败测试**

```powershell
git add -- Edu_AI/src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts
git commit -m "test: define learning resource generation navigation"
```

### Task 2: 注册独立课程路由

**Files:**
- Modify: `Edu_AI/src/stitch/shared.tsx`
- Modify: `Edu_AI/src/stitch/teacherRoutes.ts`
- Modify: `Edu_AI/src/stitch/course/courseNavigation.ts`
- Modify: `Edu_AI/src/stitch/App.tsx`

- [ ] **Step 1: 增加路由常量和教师课程路由类型**

在 `shared.tsx` 的 `routes` 中增加：

```ts
learningResourceGeneration: "learning-resource-generation",
```

在 `TeacherCourseRoute` 联合类型及 `readTeacherCourseLocation` 白名单中增加：

```ts
| "learning-resource-generation"
```

- [ ] **Step 2: 将新路由归入课程知识导航分组**

将 `courseNavigation.ts` 中课程知识项调整为：

```ts
{
  id: "knowledge",
  label: "课程知识",
  icon: "menu_book",
  hrefRoute: "knowledge",
  routes: ["knowledge", "graph", "learning-resource-generation"],
},
```

- [ ] **Step 3: 在应用路由表挂载独立页面**

在 `App.tsx` 增加懒加载：

```ts
const LearningResourceGenerationPage = lazy(() =>
  import("./pages/LearningResourceGeneration").then((module) => ({
    default: module.LearningResourceGenerationPage,
  })),
);
```

并在 `pages` 中增加：

```ts
[routes.learningResourceGeneration, "Learning Resource Generation", LearningResourceGenerationPage],
```

- [ ] **Step 4: 运行测试确认仍只剩页面和入口断言失败**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`

Expected: FAIL，但路由相关断言通过；失败集中在尚未创建的页面或入口。

- [ ] **Step 5: 提交路由变更**

```powershell
git add -- Edu_AI/src/stitch/shared.tsx Edu_AI/src/stitch/teacherRoutes.ts Edu_AI/src/stitch/course/courseNavigation.ts Edu_AI/src/stitch/App.tsx
git commit -m "feat: register learning resource generation route"
```

### Task 3: 增加入口并创建独立配置页

**Files:**
- Create: `Edu_AI/src/stitch/pages/LearningResourceGeneration.tsx`
- Create: `Edu_AI/src/stitch/pages/learningResourceGeneration.css`
- Modify: `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx`
- Modify: `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.css`
- Modify: `Edu_AI/src/stitch/pages/CourseKnowledge.tsx`

- [ ] **Step 1: 创建独立配置页**

```tsx
import { StandardLearningResources } from "../course/knowledge/StandardLearningResources";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { MaterialIcon } from "../shared";
import { buildTeacherCourseHash } from "../teacherRoutes";
import "./learningResourceGeneration.css";

export function LearningResourceGenerationPage() {
  const { courseId } = useCourseRoute();

  return (
    <section className="learning-resource-generation">
      <header className="learning-resource-generation__header">
        <a href={buildTeacherCourseHash("knowledge", courseId)}>
          <MaterialIcon name="arrow_back" />
          返回课程知识
        </a>
        <div>
          <span>按叶子知识点组织</span>
          <h2>学习资源生成</h2>
          <p>选择知识点，生成 AI 课堂、学习指南和练习。任务提交后可离开页面，系统会在后台继续处理。</p>
        </div>
      </header>
      <StandardLearningResources />
    </section>
  );
}
```

- [ ] **Step 2: 添加页面布局样式**

```css
.learning-resource-generation {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.learning-resource-generation__header {
  display: grid;
  gap: 14px;
  border: 1px solid var(--course-shell-line);
  border-radius: 16px;
  background: var(--course-shell-surface);
  padding: 20px;
}

.learning-resource-generation__header > a {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  gap: 6px;
  color: var(--course-shell-brand);
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
}

.learning-resource-generation__header h2 {
  margin: 4px 0 6px;
  color: var(--course-shell-ink);
  font-size: 24px;
}

.learning-resource-generation__header span,
.learning-resource-generation__header p {
  color: var(--course-shell-muted);
}

.learning-resource-generation__header p {
  margin: 0;
  font-size: 13px;
}
```

- [ ] **Step 3: 在知识库操作区增加次级入口**

在 `CourseKnowledgeBuildCard.tsx` 导入 `buildTeacherCourseHash`，并紧跟“更新知识库”按钮增加：

```tsx
{canBuild ? (
  <a
    className="course-kb-builder__secondary"
    href={buildTeacherCourseHash("learning-resource-generation", courseId)}
  >
    <MaterialIcon name="auto_stories" />
    学习资源生成
  </a>
) : null}
```

在 `CourseKnowledgeBuildCard.css` 增加：

```css
.course-kb-builder__secondary {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--course-shell-brand);
  border-radius: 10px;
  background: var(--course-shell-surface);
  padding: 9px 14px;
  color: var(--course-shell-brand);
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
}

.course-kb-builder__secondary:focus-visible {
  outline: 3px solid rgb(49 87 213 / 22%);
  outline-offset: 2px;
}
```

- [ ] **Step 4: 将教师配置移出课程知识页并保留学生只读视图**

把 `CourseKnowledge.tsx` 中无条件渲染改为：

```tsx
{isStudent ? <StandardLearningResources readOnly /> : null}
```

- [ ] **Step 5: 运行集成测试确认通过**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`

Expected: PASS，3 项测试全部通过。

- [ ] **Step 6: 提交入口与页面变更**

```powershell
git add -- Edu_AI/src/stitch/pages/LearningResourceGeneration.tsx Edu_AI/src/stitch/pages/learningResourceGeneration.css Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.css Edu_AI/src/stitch/pages/CourseKnowledge.tsx
git commit -m "feat: add learning resource generation page"
```

### Task 4: 增加浏览器验收覆盖

**Files:**
- Modify: `Edu_AI/tests/e2e/fixtures/apiRoutes.ts`
- Modify: `Edu_AI/tests/e2e/course-knowledge.spec.ts`

- [ ] **Step 1: 为测试夹具补充标准资源目录**

在通用 API 路由中加入：

```ts
if (path === `/api/courses/${physicsCourse.id}/standard-resources`) {
  return json(route, {
    course_id: physicsCourse.id,
    leaves: [
      {
        leaf_id: "mechanics",
        title: "力学",
        chapter_id: "physics",
        chapter_title: "大学物理",
        path_titles: ["大学物理", "力学"],
        slots: [
          { standard_kind: "classroom", material_type: "classroom", material_id: "standard-mechanics-classroom", review_status: "not_generated", resource: null },
          { standard_kind: "study_guide", material_type: "report", material_id: "standard-mechanics-guide", review_status: "not_generated", resource: null },
          { standard_kind: "practice", material_type: "quiz", material_id: "standard-mechanics-practice", review_status: "not_generated", resource: null },
        ],
      },
    ],
  });
}
```

- [ ] **Step 2: 写浏览器跳转验收测试**

在 `course-knowledge.spec.ts` 增加：

```ts
test("learning resource generation opens a dedicated configuration page", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("link", { name: "学习资源生成" }).click();

  await expect(teacherPage).toHaveURL(/#learning-resource-generation\?course_id=course-physics/);
  await expect(teacherPage.getByRole("heading", { name: "学习资源生成" })).toBeVisible();
  await expect(teacherPage.getByRole("link", { name: "返回课程知识" })).toBeVisible();
  await expect(teacherPage.getByText("力学", { exact: true })).toBeVisible();
  await teacherPage.getByRole("checkbox", { name: "力学" }).check();
  await expect(teacherPage.getByRole("button", { name: /生成 3 项资源/ })).toBeEnabled();
});
```

- [ ] **Step 3: 运行浏览器测试**

Run: `cd Edu_AI && pnpm exec playwright test tests/e2e/course-knowledge.spec.ts --project=chromium`

Expected: PASS，新增跳转测试及原课程知识测试全部通过。

- [ ] **Step 4: 提交验收覆盖**

```powershell
git add -- Edu_AI/tests/e2e/fixtures/apiRoutes.ts Edu_AI/tests/e2e/course-knowledge.spec.ts
git commit -m "test: cover learning resource generation navigation"
```

### Task 5: 全量验证

**Files:**
- Verify only

- [ ] **Step 1: 运行相关前端单元测试**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts src/stitch/legacyRetirement.test.ts`

Expected: PASS，无失败、异常或警告。

- [ ] **Step 2: 运行 TypeScript 构建检查**

Run: `cd Edu_AI && pnpm build`

Expected: PASS，Vite 构建成功且无 TypeScript 错误。

- [ ] **Step 3: 运行课程知识浏览器测试**

Run: `cd Edu_AI && pnpm exec playwright test tests/e2e/course-knowledge.spec.ts --project=chromium`

Expected: PASS。

- [ ] **Step 4: 检查差异边界**

Run: `git diff --check && git status --short`

Expected: `git diff --check` 无输出；状态中只包含本计划涉及文件以及用户原有的无关改动。

- [ ] **Step 5: 如仍有本功能未提交变更则提交**

```powershell
git add -- Edu_AI/src/stitch Edu_AI/tests/e2e/course-knowledge.spec.ts Edu_AI/tests/e2e/fixtures/apiRoutes.ts
git commit -m "feat: finish learning resource generation entry"
```
