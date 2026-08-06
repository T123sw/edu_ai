# Teacher Frontend Information Architecture, Generation UX, and Visual QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the teacher frontend into a coherent course workspace with one navigation model, one course-knowledge experience, one reusable generation workflow for nine resource types, responsive previews, and repeatable visual/accessibility quality gates.

**Architecture:** Build a shared course shell and shared page-state primitives before restyling individual pages. Merge the knowledge-base and knowledge-graph experiences at the information-architecture level while keeping their data responsibilities separate. Replace the oversized generation panel with a registry-driven workflow whose source selection, configuration shell, submission, job recovery, and result navigation are shared. Use Playwright at five specified viewports for structural, overflow, keyboard, and screenshot checks.

**Tech Stack:** React 18, TypeScript 5.6, Vite 6, Ant Design 5, CSS custom properties, Node test runner, Playwright 1.58.

## Global Constraints

- This plan implements SPEC stages 4, 5, and 6. Plans 1 and 2 must pass their completion gates before this plan is merged.
- Preserve the current login page’s split-screen visual direction; improve content hierarchy and states instead of replacing it with a generic admin template.
- Every course page uses the same course shell, URL-derived `course_id`, permission context, and back-navigation rules from Plan 1.
- The course knowledge base remains the document source of truth. The knowledge structure is a separate view over nodes and evidence links; it must not add a second upload workflow.
- Every generation type uses the source contract from Plan 2 and produces a durable job.
- Every visible configuration field must reach the submitted command and the stored `config_snapshot`; otherwise remove it from the UI.
- Fixed templates render immediately. AI recommendations load asynchronously, can fail independently, and never block manual configuration.
- At 1024×768, dialog/drawer titles and footers remain reachable and the content area scrolls internally.
- At 1366×768, 1440×900, 1920×1080, 1280×720, and 1024×768, the page root has no horizontal overflow.
- Keyboard navigation, visible focus, accessible labels, and WCAG AA contrast are release criteria.
- Use TDD for state/contract logic and Playwright for browser behavior. Do not approve UI solely from source inspection.

## Priority and Command Locations

- **P0 / baseline prerequisite:** Task 1 establishes reproducible evidence before layout changes.
- **P1 / teacher release:** Tasks 2–10 implement and verify the information architecture, generation experience, visual system, responsive behavior, and accessibility gate.
- Run pnpm commands from `D:\github\edu_ai\Edu_AI`.
- Run every git command from repository root `D:\github\edu_ai`; therefore git paths include the `Edu_AI/` prefix.

---

## Design System Decisions

Use the existing blue-violet product identity, but reduce decorative gradients and nested cards. Define semantic tokens in `src/stitch/styles.css` and consume them from pages/components:

```css
:root {
  --edu-color-bg-page: #f5f7fb;
  --edu-color-bg-surface: #ffffff;
  --edu-color-bg-subtle: #f0f4fa;
  --edu-color-text: #172033;
  --edu-color-text-muted: #667085;
  --edu-color-border: #d9e1ec;
  --edu-color-primary: #3157d5;
  --edu-color-primary-hover: #2648b8;
  --edu-color-danger: #c9362b;
  --edu-color-success: #16845b;
  --edu-radius-sm: 8px;
  --edu-radius-md: 12px;
  --edu-radius-lg: 16px;
  --edu-shadow-raised: 0 8px 24px rgb(23 32 51 / 10%);
  --edu-space-1: 4px;
  --edu-space-2: 8px;
  --edu-space-3: 12px;
  --edu-space-4: 16px;
  --edu-space-5: 24px;
  --edu-space-6: 32px;
  --edu-shell-sidebar-width: 232px;
  --edu-shell-header-height: 64px;
  --edu-content-max-width: 1480px;
}
```

Dark theme overrides the same semantic tokens instead of adding page-specific colors. Each page has one high-emphasis primary action. Loading, empty, error, offline, permission-denied, and conflict states use the shared components introduced in Task 2.

## Shared Frontend Contracts

```typescript
export type GenerationSourceMode = "course_auto" | "selected_documents" | "none";

export type GenerationSourceSelection = {
  mode: GenerationSourceMode;
  selectedDocumentIds: string[];
};

export type GenerationResourceType =
  | "report"
  | "lesson_plan"
  | "blog"
  | "quiz"
  | "ppt"
  | "flashcard"
  | "mind_map"
  | "game"
  | "classroom";

export type GenerationDraft<TConfig> = {
  courseId: string;
  resourceType: GenerationResourceType;
  source: GenerationSourceSelection;
  config: TConfig;
};

export type GenerationConfigDefinition<TConfig> = {
  resourceType: GenerationResourceType;
  title: string;
  description: string;
  defaultConfig: () => TConfig;
  validate: (config: TConfig) => Record<string, string>;
  serialize: (draft: GenerationDraft<TConfig>) => Record<string, unknown>;
};
```

## Target File Map

| File | Responsibility |
|---|---|
| `src/stitch/course/CourseShell.tsx` | Shared course sidebar/header/content layout |
| `src/stitch/course/courseNavigation.ts` | Canonical navigation items and active-route resolution |
| `src/stitch/components/PageState.tsx` | Loading, empty, error, offline, forbidden, and conflict states |
| `src/stitch/pages/CourseKnowledge.tsx` | Unified documents/structure course-knowledge page |
| `src/components/teacher/generation/GenerationFactory.tsx` | Registry-driven resource selection and workflow state |
| `src/components/teacher/generation/GenerationSourceSelector.tsx` | Three-mode source selector and document readiness UI |
| `src/components/teacher/generation/GenerationConfigShell.tsx` | Responsive modal/drawer with fixed title/footer |
| `src/components/teacher/generation/useGenerationSubmission.ts` | Preflight, enqueue, recover, cancel, retry, and open-result logic |
| `src/components/teacher/generation/definitions/*.ts` | Typed configuration and request mapping per resource |
| `src/components/teacher/generation/forms/*.tsx` | Resource-specific configuration forms |
| `src/components/teacher/generation/previews/*.tsx` | Resource-specific preview adapters |
| `tests/e2e/*.spec.ts` | Page, workflow, visual, overflow, and keyboard browser tests |
| `playwright.config.ts` | Five viewport projects and screenshot policy |

