# Course Top Workbar Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the persistent course sidebar with a responsive top workbar whose five destinations, labels, order, overview behavior, and teacher-only settings menu match the approved design.

**Architecture:** Keep route ownership in `courseNavigation.ts` and presentation in `CourseShell.tsx`. Separate the five persistent workbar items from route metadata so overview and settings remain valid course routes without appearing in navigation; use the existing role-aware hash resolver for teacher/student destinations.

**Tech Stack:** React 18, TypeScript, CSS, Node test runner with `tsx`, Vite.

---

## File map

- `Edu_AI/src/stitch/course/courseNavigation.ts`: canonical workbar order, labels, route grouping, and page-title metadata.
- `Edu_AI/src/stitch/course/courseNavigation.test.ts`: behavior tests for the canonical navigation model.
- `Edu_AI/src/stitch/course/CourseShell.tsx`: top workbar, teacher course menu, mobile top menu, active state, and role-aware links.
- `Edu_AI/src/stitch/course/CourseShell.test.ts`: source-contract regression test for removal of sidebar/drawer markup and preservation of teacher/student rules.
- `Edu_AI/src/stitch/styles.css`: desktop and responsive visual layout for the top workbar and menus.

### Task 1: Lock the canonical workbar model with failing tests

**Files:**
- Modify: `Edu_AI/src/stitch/course/courseNavigation.test.ts`

- [ ] **Step 1: Replace the old seven-item assertions with the approved five-item contract**

```ts
import assert from "node:assert/strict";
import test from "node:test";

import {
  getCourseNavigation,
  getCoursePageTitle,
  isCourseWorkspaceRoute,
} from "./courseNavigation.ts";

test("course workbar exposes the approved destinations in order", () => {
  assert.deepEqual(
    getCourseNavigation().map(({ id, label }) => [id, label]),
    [
      ["workspace", "工作台"],
      ["knowledge", "课程知识"],
      ["classroom", "AI课堂"],
      ["resources", "资源管理"],
      ["learning", "学习任务"],
    ],
  );
});

test("overview and settings stay routable without occupying the workbar", () => {
  const ids = getCourseNavigation().map((item) => item.id);
  assert.equal(ids.includes("overview"), false);
  assert.equal(ids.includes("settings"), false);
  assert.equal(getCoursePageTitle("course-detail"), "课程概览");
  assert.equal(getCoursePageTitle("edit"), "课程设置");
  assert.equal(isCourseWorkspaceRoute("course-detail"), true);
  assert.equal(isCourseWorkspaceRoute("edit"), true);
});

test("knowledge graph deep links belong to course knowledge", () => {
  const knowledge = getCourseNavigation().find((item) => item.id === "knowledge");
  assert.deepEqual(knowledge?.routes, ["knowledge", "graph"]);
});
```

- [ ] **Step 2: Run the focused test and verify the expected failure**

Run: `pnpm test -- src/stitch/course/courseNavigation.test.ts`

Expected: FAIL because `getCourseNavigation` still expects a role and returns overview/settings with the old labels and order.

- [ ] **Step 3: Commit only after Task 2 makes the test pass**

The failing test and its minimal implementation are committed together in Task 2 so the branch never records a knowingly red commit.

### Task 2: Separate workbar navigation from course route metadata

**Files:**
- Modify: `Edu_AI/src/stitch/course/courseNavigation.ts`
- Test: `Edu_AI/src/stitch/course/courseNavigation.test.ts`

- [ ] **Step 1: Replace the navigation types and data with a five-item workbar definition**

```ts
import type { TeacherCourseRoute } from "../teacherRoutes";

export type CourseNavigationId =
  | "workspace"
  | "knowledge"
  | "classroom"
  | "resources"
  | "learning";

export type CourseNavigationItem = {
  id: CourseNavigationId;
  label: string;
  icon: string;
  hrefRoute: TeacherCourseRoute;
  routes: readonly TeacherCourseRoute[];
};

const courseNavigation: readonly CourseNavigationItem[] = [
  { id: "workspace", label: "工作台", icon: "auto_awesome", hrefRoute: "ai", routes: ["ai"] },
  { id: "knowledge", label: "课程知识", icon: "menu_book", hrefRoute: "knowledge", routes: ["knowledge", "graph"] },
  { id: "classroom", label: "AI课堂", icon: "play_circle", hrefRoute: "classroom-studio", routes: ["classroom-studio"] },
  { id: "resources", label: "资源管理", icon: "folder_open", hrefRoute: "resources", routes: ["resources"] },
  { id: "learning", label: "学习任务", icon: "fact_check", hrefRoute: "learning", routes: ["learning"] },
];

const coursePageTitles: Readonly<Record<TeacherCourseRoute, string>> = {
  "course-detail": "课程概览",
  learning: "学习任务",
  ai: "工作台",
  knowledge: "课程知识",
  graph: "课程知识",
  "classroom-studio": "AI课堂",
  resources: "资源管理",
  edit: "课程设置",
};

export function getCourseNavigation() {
  return courseNavigation;
}

export function getCoursePageTitle(route: TeacherCourseRoute): string {
  return coursePageTitles[route] ?? "课程工作区";
}

export function isCourseWorkspaceRoute(route: string): route is TeacherCourseRoute {
  return Object.hasOwn(coursePageTitles, route);
}
```