---

### Task 1: Establish reproducible browser fixtures and visual baselines

**Files:**
- Modify: `package.json`
- Create: `playwright.config.ts`
- Create: `tests/e2e/fixtures/teacherApp.ts`
- Create: `tests/e2e/fixtures/apiRoutes.ts`
- Create: `tests/e2e/page-baseline.spec.ts`
- Create: `docs/qa/frontend-baseline-2026-08-06.md`

**Interfaces:**
- Produces: `pnpm test:e2e`, deterministic teacher login, fixed course/resource fixtures, and five viewport projects.

- [ ] **Step 1: Add a failing smoke test for the current page set**

```typescript
import { expect, test } from "./fixtures/teacherApp";

test("teacher can traverse every core course page", async ({ teacherPage }) => {
  await teacherPage.goto("/#home");
  await teacherPage.getByRole("link", { name: "大学物理" }).click();
  await expect(teacherPage).toHaveURL(/course_id=course-physics/);
  for (const name of ["课程概览", "问答与生成", "课程知识", "AI 课堂", "课程资源", "课程设置"]) {
    await teacherPage.getByRole("link", { name }).click();
    await expect(teacherPage.getByRole("heading", { name })).toBeVisible();
  }
});
```

- [ ] **Step 2: Add the browser test command and verify the smoke test exposes current navigation mismatches**

Add scripts:

```json
"test:e2e": "playwright test",
"test:e2e:update": "playwright test --update-snapshots"
```

Run from `Edu_AI`:

```powershell
pnpm test:e2e -- tests/e2e/page-baseline.spec.ts
```

Expected: failure because the target navigation hierarchy and stable fixtures are not yet implemented.

- [ ] **Step 3: Configure deterministic five-viewport projects**

```typescript
const viewports = {
  desktop1366: { width: 1366, height: 768 },
  desktop1440: { width: 1440, height: 900 },
  desktop1920: { width: 1920, height: 1080 },
  compact1280: { width: 1280, height: 720 },
  compact1024: { width: 1024, height: 768 },
};
```

Use one project per viewport, `colorScheme: "light"`, reduced motion, fixed locale `zh-CN`, fixed timezone `Asia/Shanghai`, and `webServer.command = "pnpm dev --host 127.0.0.1"`. The API fixture must intercept auth, course, knowledge, job, classroom, and resource calls with stable timestamps and IDs.

- [ ] **Step 4: Capture an evidence inventory, not approval snapshots**

In `docs/qa/frontend-baseline-2026-08-06.md`, record each route, fixture, known defect, viewport, and initial screenshot filename. Baseline images are diagnostic; they do not become accepted golden snapshots until the corresponding task is complete.

- [ ] **Step 5: Commit the reproducible browser harness**

```powershell
git add Edu_AI/package.json Edu_AI/playwright.config.ts Edu_AI/tests/e2e Edu_AI/docs/qa/frontend-baseline-2026-08-06.md
git commit -m "test: add teacher frontend browser baseline"
```

### Task 2: Create the shared course shell, navigation model, and page states

**Files:**
- Create: `src/stitch/course/CourseShell.tsx`
- Create: `src/stitch/course/courseNavigation.ts`
- Create: `src/stitch/components/PageState.tsx`
- Modify: `src/stitch/shared.tsx`
- Modify: `src/stitch/App.tsx`
- Modify: `src/stitch/styles.css`
- Create: `src/stitch/course/courseNavigation.test.ts`
- Create: `tests/e2e/course-shell.spec.ts`

**Interfaces:**
- Consumes: `useCourseRoute()` and permission helpers from Plan 1.
- Produces: one course shell and navigation definition used by all course pages.

- [ ] **Step 1: Write navigation and state tests**

```typescript
test("course navigation has one destination per teacher concept", () => {
  assert.deepEqual(getCourseNavigation("editor").map((item) => item.id), [
    "overview", "workspace", "knowledge", "classroom", "resources", "settings",
  ]);
});

test("viewer navigation excludes mutation-only settings", () => {
  assert.equal(getCourseNavigation("viewer").some((item) => item.id === "settings"), false);
});
```

- [ ] **Step 2: Run focused tests and observe duplicated/ad hoc navigation**

```powershell
pnpm test -- src/stitch/course/courseNavigation.test.ts
```

Expected: missing module.

- [ ] **Step 3: Implement the shell and semantic tokens**

`CourseShell` owns the course breadcrumb, title, membership badge, sidebar, task-center trigger, page main landmark, and compact navigation drawer. Pages supply only `title`, `description`, optional secondary actions, and content. At widths below 1180px, collapse the sidebar to a drawer; do not squeeze the page content beneath a fixed sidebar.

`PageState` uses a discriminated union:

```typescript
type PageStateProps =
  | { kind: "loading"; title?: string }
  | { kind: "empty"; title: string; description: string; action?: ReactNode }
  | { kind: "error" | "offline" | "forbidden" | "conflict"; title: string; description: string; action?: ReactNode };
```

- [ ] **Step 4: Verify shell navigation, landmark structure, and overflow**

```powershell
pnpm test -- src/stitch/course/courseNavigation.test.ts
pnpm test:e2e -- tests/e2e/course-shell.spec.ts
```

Browser assertions: one `main` landmark, one active navigation item, no duplicate course title blocks, `document.documentElement.scrollWidth <= document.documentElement.clientWidth`, and keyboard-openable compact menu.

- [ ] **Step 5: Commit the shared course shell**

```powershell
git add Edu_AI/src/stitch/course/CourseShell.tsx Edu_AI/src/stitch/course/courseNavigation.ts Edu_AI/src/stitch/components/PageState.tsx Edu_AI/src/stitch/shared.tsx Edu_AI/src/stitch/App.tsx Edu_AI/src/stitch/styles.css Edu_AI/src/stitch/course/courseNavigation.test.ts Edu_AI/tests/e2e/course-shell.spec.ts
git commit -m "feat: add unified course workspace shell"
```

### Task 3: Simplify login, course home, overview, settings, and profile hierarchy

**Files:**
- Modify: `src/stitch/pages/LoginPage.tsx`
- Modify: `src/stitch/pages/LoginPage.css`
- Modify: `src/stitch/pages/HomeDashboard.tsx`
- Modify: `src/stitch/pages/HomeDashboard.css`
- Modify: `src/stitch/pages/CourseDetail.tsx`
- Modify: `src/stitch/pages/CourseEdit.tsx`
- Modify: `src/stitch/pages/Profile.tsx`
- Modify: `src/stitch/api/courses.ts`
- Create: `src/stitch/pages/courseCardPresentation.test.ts`
- Create: `tests/e2e/core-pages.spec.ts`

**Interfaces:**
- Consumes: real course counters, user identity, membership role, and course revision from Plan 1.
- Produces: one course list, factual overview cards, teacher-oriented copy, and permission-aware settings.

- [ ] **Step 1: Write tests rejecting decorative progress and duplicate course entry points**

```typescript
test("course card presentation contains only factual metrics", () => {
  const card = toCourseCardPresentation(courseFixture);
  assert.equal("progress" in card, false);
  assert.deepEqual(card.metrics, [
    { label: "课程资料", value: 4 },
    { label: "课程资源", value: 7 },
    { label: "进行中任务", value: 1 },
  ]);
});
```

- [ ] **Step 2: Run and reproduce the current decorative/randomized output**

```powershell
pnpm test -- src/stitch/pages/courseCardPresentation.test.ts
```

Expected: current adapter still creates non-business progress values or the presentation helper is absent.

- [ ] **Step 3: Implement page-specific hierarchy**

- Login: retain split layout; show system name, role explanation, account help, concrete login error, and development demo-account hint only when runtime config explicitly enables it.
- Home: one searchable course grid; remove the separate carousel/list duplication; show role, last update, document/resource counts, and active jobs.
- Overview: show concise description/objectives, indexing state, latest resources, active jobs, and six quick entries; do not repeat a large hero containing the same title/description.
- Settings: editor form for owner/editor, factual read-only view for viewer, and explicit 409 conflict recovery actions “重新加载最新版本” and “复制我的修改”.
- Profile: show actual username, display name, system role, and course count; expose runtime/system settings only to permitted roles.

- [ ] **Step 4: Run browser checks at all five viewports**

```powershell
pnpm test -- src/stitch/pages/courseCardPresentation.test.ts
pnpm test:e2e -- tests/e2e/core-pages.spec.ts
```

Expected: one course entry, no random progress, readable primary actions in light/dark theme, correct viewer settings, and no page-level horizontal scroll.

- [ ] **Step 5: Commit the core-page hierarchy**

```powershell
git add Edu_AI/src/stitch/pages/LoginPage.tsx Edu_AI/src/stitch/pages/LoginPage.css Edu_AI/src/stitch/pages/HomeDashboard.tsx Edu_AI/src/stitch/pages/HomeDashboard.css Edu_AI/src/stitch/pages/CourseDetail.tsx Edu_AI/src/stitch/pages/CourseEdit.tsx Edu_AI/src/stitch/pages/Profile.tsx Edu_AI/src/stitch/api/courses.ts Edu_AI/src/stitch/pages/courseCardPresentation.test.ts Edu_AI/tests/e2e/core-pages.spec.ts
git commit -m "feat: clarify teacher core page hierarchy"
```

### Task 4: Merge course documents and knowledge structure into one course-knowledge experience

**Files:**
- Create: `src/stitch/pages/CourseKnowledge.tsx`
- Create: `src/stitch/course/knowledge/KnowledgeDocumentsView.tsx`
- Create: `src/stitch/course/knowledge/KnowledgeStructureView.tsx`
- Create: `src/stitch/course/knowledge/KnowledgeDocumentStatus.tsx`
- Modify: `src/stitch/pages/CourseKnowledgeBase.tsx`
- Modify: `src/stitch/pages/KnowledgeGraph.tsx`
- Modify: `src/stitch/teacherRoutes.ts`
- Modify: `src/stitch/teacherRoutes.test.ts`
- Create: `tests/e2e/course-knowledge.spec.ts`

**Interfaces:**
- Consumes: the single knowledge-document API and knowledge-graph evidence links from Plan 2.
- Produces: `#knowledge?course_id={course_id}&view=documents|structure` with no duplicate uploader.

- [ ] **Step 1: Add route and source assertions for the unified page**

```typescript
test("course knowledge view is encoded without losing course identity", () => {
  assert.equal(buildTeacherCourseHash("knowledge", "c1", { view: "structure" }), "#knowledge?course_id=c1&view=structure");
  assert.deepEqual(readTeacherCourseLocation("#knowledge?course_id=c1&view=documents"), {
    route: "knowledge", courseId: "c1", view: "documents",
  });
});
```