- [ ] **Step 2: Run the focused test and verify it passes**

Run: `pnpm test -- src/stitch/course/courseNavigation.test.ts`

Expected: the three navigation tests PASS.

- [ ] **Step 3: Commit the navigation model**

```text
git add Edu_AI/src/stitch/course/courseNavigation.ts Edu_AI/src/stitch/course/courseNavigation.test.ts
git commit -m "refactor: define course top workbar navigation"
```

### Task 3: Lock the shell structure and role rules with a failing contract test

**Files:**
- Create: `Edu_AI/src/stitch/course/CourseShell.test.ts`

- [ ] **Step 1: Add a source-contract test for the approved shell**

```ts
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("course shell uses a top workbar without a sidebar or left drawer", async () => {
  const shell = await readFile(new URL("./CourseShell.tsx", import.meta.url), "utf8");

  assert.match(shell, /className="course-shell__workbar"/u);
  assert.match(shell, /className="course-navigation course-navigation--desktop"/u);
  assert.match(shell, /className="course-shell__mobile-panel"/u);
  assert.doesNotMatch(shell, /course-shell__sidebar|course-shell__drawer|返回全部课程/u);
});

test("course settings live only in the teacher course menu", async () => {
  const shell = await readFile(new URL("./CourseShell.tsx", import.meta.url), "utf8");

  assert.match(shell, /!isStudent[\s\S]*course-shell__course-trigger/u);
  assert.match(shell, /buildRoleCourseHash\(user\?\.role, "edit", courseId\)/u);
  assert.match(shell, /<span>课程设置<\/span>/u);
  assert.match(shell, /isStudent[\s\S]*course-shell__course-name/u);
  assert.doesNotMatch(shell, /studentNavigationLabels/u);
});
```

- [ ] **Step 2: Run the focused test and verify the expected failure**

Run: `pnpm test -- src/stitch/course/CourseShell.test.ts`

Expected: FAIL because the current shell still contains sidebar and left-drawer markup and has no top workbar/course menu.

### Task 4: Build the responsive top workbar

**Files:**
- Modify: `Edu_AI/src/stitch/course/CourseShell.tsx`
- Modify: `Edu_AI/src/stitch/styles.css:782-904,1138-1146`
- Test: `Edu_AI/src/stitch/course/CourseShell.test.ts`

- [ ] **Step 1: Replace drawer state with course-menu and mobile-menu state**

Use `useRef` for the teacher course-menu container and add one effect that closes both menus on route changes, Escape, or a pointer event outside the menu. Keep `homeHashForRole` for the Edu AI brand and `buildRoleCourseHash` for every course destination.

```ts
const [courseMenuOpen, setCourseMenuOpen] = useState(false);
const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
const courseMenuRef = useRef<HTMLDivElement | null>(null);

useEffect(() => {
  setCourseMenuOpen(false);
  setMobileMenuOpen(false);
}, [activeRoute]);

useEffect(() => {
  const closeOnEscape = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      setCourseMenuOpen(false);
      setMobileMenuOpen(false);
    }
  };
  const closeOutside = (event: PointerEvent) => {
    if (!courseMenuRef.current?.contains(event.target as Node)) setCourseMenuOpen(false);
  };
  document.addEventListener("keydown", closeOnEscape);
  document.addEventListener("pointerdown", closeOutside);
  return () => {
    document.removeEventListener("keydown", closeOnEscape);
    document.removeEventListener("pointerdown", closeOutside);
  };
}, []);
```

- [ ] **Step 2: Render the shared five-link navigation for desktop and mobile**

Each link uses the canonical item label for both actors, `buildRoleCourseHash(user?.role, item.hrefRoute, courseId)`, `aria-current="page"` when active, and closes the mobile panel after navigation. Teacher/student active detection continues to use `studentRouteByNavigationId` for student routes and `item.routes` for teacher routes.

- [ ] **Step 3: Replace the shell markup with the top workbar**

The resulting structure must be:

```tsx
<div className="course-shell" data-testid="course-shell">
  <header className="course-shell__workbar">
    <a href={homeHref} className="course-shell__brand">Edu AI</a>
    <div className="course-shell__course" ref={courseMenuRef}>
      {!isStudent ? (
        <button
          type="button"
          className="course-shell__course-trigger"
          aria-haspopup="menu"
          aria-expanded={courseMenuOpen}
          title={course?.title ?? "当前课程"}
          onClick={() => setCourseMenuOpen((open) => !open)}
        >
          <span>{course?.title ?? "当前课程"}</span>
          <MaterialIcon name={courseMenuOpen ? "expand_less" : "expand_more"} />
        </button>
      ) : (
        <span className="course-shell__course-name" title={course?.title ?? "当前课程"}>
          {course?.title ?? "当前课程"}
        </span>
      )}
      {!isStudent && courseMenuOpen ? (
        <div className="course-shell__course-menu" role="menu">
          <a role="menuitem" href={buildRoleCourseHash(user?.role, "edit", courseId)}>
            <MaterialIcon name="settings" />
            <span>课程设置</span>
          </a>
        </div>
      ) : null}
    </div>
    {renderNavigation("desktop")}
    <div className="course-shell__actions">
      <JobCenterTrigger placement="inline" />
      <a className="course-shell__profile" href={routeHref(routes.profile)}>
        <MaterialIcon name="person" /><span>个人中心</span>
      </a>
      <button
        type="button"
        className="course-shell__mobile-menu"
        aria-label="打开课程工作栏"
        aria-expanded={mobileMenuOpen}
        onClick={() => setMobileMenuOpen((open) => !open)}
      ><MaterialIcon name={mobileMenuOpen ? "close" : "menu_book"} /></button>
    </div>
  </header>
  {mobileMenuOpen ? <div className="course-shell__mobile-panel">{renderNavigation("mobile")}</div> : null}
  <h1 className="sr-only">{pageTitle}</h1>
  <div className="course-shell__page">{content}</div>
</div>
```

- [ ] **Step 4: Replace sidebar CSS with workbar CSS**

Use a 72px sticky header, a four-column desktop grid, horizontally arranged workbar links, a positioned teacher menu, and a dropdown mobile panel. At `max-width: 980px`, hide `.course-navigation--desktop`, show `.course-shell__mobile-menu`, truncate the course name, and display the mobile navigation as a top dropdown; never use fixed left positioning or a left-side transform.

Key layout declarations:

```css
:root { --course-header-height: 72px; }
.course-shell { min-height: 100vh; background: var(--course-shell-bg); color: var(--course-shell-ink); }
.course-shell__workbar { position: sticky; top: 0; z-index: 60; display: grid; grid-template-columns: auto minmax(140px,240px) minmax(0,1fr) auto; min-height: var(--course-header-height); align-items: center; gap: 18px; border-bottom: 1px solid var(--course-shell-line); background: color-mix(in srgb,var(--course-shell-nav) 94%,transparent); padding: 10px 24px; backdrop-filter: blur(14px); }
.course-navigation--desktop { display: flex; min-width: 0; align-items: center; justify-content: center; gap: 4px; }
.course-navigation__link { display: inline-flex; min-height: 42px; align-items: center; border-radius: 11px; padding: 0 13px; color: var(--course-shell-muted); font-size: 13px; font-weight: 760; }
.course-navigation__link.is-active { background: var(--course-shell-brand-soft); color: var(--course-shell-brand); box-shadow: inset 0 -2px 0 var(--course-shell-brand); }
.course-shell__course { position: relative; min-width: 0; }
.course-shell__course-trigger,.course-shell__course-name { display: flex; min-width: 0; width: 100%; align-items: center; gap: 6px; color: var(--course-shell-ink); font-size: 13px; font-weight: 800; }
.course-shell__course-trigger span,.course-shell__course-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.course-shell__course-menu { position: absolute; top: calc(100% + 12px); left: 0; z-index: 80; width: 190px; border: 1px solid var(--course-shell-line); border-radius: 12px; background: var(--course-shell-nav); padding: 6px; box-shadow: 0 16px 38px rgba(15,23,42,.15); }
.course-shell__mobile-menu,.course-shell__mobile-panel { display: none; }
```

- [ ] **Step 5: Run the navigation and shell tests**

Run: `pnpm test -- src/stitch/course/courseNavigation.test.ts src/stitch/course/CourseShell.test.ts`

Expected: both focused test files PASS.

- [ ] **Step 6: Commit the shell implementation**

```text
git add Edu_AI/src/stitch/course/CourseShell.tsx Edu_AI/src/stitch/course/CourseShell.test.ts Edu_AI/src/stitch/styles.css
git commit -m "feat: move course navigation to top workbar"
```

### Task 5: Run regression and production verification

**Files:**
- Verify: `Edu_AI/src/stitch/course/courseNavigation.ts`
- Verify: `Edu_AI/src/stitch/course/CourseShell.tsx`
- Verify: `Edu_AI/src/stitch/styles.css`

- [ ] **Step 1: Run the complete frontend test suite**

Run: `pnpm test`

Expected: all Node/TypeScript tests PASS with zero failures.

- [ ] **Step 2: Run lint**

Run: `pnpm lint`

Expected: ESLint exits 0 without new errors.

- [ ] **Step 3: Build the production frontend**

Run: `pnpm build`

Expected: Vite completes and writes `dist` with exit code 0.

- [ ] **Step 4: Inspect the final diff against the approved specification**

Confirm all five workbar entries and order, no persistent sidebar/drawer markup, no course switcher, overview absent from navigation, teacher-only settings, student plain course name, and responsive top dropdown behavior.

- [ ] **Step 5: Commit any verification-only corrections, then report exact command results**

If verification reveals a defect, add a failing regression assertion before correcting it, rerun the focused test, and commit the correction with a scoped `fix:` message.