- [ ] **Step 2: Run and expose the two-page/two-upload structure**

```powershell
pnpm test -- src/stitch/teacherRoutes.test.ts
pnpm test:e2e -- tests/e2e/course-knowledge.spec.ts
```

Expected: current routes separate knowledge base/graph and browser test finds more than one upload entry.

- [ ] **Step 3: Implement two views with distinct responsibilities**

Documents view: discoverable upload action above the list, compact rows, filename/type/status/chunks/updated time, preview, indexing retry, and error detail. Processing/failed documents cannot be selected as evidence.

Structure view: graph canvas, structure settings, node detail, and evidence-document links. Remove textbook/file upload from this view. “关联资料” opens the existing course document picker and stores references rather than copying a file. At widths below 1180px, show `设置 / 画布 / 节点详情` as tabs; the canvas receives at least 50% of available width when side-by-side.

Keep old `knowledge-base` and `graph` hashes as transition redirects to the appropriate `knowledge` view; all new navigation and writes target only the unified route.

- [ ] **Step 4: Verify one uploader, linked evidence, canvas size, and deep-link refresh**

```powershell
pnpm test -- src/stitch/teacherRoutes.test.ts
pnpm test:e2e -- tests/e2e/course-knowledge.spec.ts
```

Expected: exactly one course-document uploader, structure links existing documents, copied URLs preserve course/view, and the canvas remains operable at 1024×768.

- [ ] **Step 5: Commit unified course knowledge**

```powershell
git add Edu_AI/src/stitch/pages/CourseKnowledge.tsx Edu_AI/src/stitch/course/knowledge Edu_AI/src/stitch/pages/CourseKnowledgeBase.tsx Edu_AI/src/stitch/pages/KnowledgeGraph.tsx Edu_AI/src/stitch/teacherRoutes.ts Edu_AI/src/stitch/teacherRoutes.test.ts Edu_AI/tests/e2e/course-knowledge.spec.ts
git commit -m "feat: unify course knowledge experience"
```

### Task 5: Restructure the question workspace and introduce the shared generation factory

**Files:**
- Create: `src/components/teacher/generation/GenerationFactory.tsx`
- Create: `src/components/teacher/generation/generationRegistry.ts`
- Create: `src/components/teacher/generation/GenerationSourceSelector.tsx`
- Create: `src/components/teacher/generation/GenerationConfigShell.tsx`
- Create: `src/components/teacher/generation/GenerationTaskStatus.tsx`
- Create: `src/components/teacher/generation/useGenerationSubmission.ts`
- Modify: `src/stitch/pages/AIWorkspace.tsx`
- Modify: `src/components/teacher/SourcePanel.tsx`
- Modify: `src/components/teacher/StudioPanel.tsx`
- Create: `src/components/teacher/generation/generationSourceSelection.test.ts`
- Create: `src/components/teacher/generation/generationRegistry.test.ts`
- Create: `tests/e2e/generation-factory-shell.spec.ts`

**Interfaces:**
- Consumes: Plan 2 preflight/direct-job APIs.
- Produces: shared source selector, registry, responsive configuration shell, and job lifecycle hook.

- [ ] **Step 1: Write source, registry, and serialization tests**

```typescript
test("switching away from selected documents clears stale IDs", () => {
  assert.deepEqual(changeSourceMode({ mode: "selected_documents", selectedDocumentIds: ["doc-1"] }, "none"), {
    mode: "none", selectedDocumentIds: [],
  });
});

test("registry contains exactly nine distinct resources", () => {
  assert.deepEqual(generationRegistry.map((item) => item.resourceType), [
    "report", "lesson_plan", "blog", "quiz", "ppt", "flashcard", "mind_map", "game", "classroom",
  ]);
});
```

- [ ] **Step 2: Run tests and prove the factory is currently branch-driven**

```powershell
pnpm test -- src/components/teacher/generation/generationSourceSelection.test.ts src/components/teacher/generation/generationRegistry.test.ts
```

Expected: missing modules; `StudioPanel.tsx` remains the source of duplicated resource branches.

- [ ] **Step 3: Implement the five-step workflow and responsive workspace**

```text
选择资源类型 → 确认资料范围 → 配置内容 → 可选预览/确认 → 后台生成并进入课程资源
```

`GenerationSourceSelector` shows three labeled radio cards:

- 自动使用课程资料: document count and indexing readiness; no checkbox list.
- 仅使用选中文档: ready-document picker; disabled documents display processing/failure reason.
- 不使用资料: clear statement that generation uses topic/configuration only.

On submit, `useGenerationSubmission` calls preflight, enqueues the job, stores `{jobId, draft}` in local storage keyed by user/course, polls owner-scoped job status, supports cancel/retry, and opens the published course resource after completion. Retry starts from the retained draft. Do not store tokens or generated content in this draft cache.

At desktop width, question/chat remains primary and source/factory are switchable side panels. At medium width, render one drawer/tab panel rather than three fixed columns. Opening the factory must not apply an opaque overlay that visually disables the chat.

- [ ] **Step 4: Retire duplicate branches with characterization coverage**

Keep `StudioPanel.tsx` temporarily as a compatibility adapter that renders `GenerationFactory`. Delete the duplicated quiz branch, unreachable legacy configuration modal, and resource-specific source validation only after registry tests prove all nine entries. Record deleted branches in the commit description.

- [ ] **Step 5: Verify keyboard flow, 1024×768 footer reachability, and job recovery**

```powershell
pnpm test -- src/components/teacher/generation/generationSourceSelection.test.ts src/components/teacher/generation/generationRegistry.test.ts
pnpm test:e2e -- tests/e2e/generation-factory-shell.spec.ts
```

Expected: keyboard can select type/source and submit; fixed header/footer stay visible; refresh restores the active job; one failed recommendation does not block manual configuration.

- [ ] **Step 6: Commit the shared generation shell**

```powershell
git add Edu_AI/src/components/teacher/generation Edu_AI/src/stitch/pages/AIWorkspace.tsx Edu_AI/src/components/teacher/SourcePanel.tsx Edu_AI/src/components/teacher/StudioPanel.tsx Edu_AI/tests/e2e/generation-factory-shell.spec.ts
git commit -m "feat: add shared teacher generation workflow"
```

### Task 6: Implement report, lesson-plan, and blog configuration definitions

**Files:**
- Create: `src/components/teacher/generation/definitions/report.ts`
- Create: `src/components/teacher/generation/definitions/lessonPlan.ts`
- Create: `src/components/teacher/generation/definitions/blog.ts`
- Create: `src/components/teacher/generation/forms/ReportForm.tsx`
- Create: `src/components/teacher/generation/forms/LessonPlanForm.tsx`
- Create: `src/components/teacher/generation/forms/BlogForm.tsx`
- Modify: `src/components/teacher/ReportEntryModal.tsx`
- Modify: `src/components/teacher/LessonPlanEntryModal.tsx`
- Create: `src/components/teacher/generation/definitions/textResources.test.ts`
- Create: `tests/e2e/generation-text-resources.spec.ts`

**Interfaces:**
- Produces: typed configs and exact API mappings for three long-form resources.

- [ ] **Step 1: Write exact field-to-payload tests**

```typescript
test("blog tone and length reach the durable command", () => {
  const payload = blogDefinition.serialize(draft({
    topic: "量子隧穿", audience: "本科一年级", tone: "通俗", length: "long",
    structure: "概念—例子—总结", specialRequirements: "加入一个生活类比",
  }));
  assert.equal(payload.tone, "通俗");
  assert.equal(payload.length, "long");
  assert.equal(payload.special_requirements, "加入一个生活类比");
});
```

- [ ] **Step 2: Run and reproduce dropped or ambiguous fields**

```powershell
pnpm test -- src/components/teacher/generation/definitions/textResources.test.ts
```

Expected: definitions do not exist and current blog/lesson paths do not provide a single auditable mapping.

- [ ] **Step 3: Implement the three configurations**

- Report: template (`brief`, `detailed`, `study_plan`, `custom`), topic, audience, depth, structure emphasis, special requirements. Fixed templates are immediate; recommended directions populate asynchronously without replacing user edits.
- Lesson plan: group into basic information, teaching objectives, teaching process, and supplementary requirements. Required: topic, audience/grade, duration, objectives. Any extracted suggestion is editable and labeled “根据资料建议”. The primary action is “生成教案大纲” when outline preview is enabled, otherwise “开始生成”.
- Blog: topic, audience, tone, length, structure, and special requirements. Remove any UI field not supported by the Plan 2 command. Closing and reopening during the same workflow restores the draft.

- [ ] **Step 4: Verify payload snapshots and long-form dialog layout**

```powershell
pnpm test -- src/components/teacher/generation/definitions/textResources.test.ts
pnpm test:e2e -- tests/e2e/generation-text-resources.spec.ts
```

Expected: every visible field appears in the intercepted request and job configuration snapshot; 1024×768 footers are reachable; recommendation failures retain manual forms.

- [ ] **Step 5: Commit text-resource configurations**

```powershell
git add Edu_AI/src/components/teacher/generation/definitions/report.ts Edu_AI/src/components/teacher/generation/definitions/lessonPlan.ts Edu_AI/src/components/teacher/generation/definitions/blog.ts Edu_AI/src/components/teacher/generation/forms/ReportForm.tsx Edu_AI/src/components/teacher/generation/forms/LessonPlanForm.tsx Edu_AI/src/components/teacher/generation/forms/BlogForm.tsx Edu_AI/src/components/teacher/ReportEntryModal.tsx Edu_AI/src/components/teacher/LessonPlanEntryModal.tsx Edu_AI/src/components/teacher/generation/definitions/textResources.test.ts Edu_AI/tests/e2e/generation-text-resources.spec.ts
git commit -m "feat: align long-form generation configs"
```

### Task 7: Implement quiz, flashcard, and game configuration definitions

**Files:**
- Create: `src/components/teacher/generation/definitions/quiz.ts`
- Create: `src/components/teacher/generation/definitions/flashcard.ts`
- Create: `src/components/teacher/generation/definitions/game.ts`
- Create: `src/components/teacher/generation/forms/QuizForm.tsx`
- Create: `src/components/teacher/generation/forms/FlashcardForm.tsx`
- Create: `src/components/teacher/generation/forms/GameForm.tsx`
- Modify: `src/components/teacher/QuizEntryModal.tsx`
- Modify: `src/components/teacher/FlashcardEntryModal.tsx`
- Modify: `src/components/teacher/GameEntryModal.tsx`
- Create: `src/components/teacher/generation/definitions/practiceResources.test.ts`
- Create: `tests/e2e/generation-practice-resources.spec.ts`

**Interfaces:**
- Produces: typed configs and interactive previews for three practice resources.

- [ ] **Step 1: Write validation and serialization tests**

```typescript
test("quiz answer and explanation switches are independent", () => {
  const payload = quizDefinition.serialize(draft({
    topic: "力学", audience: "大学一年级", difficulty: "medium", count: 10,
    questionTypes: ["single_choice", "calculation"], includeAnswers: true, includeExplanations: false,
  }));
  assert.equal(payload.include_answers, true);
  assert.equal(payload.include_explanations, false);
});

test("game card count is required and bounded", () => {
  assert.equal(gameDefinition.validate(gameConfig({ cardCount: 0 })).cardCount, "卡片数量需为 4–30");
});
```

- [ ] **Step 2: Run tests and identify duplicate quiz behavior**

```powershell
pnpm test -- src/components/teacher/generation/definitions/practiceResources.test.ts
```

Expected: missing definitions and current duplicate quiz branches cannot share one validation result.

- [ ] **Step 3: Implement precise practice configurations**

- Quiz: topic, audience, difficulty, count, question types, answers, explanations. When source mode is `none`, topic remains sufficient. Count/type selections must be preserved exactly.
- Flashcard: title, count, difficulty, category, and show-source setting. Validate title as plain text; never interpret it as an external URL.
- Game: selectable keyboard-operable buttons for classification, drag-match, and memory; topic, card/question count, difficulty, classroom duration, and a short configuration preview. Preserve draft and error when retrying.

- [ ] **Step 4: Verify keyboard selection, payloads, and previews**

```powershell
pnpm test -- src/components/teacher/generation/definitions/practiceResources.test.ts
pnpm test:e2e -- tests/e2e/generation-practice-resources.spec.ts
```

Expected: all cards have button semantics/focus, configurations match intercepted payloads, quiz answers can collapse, flashcards flip one at a time, and game previews are playable.

- [ ] **Step 5: Commit practice-resource configurations**

```powershell
git add Edu_AI/src/components/teacher/generation/definitions/quiz.ts Edu_AI/src/components/teacher/generation/definitions/flashcard.ts Edu_AI/src/components/teacher/generation/definitions/game.ts Edu_AI/src/components/teacher/generation/forms/QuizForm.tsx Edu_AI/src/components/teacher/generation/forms/FlashcardForm.tsx Edu_AI/src/components/teacher/generation/forms/GameForm.tsx Edu_AI/src/components/teacher/QuizEntryModal.tsx Edu_AI/src/components/teacher/FlashcardEntryModal.tsx Edu_AI/src/components/teacher/GameEntryModal.tsx Edu_AI/src/components/teacher/generation/definitions/practiceResources.test.ts Edu_AI/tests/e2e/generation-practice-resources.spec.ts
git commit -m "feat: align practice generation configs"
```

### Task 8: Implement PPT, mind-map, and AI-classroom definitions and previews

**Files:**
- Create: `src/components/teacher/generation/definitions/ppt.ts`
- Create: `src/components/teacher/generation/definitions/mindMap.ts`
- Create: `src/components/teacher/generation/definitions/classroom.ts`
- Create: `src/components/teacher/generation/forms/PptForm.tsx`
- Create: `src/components/teacher/generation/forms/MindMapForm.tsx`
- Create: `src/components/teacher/generation/forms/ClassroomForm.tsx`
- Create: `src/components/teacher/generation/previews/PptOutlineEditor.tsx`
- Modify: `src/components/teacher/PptEntryPanel.tsx`
- Modify: `src/components/teacher/ClassroomGenerationEntry.tsx`
- Modify: `src/stitch/pages/ClassroomStudio.tsx`
- Create: `src/components/teacher/generation/definitions/visualResources.test.ts`
- Create: `tests/e2e/generation-visual-resources.spec.ts`

**Interfaces:**
- Produces: typed visual-resource configs, structured PPT outline editing, and one classroom entry implementation.

- [ ] **Step 1: Write exact mapping and shared-entry tests**

```typescript
test("mind-map description and depth are serialized", () => {
  const payload = mindMapDefinition.serialize(draft({ topic: "电磁学", description: "突出概念关系", depth: 4 }));
  assert.equal(payload.description, "突出概念关系");
  assert.equal(payload.depth, 4);
});

test("factory and classroom page use the same definition", () => {
  assert.equal(generationRegistry.find((item) => item.resourceType === "classroom")?.definition, classroomDefinition);
  assert.equal(classroomPageDefinition, classroomDefinition);
});
```

- [ ] **Step 2: Run and reproduce dropped visual-resource fields**

```powershell
pnpm test -- src/components/teacher/generation/definitions/visualResources.test.ts
```

Expected: current PPT style, mind-map description, classroom voice, or source mode lacks one shared audited mapping.

- [ ] **Step 3: Implement visual-resource configurations**

- PPT: title, subtitle, audience, objective, slide count, focus, style, and template with recognizable visual thumbnails. Generate an outline first; edit slides through fields for title, key points, speaker notes, and visual instruction. Never expose raw JSON. Add/remove/reorder slides with keyboard-accessible controls.
- Mind map: topic, description, depth, source mode. Label every UI/result as “思维导图”; do not write into the course knowledge structure unless a separate explicit future action is invoked.
- AI classroom: topic, audience, objectives, scene count/duration, teaching style, voice enabled, voice choice when enabled, and source mode. The generation-factory entry and standalone classroom page render the same form and submit hook.

- [ ] **Step 4: Verify structured editing, shared classroom behavior, and no dialog overflow**

```powershell
pnpm test -- src/components/teacher/generation/definitions/visualResources.test.ts
pnpm test:e2e -- tests/e2e/generation-visual-resources.spec.ts
```

Expected: PPT outline edits survive submission, no JSON textarea exists, mind-map fields reach payload, classroom entries emit identical requests, and every footer is reachable at 1024×768.

- [ ] **Step 5: Commit visual-resource configurations**

```powershell
git add Edu_AI/src/components/teacher/generation/definitions/ppt.ts Edu_AI/src/components/teacher/generation/definitions/mindMap.ts Edu_AI/src/components/teacher/generation/definitions/classroom.ts Edu_AI/src/components/teacher/generation/forms/PptForm.tsx Edu_AI/src/components/teacher/generation/forms/MindMapForm.tsx Edu_AI/src/components/teacher/generation/forms/ClassroomForm.tsx Edu_AI/src/components/teacher/generation/previews/PptOutlineEditor.tsx Edu_AI/src/components/teacher/PptEntryPanel.tsx Edu_AI/src/components/teacher/ClassroomGenerationEntry.tsx Edu_AI/src/stitch/pages/ClassroomStudio.tsx Edu_AI/src/components/teacher/generation/definitions/visualResources.test.ts Edu_AI/tests/e2e/generation-visual-resources.spec.ts
git commit -m "feat: align visual generation configs"
```

### Task 9: Make course resources and AI-classroom playback responsive and type-aware

**Files:**
- Modify: `src/stitch/pages/CourseResources.tsx`
- Modify: `src/stitch/api/courseMaterialPresentation.ts`
- Modify: `src/components/teacher/ReportArtifactPreview.tsx`
- Modify: `src/components/teacher/LessonPlanArtifactPreview.tsx`
- Modify: `src/components/teacher/QuizArtifactPreview.tsx`
- Modify: `src/components/teacher/FlashcardArtifactPreview.tsx`
- Modify: `src/components/teacher/MindMapArtifactPreview.tsx`
- Modify: `src/components/teacher/GameArtifactPreview.tsx`
- Create: `src/components/teacher/generation/previews/BlogArtifactPreview.tsx`
- Create: `src/components/teacher/generation/previews/PptArtifactPreview.tsx`
- Modify: `src/stitch/pages/ClassroomPlayer.tsx`
- Create: `src/stitch/pages/resourcePreviewConstraints.test.ts`
- Create: `tests/e2e/resources-and-classroom.spec.ts`

**Interfaces:**
- Consumes: course-shared artifact manifests from Plans 1–2.
- Produces: type-aware resource previews, factual metadata, constrained content, and a first-screen-operable classroom player.

- [ ] **Step 1: Write presentation and hostile-content constraint tests**

```typescript
test("resource metadata exposes provenance without internal IDs", () => {
  const view = toCourseMaterialPresentation(materialFixture);
  assert.deepEqual(view.meta.map((item) => item.label), ["类型", "创建者", "资料范围", "创建时间"]);
  assert.equal(JSON.stringify(view).includes("rag_index_key"), false);
});

test("preview constraint class is applied to rich content", () => {
  assert.match(REPORT_PREVIEW_CLASSNAME, /edu-rich-preview/);
});
```

- [ ] **Step 2: Run tests and reproduce medium-width overflow or generic previews**

```powershell
pnpm test -- src/stitch/pages/resourcePreviewConstraints.test.ts src/stitch/api/courseMaterialPresentation.test.ts
```

Expected: missing constraints or incomplete type-specific presentation.

- [ ] **Step 3: Implement responsive list/preview behavior**

Desktop retains filter/list/preview columns. Below 1180px, show list above preview or open preview in a drawer; never compress three columns into unreadable widths. Display title, type, creator, source mode, created time, and status. Apply `.edu-rich-preview` rules to Markdown, tables, code, links, images, long words, and citations:

```css
.edu-rich-preview { min-width: 0; overflow-wrap: anywhere; }
.edu-rich-preview pre { max-width: 100%; overflow: auto; }
.edu-rich-preview table { display: block; max-width: 100%; overflow-x: auto; }
.edu-rich-preview img { max-width: 100%; height: auto; }
```

Previews: report/blog/lesson as structured rich text; quiz answers collapsible; flashcards flip individually; PPT paged; mind map zoom/pan; game playable; classroom opens the player.

- [ ] **Step 4: Recompose the classroom player first screen**

At 1280×720, keep stage, play/pause, previous/next, progress, scene title, and volume/voice status visible without scrolling. Move scene catalog, transcript, export detail, and technical metadata into collapsible side/bottom panels. Do not show raw internal IDs or renderer type names to teachers. The back link always targets the current course’s AI-classroom list.

- [ ] **Step 5: Verify hostile samples and classroom controls**

```powershell
pnpm test -- src/stitch/pages/resourcePreviewConstraints.test.ts src/stitch/api/courseMaterialPresentation.test.ts
pnpm test:e2e -- tests/e2e/resources-and-classroom.spec.ts
```

Use fixtures containing a 200-character unbroken title, wide table, long URL, code block, large image, and long citation. Expected: page root does not overflow; only table/code containers scroll internally; core classroom controls are visible at 1280×720.

- [ ] **Step 6: Commit responsive resource and classroom presentation**

```powershell
git add Edu_AI/src/stitch/pages/CourseResources.tsx Edu_AI/src/stitch/api/courseMaterialPresentation.ts Edu_AI/src/components/teacher/ReportArtifactPreview.tsx Edu_AI/src/components/teacher/LessonPlanArtifactPreview.tsx Edu_AI/src/components/teacher/QuizArtifactPreview.tsx Edu_AI/src/components/teacher/FlashcardArtifactPreview.tsx Edu_AI/src/components/teacher/MindMapArtifactPreview.tsx Edu_AI/src/components/teacher/GameArtifactPreview.tsx Edu_AI/src/components/teacher/generation/previews/BlogArtifactPreview.tsx Edu_AI/src/components/teacher/generation/previews/PptArtifactPreview.tsx Edu_AI/src/stitch/pages/ClassroomPlayer.tsx Edu_AI/src/stitch/pages/resourcePreviewConstraints.test.ts Edu_AI/tests/e2e/resources-and-classroom.spec.ts
git commit -m "feat: improve course resource previews"
```

### Task 10: Complete visual, responsive, accessibility, and deprecation gates

**Files:**
- Create: `tests/e2e/visual-regression.spec.ts`
- Create: `tests/e2e/keyboard-accessibility.spec.ts`
- Create: `tests/e2e/overflow-regression.spec.ts`
- Modify: `src/stitch/legacyRetirement.test.ts`
- Modify: `docs/qa/frontend-baseline-2026-08-06.md`
- Create: `docs/qa/teacher-frontend-release-checklist.md`
- Modify: `docs/superpowers/specs/2026-08-06-course-centered-teacher-experience-design.md` only after evidence exists.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: accepted screenshots, automated layout assertions, keyboard evidence, and an explicit legacy-removal list.

- [ ] **Step 1: Enumerate the page/state/viewport matrix**

Test these pages: login, course home, course overview, question/generation, course knowledge documents, course knowledge structure, AI classroom list, classroom player, course resources, course settings, and profile.

For data pages cover loaded, loading, empty, error, and permission-denied where applicable. For generation cover each of nine configuration shells plus success, failed, canceled, and recovered-job states. Run light theme on every viewport and dark theme on 1366×768 and 1024×768.

- [ ] **Step 2: Add structural overflow assertions**

```typescript
await expect.poll(() => page.evaluate(() => ({
  root: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  body: document.body.scrollWidth <= document.body.clientWidth,
}))).toEqual({ root: true, body: true });
```

For every open dialog/drawer, assert the title and primary action intersect the viewport. Assert no page contains three nested independently scrollable ancestors above the focused control.

- [ ] **Step 3: Add keyboard and accessibility checks**

Without pointer input, perform login, enter a course, switch course-knowledge views, select a document, choose a generation type/source mode, complete a minimum form, submit, cancel a job, open a resource, flip a flashcard, select a game type, and operate classroom playback. Check visible focus and accessible names for icon buttons. Check critical text/background color pairs with a WCAG contrast helper at AA thresholds.

- [ ] **Step 4: Remove legacy mainline code and assert it stays removed**

Update `legacyRetirement.test.ts` to fail if the following return:

- old knowledge-base/graph navigation items rather than redirects;
- a knowledge-graph upload control;
- duplicate quiz generation branches;
- unreachable legacy configuration modal identifiers;
- raw PPT JSON editor;
- page-local course fallback from `localStorage`;
- random/decorative course progress generation.

- [ ] **Step 5: Run the complete frontend gate**

```powershell
pnpm test
pnpm lint
pnpm build
pnpm test:e2e
```

Expected: unit/contract tests, lint, production build, five-viewport browser suite, visual snapshots, overflow assertions, and keyboard scenarios all pass. Console assertions permit no new React key, invalid DOM nesting, uncontrolled/controlled form, or deprecated-property warnings.

- [ ] **Step 6: Perform human visual review and record decisions**

Review the accepted screenshots page by page. Record reviewer/date, viewport, light/dark result, defects found, fix commit, and final disposition in `docs/qa/teacher-frontend-release-checklist.md`. Automated snapshots detect change; human review decides whether hierarchy, clarity, and visual quality are acceptable.

- [ ] **Step 7: Check Spec items backed by evidence and commit the gate**

```powershell
git add Edu_AI/tests/e2e Edu_AI/src/stitch/legacyRetirement.test.ts Edu_AI/docs/qa/frontend-baseline-2026-08-06.md Edu_AI/docs/qa/teacher-frontend-release-checklist.md Edu_AI/docs/superpowers/specs/2026-08-06-course-centered-teacher-experience-design.md
git commit -m "test: enforce teacher frontend quality gate"
```

Only mark SPEC stage 4–6 acceptance items complete when the checklist points to an automated test, accepted screenshot, or named manual review entry.

---

## Plan 3 Completion Gate

The teacher frontend is ready for the later P2 student/Agent plans only when all of the following are evidenced:

- Login leads to one clear course list and every course page uses one shared shell.
- Course overview, question/generation, course knowledge, AI classroom, resources, and settings are discoverable without duplicate concepts.
- Course knowledge has one document uploader and a separate structure view referencing the same documents.
- All nine resources use the same source selector, configuration shell, preflight, durable job, recovery, and result-navigation model.
- Every visible resource configuration field is found in the intercepted request and persisted configuration snapshot.
- Report, lesson plan, blog, quiz, PPT, flashcard, mind map, game, and classroom each have a type-appropriate result experience.
- Five viewport projects have no page-level horizontal overflow and no unreachable dialog action.
- Classroom core playback controls fit in the first 1280×720 viewport.
- Main workflows are keyboard operable, focus is visible, critical contrast is WCAG AA, and icon actions have accessible names.
- Old duplicate navigation, generation branches, raw PPT JSON editing, decorative course progress, and page-local course fallbacks are removed or reduced to explicit redirects.
- Unit tests, lint, production build, browser tests, screenshots, and human review all pass.

## Deferred P2 Follow-up

After Plans 1–3 are accepted, write separate plans for:

1. Student minimum access: reuse the same course facts, knowledge, Q&A, and published resources; add viewer-focused learning tools without copying teacher management surfaces.
2. Agent performance and memory: measure P50/P95 latency first, then optimize routing/cache/tool concurrency and add course-scoped, visible, deletable memory.

Do not begin either P2 plan while the course data boundary, generation reliability, or teacher quality gates remain incomplete.
